"""Smoke test of the hardware MCP server over real stdio: list the tools and call each cheap one.

    make mcp-smoke

Exit 1 if the server does not start, a tool is missing, or a call returns an error.
`measure_gap` is skipped (it loads the CAD; covered by `make verify`).
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

EXPECTED_TOOLS = {
    "list_parts",
    "get_part",
    "get_fastener",
    "fits",
    "clearances",
    "measure_gap",
    "joint_limits",
    "pinout",
    "bom_line",
    "verification_status",
}
CALLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("list_parts", {"kind": "printed"}),
    ("get_part", {"part_id": "electronics_deck"}),
    ("get_fastener", {"spec": "iso4762_m3x10"}),
    ("fits", {"status": "fail"}),
    ("clearances", {"max_gap_mm": 1.0}),
    ("joint_limits", {"leg": "FL"}),
    ("pinout", {"query": "lcd"}),
    ("bom_line", {"line_id": "pi5_4gb"}),
    ("verification_status", {}),
)


async def run() -> int:
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "strido_workspace.cli", "mcp"])
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        missing = EXPECTED_TOOLS - tools
        if missing:
            print(f"FAIL missing tools: {sorted(missing)}")
            return 1
        failures = 0
        for name, arguments in CALLS:
            result = await session.call_tool(name, arguments)
            text = "".join(getattr(block, "text", "") for block in result.content)
            status = "ERROR" if result.isError else "ok"
            failures += result.isError
            print(f"{status:5s} {name}({json.dumps(arguments)}) -> {text[:110]!r}")
        print(f"mcp-smoke: {len(tools)} tools, {len(CALLS) - failures}/{len(CALLS)} calls ok")
        return 1 if failures else 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
