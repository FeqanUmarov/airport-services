"""Profile mathematics for partitioning overlapping OLS surfaces.

All distances are metres measured in a projected CRS along the runway
centreline.  ``o`` is the outward distance from a direction's Approach inner
edge (the actual Strip end); heights are relative to one common datum.

The partition rules reproduce the ArcGIS reference workflow (Lankaran OLS):

* Approach and Take-off overlap: the surface with the lower relative profile
  controls; the boundary is a line perpendicular to the centreline at the
  station where both profiles are equal.
* Inner Horizontal: Approach/Take-off are retained up to the first station at
  which the centreline-controlling profile ``min(A, T)`` reaches the Inner
  Horizontal height; beyond it, inside the Inner Horizontal footprint, the
  Inner Horizontal controls.
* Conical is cut by the complete Approach/Take-off footprints.
* Transitional outer edge is offset from the Strip side by height / slope.

The cut stations depend only on the standard parameters and the actual
Strip/Clearway geometry; threshold elevations only affect the Z values.
"""

from dataclasses import dataclass
import math

TOLERANCE_M = 1e-9


@dataclass(frozen=True)
class ApproachSection:
    length: float
    slope_pct: float
    end_width: float | None = None


class ApproachProfile:
    """Relative height and half-width of an Approach as a function of ``o``."""

    def __init__(self, inner_width: float, divergence_pct: float, sections: list[ApproachSection]) -> None:
        if not sections:
            raise ValueError("Approach requires at least one section")
        self.inner_width = inner_width
        self.rows: list[tuple[float, float, float, float, float, float]] = []
        start = height = 0.0
        width = inner_width
        for section in sections:
            if section.length <= 0:
                raise ValueError("Approach section length must be positive")
            end_width = section.end_width if section.end_width is not None else width + 2 * section.length * divergence_pct / 100
            self.rows.append((start, start + section.length, height, section.slope_pct, width, end_width))
            start += section.length
            height += section.length * section.slope_pct / 100
            width = end_width
        self.total_length = start

    @property
    def breakpoints(self) -> list[float]:
        return [0.0, *(row[1] for row in self.rows)]

    def _row(self, o: float):
        for row in self.rows:
            if o <= row[1] + TOLERANCE_M:
                return row
        return self.rows[-1]

    def height(self, o: float) -> float:
        o = min(max(o, 0.0), self.total_length)
        start, _, height, slope, _, _ = self._row(o)
        return height + (o - start) * slope / 100

    def half_width(self, o: float) -> float:
        o = min(max(o, 0.0), self.total_length)
        start, end, _, _, width, end_width = self._row(o)
        return (width + (end_width - width) * (o - start) / (end - start)) / 2

    def station_for_half_width(self, half_width: float) -> float | None:
        """First ``o`` where the Approach side edge reaches ``half_width``."""
        for start, end, _, _, width, end_width in self.rows:
            if end_width / 2 >= half_width - TOLERANCE_M:
                if abs(end_width - width) < TOLERANCE_M:
                    return start
                ratio = (2 * half_width - width) / (end_width - width)
                return start + max(0.0, min(1.0, ratio)) * (end - start)
        return None


class TakeoffProfile:
    """Relative height and half-width of a Take-off climb surface."""

    def __init__(self, start: float, inner_width: float, divergence_pct: float, final_width: float, length: float, slope_pct: float) -> None:
        if length <= 0 or divergence_pct <= 0:
            raise ValueError("Take-off length and divergence must be positive")
        self.start = start
        self.inner_width = inner_width
        self.final_width = final_width
        self.divergence_pct = divergence_pct
        self.slope_pct = slope_pct
        self.end = start + length
        self.diverging_length = min(length, max(0.0, (final_width - inner_width) / 2 / (divergence_pct / 100)))

    @property
    def breakpoints(self) -> list[float]:
        points = [self.start, self.start + self.diverging_length, self.end]
        return sorted(set(points))

    def height(self, o: float) -> float:
        return (min(max(o, self.start), self.end) - self.start) * self.slope_pct / 100

    def half_width(self, o: float) -> float:
        distance = min(max(o, self.start), self.end) - self.start
        return min(self.final_width, self.inner_width + 2 * distance * self.divergence_pct / 100) / 2


