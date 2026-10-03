"""OLS partition profile mathematics (no database required).

The expected stations are the ones measured on the Lankaran ArcGIS reference
(design frame, see the comparison report): Take-off controls the
Approach/Take-off overlap until it reaches the horizontal Approach section,
and the Inner Horizontal takes over where Take-off reaches its height.
"""

import math

from app.modules.ols.envelope import (
    ApproachProfile,
    ApproachSection,
    AxisFrame,
    TakeoffProfile,
    arc_segments_per_quadrant,
    controlling_intervals,
    distance_to_segment,
    inner_horizontal_cut_station,
)


def close(value, expected, tolerance=1e-6):
    assert value is not None and abs(value - expected) <= tolerance, (value, expected)


def main() -> None:
    # ICAO_ANNEX_14_V1_ZANGILAN parameters; ``o`` is measured from the Strip end.
    strip_extension, clearway = 60.0, 300.0
    approach = ApproachProfile(280, 15, [ApproachSection(3000, 2, 1180), ApproachSection(3600, 2.5, 2260), ApproachSection(8400, 0, 4780)])
    takeoff = TakeoffProfile(clearway - strip_extension, 180, 12.5, 1200, 15000, 2)
    divergence_only = ApproachProfile(280, 15, [ApproachSection(3000, 2), ApproachSection(3600, 2.5), ApproachSection(8400, 0)])

    close(approach.height(3000), 60); close(approach.height(6600), 150); close(approach.height(15000), 150)
    close(approach.half_width(15000), 2390); close(divergence_only.half_width(15000), 2390)
    close(takeoff.half_width(takeoff.start), 90); close(takeoff.half_width(takeoff.start + 4080), 600); close(takeoff.half_width(takeoff.end), 600)
    close(takeoff.height(takeoff.end), 300)

    # Approach/Take-off: lower profile controls; equality where T reaches 150 m.
    intervals = controlling_intervals(approach, takeoff)
    assert [code for _, _, code in intervals] == ["TAKE_OFF_CLIMB", "APPROACH"], intervals
    close(intervals[0][0], 240); close(intervals[0][1] + strip_extension, 7800); close(intervals[1][1], 15000)

    # Inner Horizontal cut: centreline-controlling profile reaches 45 m.
    close(inner_horizontal_cut_station(approach, takeoff, 45) + strip_extension, 2550)
    close(inner_horizontal_cut_station(approach, None, 45) + strip_extension, 2310)
    close(inner_horizontal_cut_station(None, takeoff, 45) + strip_extension, 2550)
    assert inner_horizontal_cut_station(approach, takeoff, 1000) is None

    # Transitional apex: Approach edge reaches Strip half-width + 45 / (1/7).
    close(approach.station_for_half_width(140 + 45 / (100 / 7 / 100)) + strip_extension, 2160)
    assert approach.station_for_half_width(10_000) is None

    # A 5 % take-off starts lower but crosses the 2 % Approach at 0.05(o-240) = 0.02o.
    steep = TakeoffProfile(240, 180, 12.5, 1200, 15000, 5)
    steep_intervals = controlling_intervals(approach, steep)
    assert [code for _, _, code in steep_intervals] == ["TAKE_OFF_CLIMB", "APPROACH"], steep_intervals
    close(steep_intervals[0][1], 400)

    frame = AxisFrame((1000.0, 2000.0), math.cos(0.3), math.sin(0.3))
    x, y = frame.to_xy(123.4, -56.7)
    station, lateral = frame.to_frame(x, y)
    close(station, 123.4, 1e-9); close(lateral, -56.7, 1e-9)
    close(distance_to_segment((5, 5), (0, 0), (10, 0)), 5); close(distance_to_segment((15, 0), (0, 0), (10, 0)), 5)
    segments = arc_segments_per_quadrant(6000, 0.01)
    assert 6000 * (1 - math.cos(math.pi / 4 / segments)) <= 0.01
    print("OLS envelope smoke test passed.")


if __name__ == "__main__":
    main()
