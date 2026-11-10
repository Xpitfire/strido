"""`strido`: workspace CLI over the hardware knowledge index, plus the MCP server.

strido mcp                       # hardware MCP server on stdio (used by .mcp.json)
strido part electronics_deck     # one catalogue part as JSON
strido parts --kind printed      # list parts
strido fastener iso4762_m3x10
strido pinout lcd                # pins/devices matching "lcd"
strido limits FL
strido fits --status warn
strido clearances --max-gap 1.0
strido status                    # verification report headlines
"""

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from . import hardware_index


def _print(value: Any) -> None:
    json.dump(value, sys.stdout, indent=1, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="strido", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("mcp", help="hardware MCP server on stdio")
    sub.add_parser("status", help="verification report headlines")
    parts = sub.add_parser("parts", help="list catalogue parts")
    parts.add_argument("--kind", default="all", choices=("all", "printed", "purchased", "fastener"))
    part = sub.add_parser("part", help="one catalogue part")
    part.add_argument("part_id")
    fastener = sub.add_parser("fastener", help="fastener catalogue entry")
    fastener.add_argument("spec")
    pinout = sub.add_parser("pinout", help="controller pins, I²C devices, servo channels")
    pinout.add_argument("query", nargs="?", default="")
    limits = sub.add_parser("limits", help="joint limits of one leg")
    limits.add_argument("leg", choices=hardware_index.LEG_NAMES)
    fits = sub.add_parser("fits", help="screw fits and bearing seats")
    fits.add_argument("--status", default="fail", choices=("ok", "warn", "fail"))
    clearances = sub.add_parser("clearances", help="tight moving-part pairs")
    clearances.add_argument("--max-gap", type=float, default=1.0)
    bom = sub.add_parser("bom", help="BOM line with offers (no id: all lines)")
    bom.add_argument("line_id", nargs="?", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "mcp":
        from .mcp_server import serve

        serve()
        return 0
    queries: dict[str, Callable[[], Any]] = {
        "status": hardware_index.verification_status,
        "parts": lambda: hardware_index.list_parts(args.kind),
        "part": lambda: hardware_index.get_part(args.part_id),
        "fastener": lambda: hardware_index.get_fastener(args.spec),
        "pinout": lambda: hardware_index.pinout(args.query),
        "limits": lambda: hardware_index.joint_limits(args.leg),
        "fits": lambda: hardware_index.fits_summary(args.status),
        "clearances": lambda: hardware_index.clearance_pairs(args.max_gap),
        "bom": lambda: hardware_index.bom_line(args.line_id),
    }
    try:
        _print(queries[args.command]())
    except (KeyError, ValueError, hardware_index.MissingArtefactError) as error:
        print(f"strido: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