def _crossings(first, second, low: float, high: float, breakpoints: list[float]) -> list[float]:
    """Sorted breakpoints in ``[low, high]`` including equal-height stations."""
    points = sorted({low, high, *(p for p in breakpoints if low < p < high)})
    result = [points[0]]
    for a, b in zip(points, points[1:]):
        da, db = first(a) - second(a), first(b) - second(b)
        if da * db < 0:
            result.append(a + (b - a) * da / (da - db))
        result.append(b)
    return result


def controlling_intervals(approach: ApproachProfile, takeoff: TakeoffProfile) -> list[tuple[float, float, str]]:
    """Stations where Approach and Take-off overlap, labelled by the lower surface."""
    low, high = max(0.0, takeoff.start), min(approach.total_length, takeoff.end)
    if high - low <= TOLERANCE_M:
        return []
    points = _crossings(takeoff.height, approach.height, low, high, approach.breakpoints + takeoff.breakpoints)
    intervals: list[tuple[float, float, str]] = []
    for a, b in zip(points, points[1:]):
        if b - a <= TOLERANCE_M:
            continue
        middle = (a + b) / 2
        label = "TAKE_OFF_CLIMB" if takeoff.height(middle) <= approach.height(middle) else "APPROACH"
        if intervals and intervals[-1][2] == label and abs(intervals[-1][1] - a) <= TOLERANCE_M:
            intervals[-1] = (intervals[-1][0], b, label)
        else:
            intervals.append((a, b, label))
    return intervals


def inner_horizontal_cut_station(approach: ApproachProfile | None, takeoff: TakeoffProfile | None, height: float) -> float | None:
    """First ``o`` where the centreline-controlling profile reaches ``height``."""
    surfaces = []
    if approach is not None:
        surfaces.append((approach.height, 0.0, approach.total_length, approach.breakpoints))
    if takeoff is not None:
        surfaces.append((takeoff.height, takeoff.start, takeoff.end, takeoff.breakpoints))
    if not surfaces:
        return None
    breakpoints = [point for surface in surfaces for point in surface[3]]
    low = max(0.0, min(surface[1] for surface in surfaces))
    high = max(surface[2] for surface in surfaces)
    first, second = surfaces[0][0], surfaces[-1][0]
    points = _crossings(first, second, low, high, breakpoints)
    for a, b in zip(points, points[1:]):
        if b - a <= TOLERANCE_M:
            continue
        middle = (a + b) / 2
        active = [function for function, start, end, _ in surfaces if start <= middle <= end]
        if not active:
            continue
        # The candidates are linear inside (a, b) and do not cross there, so
        # the controlling surface is fixed across the interval.
        surface = min(active, key=lambda function: function(middle))
        ha, hb = surface(a), surface(b)
        if ha >= height - TOLERANCE_M:
            return a
        if hb >= height - TOLERANCE_M:
            return a + (b - a) * (height - ha) / (hb - ha)
    return None


@dataclass(frozen=True)
class AxisFrame:
    """Metric centreline frame: ``station`` along ``u`` and ``lateral`` to its left."""

    origin: tuple[float, float]
    ux: float
    uy: float

    def to_frame(self, x: float, y: float) -> tuple[float, float]:
        dx, dy = x - self.origin[0], y - self.origin[1]
        return dx * self.ux + dy * self.uy, -dx * self.uy + dy * self.ux

    def to_xy(self, station: float, lateral: float) -> tuple[float, float]:
        return (
            self.origin[0] + station * self.ux - lateral * self.uy,
            self.origin[1] + station * self.uy + lateral * self.ux,
        )


def distance_to_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    ratio = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
    return math.dist(point, (start[0] + ratio * dx, start[1] + ratio * dy))


def arc_segments_per_quadrant(radius: float, tolerance: float) -> int:
    """Quarter-circle segment count keeping the chord sagitta within tolerance."""
    if radius <= tolerance:
        return 1
    return max(8, math.ceil((math.pi / 2) / (2 * math.acos(1 - tolerance / radius))))
