"""Command line entry point: ``mechparts serve`` or ``mechparts mcp``."""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mechparts", description="Agent-native parametric parts server.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the HTTP API with the MCP server mounted at /mcp.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("mcp", help="Run the MCP server over stdio (for desktop agent clients).")

    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn

        os.environ.setdefault("MECHPARTS_BASE_URL", f"http://{args.host}:{args.port}")
        from mechparts.http import create_app

        uvicorn.run(create_app(mcp_host=args.host), host=args.host, port=args.port)
    elif args.command == "mcp":
        from mechparts.mcp_server import create_mcp_server

        create_mcp_server().run("stdio")


if __name__ == "__main__":
    main()
