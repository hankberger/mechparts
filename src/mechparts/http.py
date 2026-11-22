"""FastAPI HTTP API. The MCP server is mounted on the same app at /mcp."""

from __future__ import annotations

import contextlib
from typing import Annotated, Any

from fastapi import Body, FastAPI, Path, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from mechparts import __version__
from mechparts.core.models import GenerationResult, OutputFormat, PartDetail, PartSummary, ValidationResult
from mechparts.service import PartService, ServiceError


class ParamsBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict, description="Parameter values; omitted ones take defaults.")


class GenerateBody(ParamsBody):
    format: OutputFormat = Field("stl", description="Output file format.")


class ErrorBody(BaseModel):
    error: dict[str, Any]


ERRORS = {404: {"model": ErrorBody}, 422: {"model": ErrorBody}, 500: {"model": ErrorBody}}


def create_app(service: PartService | None = None, mount_mcp: bool = True, mcp_host: str = "127.0.0.1") -> FastAPI:
    service = service or PartService()
    mcp_server = None
    if mount_mcp:
        from mechparts.mcp_server import create_mcp_server

        mcp_server = create_mcp_server(service)
        mcp_app = mcp_server.streamable_http_app(streamable_http_path="/mcp", host=mcp_host)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if mcp_server is None:
            yield
            return
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(
        title="mechparts",
        version=__version__,
        description=(
            "Agent-native parametric mechanical parts. Search part families, read their parameter JSON "
            "Schema, validate parameters, then generate an STL, STEP or 3MF file. All lengths are mm. "
            "Generated files are CC0-1.0."
        ),
        lifespan=lifespan,
    )
    app.state.service = service

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(exc.to_dict(), status_code=exc.status)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/parts", response_model=list[PartSummary], tags=["parts"], operation_id="search_parts")
    def search_parts(
        query: Annotated[str, Query(description="Free-text keywords, e.g. 'gear 20 teeth'.")] = "",
        tags: Annotated[list[str] | None, Query(description="Only parts having all of these tags.")] = None,
        standard: Annotated[str | None, Query(description="Only parts related to this standard, e.g. 'M3', '608'.")] = None,
    ) -> list[PartSummary]:
        """Search part families by keyword, tag and standard. An empty query lists all families."""
        return service.search_parts(query, tags, standard)

    @app.get("/v1/parts/{part_id}", response_model=PartDetail, responses=ERRORS, tags=["parts"], operation_id="get_part")
    def get_part(part_id: Annotated[str, Path(description="Part family id from search_parts.")]) -> PartDetail:
        """Full metadata and the parameter JSON Schema for one part family."""
        return service.get_part(part_id)

    @app.post(
        "/v1/parts/{part_id}/validate",
        response_model=ValidationResult,
        responses=ERRORS,
        tags=["parts"],
        operation_id="validate_parameters",
    )
    def validate_parameters(part_id: str, body: Annotated[ParamsBody, Body()] = ParamsBody()) -> ValidationResult:
        """Check parameters without generating. Returns issues, resolved params and computed dimensions."""
        return service.validate_parameters(part_id, body.params)

    @app.post(
        "/v1/parts/{part_id}/generate",
        response_model=GenerationResult,
        responses=ERRORS,
        tags=["parts"],
        operation_id="generate_part",
    )
    def generate_part(part_id: str, body: Annotated[GenerateBody, Body()] = GenerateBody()) -> GenerationResult:
        """Generate a part file. Returns a download URL plus dimensions, bounding box, volume and hash."""
        return service.generate_part(part_id, body.params, body.format)

    @app.get(
        "/v1/download/{hash}/{format}",
        responses={200: {"content": {"model/stl": {}, "model/step": {}, "model/3mf": {}}}, **ERRORS},
        response_class=Response,
        tags=["files"],
        operation_id="download",
    )
    def download(
        hash: Annotated[str, Path(description="Hash returned by generate_part.")],
        format: Annotated[str, Path(description="stl, step or 3mf.")],
    ) -> Response:
        """Fetch a generated file. Any format can be fetched for a hash generated before in another format."""
        f = service.download(hash, format)
        return Response(
            content=f.data,
            media_type=f.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{f.filename}"',
                "X-Content-SHA256": f.result.file_sha256,
                "X-Part-License": f.result.license,
            },
        )

    if mount_mcp:
        app.mount("/", mcp_app)
    return app
