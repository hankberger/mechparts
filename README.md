# mechparts

Agent-native parametric mechanical parts library. AI agents search for a part
family, read its parameter JSON Schema, and get back a watertight STL, STEP or
3MF file that matches the requested dimensions exactly.

Work in progress. Full documentation arrives with milestone 3.

## Quick start

```bash
uv sync
uv run mechparts serve          # HTTP API on :8000, MCP (streamable HTTP) at /mcp
uv run mechparts mcp            # MCP over stdio, for desktop agent clients
uv run pytest
```

OpenAPI docs: http://127.0.0.1:8000/docs
