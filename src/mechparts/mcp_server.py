"""MCP server exposing the same five operations as the HTTP API, as tools."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent, ToolAnnotations
from pydantic import Field

from mechparts import __version__
from mechparts.core.models import GenerationResult, PartDetail, PartSummary, ValidationResult
from mechparts.service import PartService, ServiceError

INSTRUCTIONS = """\
Parametric, 3D-printable mechanical parts. All lengths are millimetres; generated files are CC0-1.0.
Typical flow: search_parts -> get_part (read parameters_schema) -> validate_parameters -> generate_part.
Errors come back as JSON with an issues list naming the parameter, the problem, and allowed_min/allowed_max
where known; adjust and retry. generate_part returns a hash; download(hash, format) fetches the file in
any format later, and file_path is the file on the server's disk when it runs locally.
"""

MAX_EMBED_BYTES = 8 * 1024 * 1024
READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
IDEMPOTENT = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def _tool_error(exc: ServiceError) -> ToolError:
    return ToolError(json.dumps(exc.to_dict()))


def create_mcp_server(service: PartService | None = None) -> MCPServer:
    service = service or PartService()
    mcp = MCPServer(name="mechparts", version=__version__, instructions=INSTRUCTIONS)

    @mcp.tool(annotations=READ_ONLY)
    def search_parts(
        query: Annotated[str, Field(description="Free-text keywords, e.g. 'gear', 'pulley GT2'. Empty lists all.")] = "",
        tags: Annotated[list[str] | None, Field(description="Only parts having all of these tags.")] = None,
        standard: Annotated[str | None, Field(description="Only parts related to this standard, e.g. 'M3', '608'.")] = None,
    ) -> list[PartSummary]:
        """Search part families by keyword, tag and standard."""
        return service.search_parts(query, tags, standard)

    @mcp.tool(annotations=READ_ONLY)
    def get_part(part_id: Annotated[str, Field(description="Part family id from search_parts.")]) -> PartDetail:
        """Full metadata for a part family, including the JSON Schema of its parameters."""
        try:
            return service.get_part(part_id)
        except ServiceError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=READ_ONLY)
    def validate_parameters(
        part_id: Annotated[str, Field(description="Part family id.")],
        params: Annotated[dict[str, Any] | None, Field(description="Parameter values; omitted ones take defaults.")] = None,
    ) -> ValidationResult:
        """Check parameters without generating. Returns issues, resolved params and computed dimensions."""
        try:
            return service.validate_parameters(part_id, params or {})
        except ServiceError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=IDEMPOTENT)
    def generate_part(
        part_id: Annotated[str, Field(description="Part family id.")],
        params: Annotated[dict[str, Any] | None, Field(description="Parameter values; omitted ones take defaults.")] = None,
        format: Annotated[Literal["stl", "step", "3mf"], Field(description="Output file format.")] = "stl",
    ) -> GenerationResult:
        """Generate a part file. Returns download_url, file_path, resolved params, key dimensions,
        bounding box, volume and a stable hash."""
        try:
            return service.generate_part(part_id, params or {}, format)
        except ServiceError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=IDEMPOTENT)
    def download(
        hash: Annotated[str, Field(description="Hash returned by generate_part.")],
        format: Annotated[Literal["stl", "step", "3mf"], Field(description="Output file format.")] = "stl",
        include_content: Annotated[
            bool, Field(description="Embed the file bytes (base64) in the result. Files over 8 MB are never embedded.")
        ] = False,
    ) -> CallToolResult:
        """Fetch a previously generated file by hash, in any format."""
        try:
            f = service.download(hash, format)
        except ServiceError as exc:
            raise _tool_error(exc) from exc
        meta = f.result.model_dump(mode="json")
        content: list[Any] = [TextContent(type="text", text=json.dumps(meta))]
        if include_content:
            if len(f.data) > MAX_EMBED_BYTES:
                meta["warnings"] = [*meta.get("warnings", []), "File too large to embed; use download_url or file_path."]
                content[0] = TextContent(type="text", text=json.dumps(meta))
            else:
                content.append(
                    EmbeddedResource(
                        type="resource",
                        resource=BlobResourceContents(
                            uri=f.result.download_url,
                            mime_type=f.media_type,
                            blob=base64.b64encode(f.data).decode(),
                        ),
                    )
                )
        return CallToolResult(content=content, structured_content=meta)

    return mcp
