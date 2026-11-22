"""The five operations, shared by the HTTP API and the MCP server."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from mechparts.config import Settings
from mechparts.core import registry
from mechparts.core.db import Database
from mechparts.core.geometry import GeometryError
from mechparts.core.hashing import geometry_hash
from mechparts.core.models import (
    BoundingBox,
    GenerationResult,
    OutputFormat,
    ParamIssue,
    PartDetail,
    PartSummary,
    ValidationResult,
)
from mechparts.core.part import PartFamily
from mechparts.core.runner import Runner, RunnerCrashed, RunnerTimeout, make_runner, produce
from mechparts.core.storage import LocalStorage, Storage

# build123d logs every extrude at INFO, which floods server logs.
logging.getLogger("build123d").setLevel(logging.WARNING)

FORMATS: tuple[OutputFormat, ...] = ("stl", "step", "3mf")
MEDIA_TYPES = {
    "stl": "model/stl",
    "step": "model/step",
    "3mf": "model/3mf",
}


class ServiceError(Exception):
    code = "error"
    status = 400

    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, **self.details}}


class UnknownPart(ServiceError):
    code = "unknown_part"
    status = 404


class InvalidParameters(ServiceError):
    code = "invalid_parameters"
    status = 422


class InvalidFormat(ServiceError):
    code = "invalid_format"
    status = 422


class GenerationFailed(ServiceError):
    code = "generation_failed"
    status = 500


class GenerationTimeout(ServiceError):
    code = "generation_timeout"
    status = 504


class NotFound(ServiceError):
    code = "not_found"
    status = 404


@dataclass
class FileResponse:
    result: GenerationResult
    data: bytes
    media_type: str
    filename: str


_PYDANTIC_CODES = {
    "greater_than_equal": "too_small",
    "greater_than": "too_small",
    "less_than_equal": "too_large",
    "less_than": "too_large",
    "extra_forbidden": "unknown_parameter",
    "literal_error": "invalid_choice",
    "missing": "missing",
}


def _schema_issues(part: PartFamily, err: ValidationError) -> list[ParamIssue]:
    issues = []
    known = sorted(part.Params.model_fields)
    for e in err.errors():
        param = ".".join(str(x) for x in e["loc"])
        code = _PYDANTIC_CODES.get(e["type"], e["type"])
        ctx = e.get("ctx") or {}
        msg = f"{param}: {e['msg']}"
        if code == "unknown_parameter":
            msg = f"Unknown parameter {param!r} for {part.id}. Valid parameters: {', '.join(known)}."
        elif "input" in e and code in ("too_small", "too_large", "invalid_choice"):
            msg = f"{param}={e['input']!r}: {e['msg']}."
        lo = ctx.get("ge", ctx.get("gt"))
        hi = ctx.get("le", ctx.get("lt"))
        issues.append(
            ParamIssue(
                param=param,
                code=code,
                message=msg,
                allowed_min=float(lo) if code == "too_small" and lo is not None else None,
                allowed_max=float(hi) if code == "too_large" and hi is not None else None,
            )
        )
    return issues


class PartService:
    def __init__(
        self,
        settings: Settings | None = None,
        storage: Storage | None = None,
        db: Database | None = None,
        runner: Runner | None = None,
    ):
        self.settings = settings or Settings()
        self.storage = storage or LocalStorage(self.settings.files_dir)
        self.db = db or Database(self.settings.db_path)
        self.runner = runner or make_runner(self.settings.workers, self.settings.timeout)
        self.db.sync_catalog(
            [
                {"id": p.id, "name": p.name, "summary": p.summary, "tags": p.tags, "standards": p.standards,
                 "version": p.generator_version}
                for p in registry.all_parts().values()
            ]
        )

    def close(self) -> None:
        self.runner.close()

    # Lookup -------------------------------------------------------------
    def _part(self, part_id: str) -> PartFamily:
        part = registry.get(part_id)
        if part is None:
            raise UnknownPart(
                f"No part family with id {part_id!r}.", available=sorted(registry.all_parts())
            )
        return part

    @staticmethod
    def _summary(p: PartFamily) -> PartSummary:
        return PartSummary(id=p.id, name=p.name, summary=p.summary, tags=p.tags, standards=p.standards)

    def search_parts(
        self, query: str = "", tags: list[str] | None = None, standard: str | None = None
    ) -> list[PartSummary]:
        """Keyword search over id, name, summary, description, tags and standards.

        ``tags`` must all be present (case-insensitive); ``standard`` must match one listed standard.
        Results are ordered by number of matching query words, then id.
        """
        words = [w for w in re.split(r"[^a-z0-9.]+", query.lower()) if w]
        want_tags = {t.lower() for t in tags or []}
        scored = []
        for p in registry.all_parts().values():
            ptags = {t.lower() for t in p.tags}
            pstds = {s.lower() for s in p.standards}
            if want_tags and not want_tags <= ptags:
                continue
            if standard and standard.lower() not in pstds:
                continue
            haystack = " ".join([p.id.replace("_", " "), p.name, p.summary, p.description, *p.tags, *p.standards]).lower()
            tokens = set(re.split(r"[^a-z0-9.]+", haystack))
            score = sum(1 for w in words if w in tokens or (len(w) > 3 and w in haystack))
            if words and score == 0:
                continue
            scored.append((-score, p.id, p))
        return [self._summary(p) for _, _, p in sorted(scored, key=lambda t: (t[0], t[1]))]

    def get_part(self, part_id: str) -> PartDetail:
        p = self._part(part_id)
        return PartDetail(
            **self._summary(p).model_dump(),
            description=p.description,
            compatibility=p.compatibility,
            printability=p.printability,
            generator_version=p.generator_version,
            parameters_schema=p.parameters_schema(),
            computed_dimensions=p.computed_dimensions,
        )

    # Validation ---------------------------------------------------------
    def _resolve(self, part: PartFamily, params: dict[str, Any] | None) -> tuple[Any, list[ParamIssue]]:
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return None, [ParamIssue(param="", code="invalid", message="params must be a JSON object.")]
        try:
            model = part.Params.model_validate(params)
        except ValidationError as err:
            return None, _schema_issues(part, err)
        return model, part.check(model)

    def validate_parameters(self, part_id: str, params: dict[str, Any] | None) -> ValidationResult:
        part = self._part(part_id)
        model, issues = self._resolve(part, params)
        if model is None:
            return ValidationResult(part_id=part_id, valid=False, issues=issues)
        valid = not issues
        return ValidationResult(
            part_id=part_id,
            valid=valid,
            issues=issues,
            resolved_params=model.model_dump(mode="json"),
            computed=part.computed(model) if valid else None,
            warnings=part.warnings(model) if valid else [],
        )

    # Generation ---------------------------------------------------------
    def _check_format(self, fmt: str) -> OutputFormat:
        f = fmt.lower().lstrip(".") if isinstance(fmt, str) else fmt
        if f == "stp":
            f = "step"
        if f not in FORMATS:
            raise InvalidFormat(f"Unsupported format {fmt!r}. Use one of: {', '.join(FORMATS)}.")
        return f  # type: ignore[return-value]

    def _url(self, hash_: str, fmt: str) -> str:
        return f"{self.settings.base_url}/v1/download/{hash_}/{fmt}"

    def generate_part(self, part_id: str, params: dict[str, Any] | None, fmt: str = "stl") -> GenerationResult:
        part = self._part(part_id)
        fmt = self._check_format(fmt)
        model, issues = self._resolve(part, params)
        if model is None or issues:
            raise InvalidParameters(
                f"Parameters for {part_id} are invalid; fix the listed issues and retry.",
                issues=[i.model_dump(exclude_none=True) for i in issues],
            )
        resolved = model.model_dump(mode="json")
        hash_ = geometry_hash(part.id, part.generator_version, resolved)

        cached = self.db.get_file(hash_, fmt)
        if cached and self.storage.exists(cached["storage_key"]):
            result = GenerationResult.model_validate(cached["result"])
            return result.model_copy(
                update={
                    "cached": True,
                    "download_url": self._url(hash_, fmt),
                    "file_path": self.storage.local_path(cached["storage_key"]),
                }
            )

        try:
            bbox, volume, data = self.runner.run(produce, part.id, resolved, fmt, hash_)
        except GeometryError as err:
            raise GenerationFailed(
                f"Generating {part_id} failed a geometry check: {err}", resolved_params=resolved
            ) from err
        except RunnerTimeout as err:
            raise GenerationTimeout(
                f"Generating {part_id} took longer than {self.runner.timeout:g} s and was stopped. "
                "Reduce complexity (e.g. fewer teeth) or retry later.",
                resolved_params=resolved,
            ) from err
        except RunnerCrashed as err:
            raise GenerationFailed(f"The geometry worker crashed while generating {part_id}.") from err

        key = f"{hash_}.{fmt}"
        self.storage.put(key, data)
        sha = hashlib.sha256(data).hexdigest()
        result = GenerationResult(
            part_id=part.id,
            format=fmt,
            hash=hash_,
            file_sha256=sha,
            size_bytes=len(data),
            download_url=self._url(hash_, fmt),
            file_path=self.storage.local_path(key),
            resolved_params=resolved,
            computed=part.computed(model),
            bounding_box=BoundingBox.model_validate(bbox),
            volume_mm3=volume,
            watertight=True,
            cached=False,
            generator_version=part.generator_version,
            warnings=part.warnings(model),
            printability=part.printability,
        )
        self.db.record_geometry(hash_, part.id, part.generator_version, resolved)
        self.db.record_file(hash_, fmt, key, sha, len(data), result.model_dump(mode="json"))
        return result

    def download(self, hash_: str, fmt: str = "stl") -> FileResponse:
        """Fetch a generated file. If this geometry was generated before in another format,
        the requested format is produced from the stored parameters."""
        fmt = self._check_format(fmt)
        if not re.fullmatch(r"[0-9a-f]{32}", hash_ or ""):
            raise NotFound(f"Malformed hash {hash_!r}; expected 32 lowercase hex characters from generate_part.")
        rec = self.db.get_file(hash_, fmt)
        if rec is None or not self.storage.exists(rec["storage_key"]):
            geo = self.db.get_geometry(hash_)
            if geo is None:
                raise NotFound(f"No generated part with hash {hash_}. Call generate_part first.")
            part = self._part(geo["part_id"])
            if part.generator_version != geo["generator_version"]:
                raise NotFound(
                    f"Hash {hash_} was made by an older {part.id} generator; call generate_part again for a new hash."
                )
            self.generate_part(geo["part_id"], geo["params"], fmt)
            rec = self.db.get_file(hash_, fmt)
            assert rec is not None
        result = GenerationResult.model_validate(rec["result"]).model_copy(
            update={"cached": True, "download_url": self._url(hash_, fmt),
                    "file_path": self.storage.local_path(rec["storage_key"])}
        )
        return FileResponse(
            result=result,
            data=self.storage.get(rec["storage_key"]),
            media_type=MEDIA_TYPES[fmt],
            filename=f"{result.part_id}-{hash_[:12]}.{fmt}",
        )
