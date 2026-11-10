"""Result records of the fit check."""

from dataclasses import dataclass, field


@dataclass
class PartFit:
    part: str
    instance: str
    source: str
    start_mm: float  # where the screw enters the part, measured from the head bearing face
    span_mm: float
    hole_d_mm: float  # narrowest inscribed diameter along the span (0 = solid material)
    fit: str  # clearance | thread-forming | passage | bearing bore | tight passage | line-to-line | solid | oversize
    status: str  # ok | warn | fail
    note: str = ""
    engaged_mm: float = 0.0  # length where the screw cuts material (hole narrower than d); thread-forming grip


@dataclass
class ScrewFit:
    instance: str
    spec: str
    thread: str
    joint: str
    termination: str
    status: str
    parts: list[PartFit] = field(default_factory=list)
