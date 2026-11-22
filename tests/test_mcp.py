import asyncio
import json

from mcp import Client

from mechparts.mcp_server import create_mcp_server


def run(coro):
    return asyncio.run(coro)


def test_mcp_tools(service):
    server = create_mcp_server(service)

    async def scenario():
        async with Client(server) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert names == {"search_parts", "get_part", "validate_parameters", "generate_part", "download"}
            r = await c.call_tool("get_part", {"part_id": "spur_gear"})
            assert r.structured_content["id"] == "spur_gear"
            r = await c.call_tool("validate_parameters", {"part_id": "spur_gear", "params": {"bore_diameter": 30}})
            assert r.structured_content["valid"] is False
            r = await c.call_tool("generate_part", {"part_id": "spur_gear", "params": {"teeth": 13}, "format": "stl"})
            assert not r.is_error
            h = r.structured_content["hash"]
            r = await c.call_tool("download", {"hash": h, "format": "3mf", "include_content": True})
            assert not r.is_error and r.content[1].resource.mime_type == "model/3mf"
            r = await c.call_tool("generate_part", {"part_id": "spur_gear", "params": {"bore_diameter": 30}})
            assert r.is_error
            payload = json.loads(r.content[0].text.split(": ", 1)[1])
            assert payload["error"]["code"] == "invalid_parameters"

    run(scenario())
