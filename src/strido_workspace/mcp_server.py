"""`strido-hardware` MCP server: read-only hardware knowledge for coding agents (stdio).

Started by `.mcp.json` as `uv run --locked strido mcp`. Every tool wraps one query of
`strido_workspace.hardware_index`; failures come back as tool errors with the command
that builds the missing artefact.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import hardware_index

INSTRUCTIONS = (
    "Strido hardware facts from the tracked CAD data and the last verification run. "
    "Use it before editing parts, fasteners, wiring or firmware pins: part dimensions and masses, fastener specs, "
    "screw fits and bearing seats, moving-part clearances, joint limits, pin map, BOM offers, verification status. "
    "Lengths in mm, angles in degrees, currents in A, prices in EUR incl. VAT."
)

server = FastMCP("strido-hardware", instructions=INSTRUCTIONS, log_level="WARNING")


@server.tool()
def list_parts(kind: str = "all") -> list[dict[str, Any]]:
    """List catalogue parts: kind = printed | purchased | fastener | all."""
    return hardware_index.list_parts(kind)


@server.tool()
def get_part(part_id: str) -> dict[str, Any]:
    """One part: size, mass, material/print settings or vendor, assembly steps, measured screw fits."""
    return hardware_index.get_part(part_id)


@server.tool()
def get_fastener(spec: str) -> dict[str, Any]:
    """Fastener catalogue entry (e.g. iso4762_m3x10): nominal dimensions and count in the robot."""
    return hardware_index.get_fastener(spec)


@server.tool()
def fits(status: str = "fail") -> dict[str, Any]:
    """Screw-fit and bearing-seat results; lists the screws with status ok | warn | fail."""
    return hardware_index.fits_summary(status)


@server.tool()
def clearances(max_gap_mm: float = 1.0) -> dict[str, Any]:
    """Moving-part pairs whose minimum gap over all operating poses is below max_gap_mm."""
    return hardware_index.clearance_pairs(max_gap_mm)


@server.tool()
def measure_gap(part_a: str, part_b: str, pose: str = "stand_170mm") -> dict[str, Any]:
    """Exact minimum distance between two parts in a named pose (slow: loads the CAD)."""
    return hardware_index.measure_gap(part_a, part_b, pose)


@server.tool()
def joint_limits(leg: str) -> dict[str, Any]:
    """Safe joint limits (deg) of leg FL | FR | RL | RR from the range-of-motion sweep."""
    return hardware_index.joint_limits(leg)


@server.tool()
def pinout(query: str = "") -> dict[str, Any]:
    """XIAO ESP32-S3 pins, I²C addresses and PCA9685 servo channels; optional text filter."""
    return hardware_index.pinout(query)


@server.tool()
def bom_line(line_id: str = "") -> dict[str, Any]:
    """A BOM line with all vendor offers; empty id lists every line."""
    return hardware_index.bom_line(line_id)


@server.tool()
def verification_status() -> dict[str, Any]:
    """Headline result of every generated verification report."""
    return hardware_index.verification_status()


def serve() -> None:
    server.run("stdio")
