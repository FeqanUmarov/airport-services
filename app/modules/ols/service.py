import json
import math
from decimal import Decimal
from typing import Any

from pyproj import Transformer
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.ols.repository import OlsRepository
from app.modules.ols_revisions.repository import OlsRevisionRepository
from app.modules.ols.schemas import (
    AutomaticOlsGenerationResponse,
    GeneratedOlsSurface,
    ManualOlsCreate,
    OlsSurfaceListResponse,
    OlsSurfaceResponse,
    OlsSurfaceSummary,
)


# Geometric tolerances (not OLS dimensions; those always come from the standard).
SNAP_TOLERANCE_M = 0.001  # CRS round-trip noise against the stored Strip
ARC_TOLERANCE_M = 0.01  # maximum chord sagitta of Inner Horizontal/Conical arcs
TOPOLOGY_TOLERANCE_M = 0.01
NODE_TOLERANCE_M = 1e-5  # shared-node insertion; 10 x the overlay grid
STRIP_OFFSET_TOLERANCE_M = 0.50  # QA tolerance between threshold offset and Strip end


class OlsNotFoundError(ValueError): pass
class OlsValidationError(ValueError): pass


class AutomaticOlsService:
    RUN_LEVEL = {"INNER_HORIZONTAL", "CONICAL", "TRANSITIONAL"}
    DIRECTION_LEVEL = {"APPROACH", "TAKE_OFF_CLIMB", "TAKEOFF_CLIMB"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = OlsRepository(session)
        self.revisions = OlsRevisionRepository(session)

    @staticmethod
    def _number(parameters: dict[int, dict[str, Any]], aliases: tuple[str, ...], section: int = 0) -> float:
        source = parameters.get(section, {})
        for alias in aliases:
            if alias in source and source[alias] is not None:
                return float(source[alias])
        raise OlsValidationError(f"Missing OLS parameter ({'/'.join(aliases)}) for section {section}")

    @staticmethod
    def _direction_frame(centerline_geojson: str, threshold: tuple[float, float]) -> dict[str, Any]:
        coordinates = json.loads(centerline_geojson).get("coordinates", [])
        if len(coordinates) < 2:
            raise OlsValidationError("Runway centerline requires at least two coordinates")
        lon, lat = threshold
        zone = int((lon + 180) // 6) + 1
        srid = (32600 if lat >= 0 else 32700) + zone
        forward = Transformer.from_crs(4326, srid, always_xy=True)
        inverse = Transformer.from_crs(srid, 4326, always_xy=True)
        threshold_xy = forward.transform(lon, lat)
        first = forward.transform(*map(float, coordinates[0][:2]))
        last = forward.transform(*map(float, coordinates[-1][:2]))
        near, far = (first, last) if math.dist(threshold_xy, first) <= math.dist(threshold_xy, last) else (last, first)
        dx, dy = far[0] - near[0], far[1] - near[1]
        length = math.hypot(dx, dy)
        if length == 0:
            raise OlsValidationError("Runway centerline endpoints must be different")
        ux, uy = dx / length, dy / length
        threshold_station = (threshold_xy[0] - near[0]) * ux + (threshold_xy[1] - near[1]) * uy
        threshold_anchor = (near[0] + threshold_station * ux, near[1] + threshold_station * uy)
        return {"forward":forward,"inverse":inverse,"srid":srid,"near":near,"ux":ux,"uy":uy,"axis_length":length,"bearing":(math.degrees(math.atan2(ux,uy))+360)%360,"threshold_station":threshold_station,"threshold_anchor":threshold_anchor}

    @staticmethod
    def _geometry_stations(geojson: str, frame: dict[str, Any]) -> list[float]:
        geometry = json.loads(geojson)
        if geometry.get("type") == "Polygon": rings = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPolygon": rings = [ring for polygon in geometry.get("coordinates", []) for ring in polygon]
        else: raise OlsValidationError("Reference geometry must be Polygon or MultiPolygon")
        result=[]
        for ring in rings:
            for point in ring:
                x,y=frame["forward"].transform(float(point[0]),float(point[1])); result.append((x-frame["near"][0])*frame["ux"]+(y-frame["near"][1])*frame["uy"])
        if not result: raise OlsValidationError("Reference geometry has no coordinates")
        return result

    @staticmethod
    def _axis(frame: dict[str, Any]) -> AxisFrame:
        return AxisFrame(frame["near"], frame["ux"], frame["uy"])

    @staticmethod
    def _frame_polygon(axis: AxisFrame, root_station: float, points: list[tuple[float, float]]) -> dict[str, Any]:
        """Polygon from (outward distance, lateral offset) pairs of a direction."""
        ring = [list(axis.to_xy(root_station - outward, lateral)) for outward, lateral in points]
        return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}

    @staticmethod
    def _footprint_points(breakpoints: list[float], half_width) -> list[tuple[float, float]]:
        return [*((o, half_width(o)) for o in breakpoints), *((o, -half_width(o)) for o in reversed(breakpoints))]

    def _approach_profile(self, params: dict[int, dict[str, Any]]) -> ApproachProfile:
        sections = sorted(section for section in params if section > 0)
        if not sections:
            raise OlsValidationError("APPROACH requires at least one section")
        use_end_width = all(params[section].get("END_WIDTH") is not None for section in sections)
        return ApproachProfile(
            self._number(params, ("INNER_EDGE",)),
            self._number(params, ("DIVERGENCE",)),
            [
                ApproachSection(
                    self._number(params, ("LENGTH",), section),
                    self._number(params, ("SLOPE",), section),
                    self._number(params, ("END_WIDTH",), section) if use_end_width else None,
                )
                for section in sections
            ],
        )

    def _takeoff_profile(self, params: dict[int, dict[str, Any]], start: float) -> TakeoffProfile:
        return TakeoffProfile(
            start,
            self._number(params, ("INNER_EDGE",)),
            self._number(params, ("DIVERGENCE",)),
            self._number(params, ("FINAL_WIDTH",)),
            self._number(params, ("LENGTH", "TOTAL_LENGTH")),
            self._number(params, ("SLOPE",)),
        )

    @staticmethod
    def _with_z(geometry: dict[str, Any], elevation) -> list[list[list[tuple[float, float, float]]]]:
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        return [
            [[(float(point[0]), float(point[1]), float(elevation(float(point[0]), float(point[1])))) for point in ring] for ring in polygon]
            for polygon in polygons
        ]

    async def _partitioned_surfaces(self, configs: dict[str, dict[str, Any]], context: Any, airport: Any, directions: list[Any], run_id: int) -> dict[tuple[str, int | None], dict[str, Any]]:
        """Build every configured surface as one non-overlapping OLS partition.

        All geometry is computed in the runway's projected CRS.  Cut stations
        come from the standard profiles (see ``app.modules.ols.envelope``);
        the actual Strip and Clearway geometries are the shared boundaries.
        """
        repo = self.repository
        params = {code: config["parameters"] for code, config in configs.items()}
        frames = []
        for row in directions:
            coordinates = json.loads(row.threshold)["coordinates"]
            frames.append(self._direction_frame(context.centerline, (float(coordinates[0]), float(coordinates[1]))))
        srid = frames[0]["srid"]
        runway_axis = self._axis(frames[0])
        centerline = [frames[0]["forward"].transform(float(point[0]), float(point[1])) for point in json.loads(context.centerline)["coordinates"]]

        strip = await repo.active_strip(run_id)
        if strip is None and ({"APPROACH", "TRANSITIONAL"} & configs.keys()):
            raise OlsValidationError("APPROACH and TRANSITIONAL require an active Runway Strip")
        strip_shell = await repo.metric_geometry(strip[0].GEOM, srid, shell=True) if strip is not None else None
        strip_points = [tuple(point[:2]) for polygon in strip_shell["coordinates"] for point in polygon[0]] if strip_shell else []

        ih_height = ih_radius = ih_elevation = None
        if "INNER_HORIZONTAL" in params:
            ih_radius = self._number(params["INNER_HORIZONTAL"], ("HORIZONTAL_OFFSET", "OFFSET", "RADIUS"))
            ih_height = self._number(params["INNER_HORIZONTAL"], ("HEIGHT",))
            ih_elevation = float(airport.ELEVATION_M) + ih_height
        if ({"CONICAL", "TRANSITIONAL"} & configs.keys()) and ih_height is None:
            raise OlsValidationError("CONICAL and TRANSITIONAL require the INNER_HORIZONTAL configuration")
        conical_width = self._number(params["CONICAL"], ("HORIZONTAL_WIDTH", "WIDTH")) if "CONICAL" in params else 0.0
        outer_radius = (ih_radius or 0.0) + conical_width
        quad_segs = arc_segments_per_quadrant(max(outer_radius, 1.0), ARC_TOLERANCE_M)

        approach_profile = self._approach_profile(params["APPROACH"]) if "APPROACH" in params else None
        items = []
        for row, frame in zip(directions, frames):
            direction = row[0]
            axis = self._axis(frame)
            root = min(axis.to_frame(*point)[0] for point in strip_points) if strip_points else frame["threshold_station"]
            clearway_row = await repo.active_clearway(direction.RUN_DIR_ID)
            clearway = await repo.metric_geometry(clearway_row[0].GEOM, srid) if clearway_row is not None else None
            # A direction owns the CWY outside its own threshold; its outer end
            # edge holds the minimum stations in this direction frame. Take-off
            # starts at the innermost vertex of that edge and the CWY is then
            # subtracted, so both share the actual (possibly skewed) edge.
            if clearway:
                stations = [axis.to_frame(*point[:2])[0] for polygon in clearway["coordinates"] for point in polygon[0]]
                clearway_end = max(station for station in stations if station <= min(stations) + SNAP_TOLERANCE_M)
            else:
                clearway_end = frame["threshold_station"]
            takeoff_profile = self._takeoff_profile(params["TAKE_OFF_CLIMB"], root - clearway_end) if "TAKE_OFF_CLIMB" in params else None
            items.append({"direction": direction, "frame": frame, "axis": axis, "root": root, "clearway": clearway, "clearway_end": clearway_end, "approach_profile": approach_profile, "takeoff_profile": takeoff_profile})
        clearways = [item["clearway"] for item in items if item["clearway"]]

        ih_footprint = await repo.buffer_line(centerline, ih_radius, quad_segs, srid) if ih_radius is not None else None
        reach = outer_radius + max(
            [approach_profile.total_length if approach_profile else 0.0]
            + [item["takeoff_profile"].end for item in items if item["takeoff_profile"]]
        ) + math.dist(centerline[0], centerline[-1])

        def band(item: dict[str, Any], low: float, high: float) -> dict[str, Any]:
            return self._frame_polygon(item["axis"], item["root"], [(low, -reach), (high, -reach), (high, reach), (low, reach)])

        # Transitional outer edge: actual Strip side + IH height / slope. The
        # station where the Approach edge reaches it is inserted as an Approach
        # vertex so both surfaces share the same node.
        side_width: dict[int, float] = {}
        transitional_slope = None
        transitional_reach: list[float] = []
        transitional_bands: list[dict[str, Any]] = []
        if "TRANSITIONAL" in params:
            if approach_profile is None:
                raise OlsValidationError("TRANSITIONAL requires the APPROACH configuration")
            transitional_slope = self._number(params["TRANSITIONAL"], ("SLOPE",))
            if transitional_slope <= 0:
                raise OlsValidationError("TRANSITIONAL slope must be greater than zero")
            run = ih_height / (transitional_slope / 100)
            for side in (-1, 1):
                side_width[side] = max(side * runway_axis.to_frame(*point)[1] for point in strip_points)
                outer = side_width[side] + run
                reach_station = approach_profile.station_for_half_width(outer)
                if reach_station is None:
                    band_length = approach_profile.total_length
                else:
                    transitional_reach.append(reach_station)
                    # Run past the apex; that part lies inside the Approach and
                    # is removed, so the corner is the shared Approach vertex.
                    band_length = reach_station + run
                edges = []
                for item in items:
                    root_station = runway_axis.to_frame(*item["axis"].to_xy(item["root"], 0.0))[0]
                    sign = item["frame"]["ux"] * runway_axis.ux + item["frame"]["uy"] * runway_axis.uy
                    edges.append(root_station - sign * band_length)
                low, high = min(edges), max(edges)
                ring = [list(runway_axis.to_xy(s, v)) for s, v in ((low, 0.0), (high, 0.0), (high, side * outer), (low, side * outer))]
                transitional_bands.append({"type": "Polygon", "coordinates": [[*ring, ring[0]]]})

        # Approach / Take-off per direction.
        for item in items:
            approach, takeoff = item["approach_profile"], item["takeoff_profile"]
            item["approach_footprint"] = item["approach"] = item["takeoff"] = None
            item["notes"] = []
            if approach is not None:
                stations = sorted({*approach.breakpoints, *transitional_reach})
                footprint = self._frame_polygon(item["axis"], item["root"], self._footprint_points(stations, approach.half_width))
                footprint = await repo.snap(srid, footprint, strip_shell, SNAP_TOLERANCE_M)
                item["approach_footprint"] = footprint
                item["approach"] = await repo.difference(srid, footprint, strip_shell, *clearways)
            if takeoff is not None:
                footprint = self._frame_polygon(item["axis"], item["root"], self._footprint_points(takeoff.breakpoints, takeoff.half_width))
                item["takeoff"] = await repo.difference(srid, footprint, strip_shell, *clearways)
            if approach is not None and takeoff is not None:
                overlap = await repo.intersection(srid, item["approach"], item["takeoff"])
                if overlap:
                    intervals = controlling_intervals(approach, takeoff)
                    takeoff_band = await repo.union(srid, [band(item, a, b) for a, b, code in intervals if code == "TAKE_OFF_CLIMB"])
                    approach_band = await repo.union(srid, [band(item, a, b) for a, b, code in intervals if code == "APPROACH"])
                    item["approach"] = await repo.difference(srid, item["approach"], await repo.intersection(srid, overlap, takeoff_band))
                    item["takeoff"] = await repo.difference(srid, item["takeoff"], await repo.intersection(srid, overlap, approach_band))
                    item["notes"].append("Approach/Take-off overlap (distance from Strip end): " + ", ".join(f"{'Take-off' if code == 'TAKE_OFF_CLIMB' else 'Approach'} {a:.1f}-{b:.1f} m" for a, b, code in intervals))
            if ih_footprint is not None and (approach is not None or takeoff is not None):
                cut = inner_horizontal_cut_station(approach, takeoff, ih_height)
                if cut is not None:
                    removed = await repo.intersection(srid, ih_footprint, band(item, cut, reach))
                    item["approach"] = await repo.difference(srid, item["approach"], removed)
                    item["takeoff"] = await repo.difference(srid, item["takeoff"], removed)
                    item["notes"].append(f"Inner Horizontal controls beyond {cut:.1f} m from Strip end")
        approaches = [item["approach"] for item in items if item["approach"]]
        takeoffs = [item["takeoff"] for item in items if item["takeoff"]]

        transitional = None
        if transitional_bands:
            transitional = await repo.difference(
                srid, await repo.union(srid, transitional_bands), strip_shell, *clearways,
                *(item["approach_footprint"] for item in items), *takeoffs,
            )

        inner_horizontal = conical = None
        if ih_footprint is not None and "INNER_HORIZONTAL" in params:
            inner_horizontal = await repo.difference(srid, ih_footprint, strip_shell, *clearways, transitional, *approaches, *takeoffs)
        if "CONICAL" in params:
            outer = await repo.buffer_line(centerline, outer_radius, quad_segs, srid)
            conical = await repo.difference(srid, outer, ih_footprint, *approaches, *takeoffs)

        # Height functions (absolute elevations) evaluated at every vertex.
        def centerline_distance(x: float, y: float) -> float:
            return min(distance_to_segment((x, y), a, b) for a, b in zip(centerline, centerline[1:]))

        conical_slope = None
        if "CONICAL" in params:
            conical_height = self._number(params["CONICAL"], ("HEIGHT",))
            source = params["CONICAL"].get(0, {})
            conical_slope = float(source["SLOPE"]) if source.get("SLOPE") is not None else conical_height / conical_width * 100

        def approach_z(item: dict[str, Any]):
            base = float(item["direction"].THRESHOLD_ELEVATION_M)
            return lambda x, y: base + approach_profile.height(item["root"] - item["axis"].to_frame(x, y)[0])

        def takeoff_z(item: dict[str, Any]):
            direction, frame = item["direction"], item["frame"]
            base = float(direction.THRESHOLD_ELEVATION_M) + abs(item["clearway_end"] - frame["threshold_station"]) * float(direction.SLOPE_PCT) / 100
            profile = item["takeoff_profile"]
            return lambda x, y: base + profile.height(item["root"] - item["axis"].to_frame(x, y)[0])

        runway_profile = sorted(
            (runway_axis.to_frame(*item["axis"].to_xy(item["frame"]["threshold_station"], 0.0))[0], float(item["direction"].THRESHOLD_ELEVATION_M))
            for item in items
        )
        strip_range = (min(runway_axis.to_frame(*p)[0] for p in strip_points), max(runway_axis.to_frame(*p)[0] for p in strip_points)) if strip_points else (0.0, 0.0)

        def runway_elevation(station: float) -> float:
            (first_station, first_z), (last_station, last_z) = runway_profile[0], runway_profile[-1]
            if last_station - first_station <= 1e-9:
                return first_z
            ratio = min(1.0, max(0.0, (station - first_station) / (last_station - first_station)))
            return first_z + (last_z - first_z) * ratio

        def transitional_z(x: float, y: float) -> float:
            station, lateral = runway_axis.to_frame(x, y)
            side = 1 if lateral >= 0 else -1
            if strip_range[0] - SNAP_TOLERANCE_M <= station <= strip_range[1] + SNAP_TOLERANCE_M:
                lower_width, lower_z = side_width[side], runway_elevation(station)
            else:
                item = min(items, key=lambda candidate: math.dist((x, y), candidate["axis"].to_xy(candidate["root"], 0.0)))
                outward = item["root"] - item["axis"].to_frame(x, y)[0]
                lower_width, lower_z = approach_profile.half_width(outward), approach_z(item)(x, y)
            z = lower_z + max(0.0, abs(lateral) - lower_width) * transitional_slope / 100
            return min(z, max(lower_z, ih_elevation))

        result: dict[tuple[str, int | None], dict[str, Any]] = {}

        async def topology(geometry, gap_references, reference_name, message, extra_warning=False):
            others = [strip_shell, *clearways, *(value for value in (inner_horizontal, conical, transitional, *approaches, *takeoffs) if value and value is not geometry)]
            _, overlap_area, overlap_width = await repo.topology_metrics(srid, geometry, others)
            gap = (await repo.topology_metrics(srid, geometry, gap_references))[0] if any(gap_references) else 0.0
            passed = gap <= TOPOLOGY_TOLERANCE_M and overlap_width <= TOPOLOGY_TOLERANCE_M and not extra_warning
            return {"reference_geometry": reference_name, "topology_status": "PASSED" if passed else "WARNING", "topology_message": f"{message} Measured overlap with other OLS/Strip/CWY: {overlap_area:.4f} m² (sliver width {overlap_width:.6f} m).", "gap_m": round(gap, 4), "overlap_m": round(overlap_width, 4)}

        layers = {"INNER_HORIZONTAL": inner_horizontal, "CONICAL": conical, "TRANSITIONAL": transitional}
        for index, item in enumerate(items):
            layers[f"APPROACH:{index}"] = item["approach"]
            layers[f"TAKE_OFF_CLIMB:{index}"] = item["takeoff"]
        noded = {
            name: await repo.node(srid, value, [strip_shell, *clearways, *(other for key, other in layers.items() if key != name)], NODE_TOLERANCE_M)
            for name, value in layers.items()
        }
        inner_horizontal, conical, transitional = noded["INNER_HORIZONTAL"], noded["CONICAL"], noded["TRANSITIONAL"]
        for index, item in enumerate(items):
            item["approach"], item["takeoff"] = noded[f"APPROACH:{index}"], noded[f"TAKE_OFF_CLIMB:{index}"]
        approaches = [item["approach"] for item in items if item["approach"]]
        takeoffs = [item["takeoff"] for item in items if item["takeoff"]]

        def store(code: str, direction_id: int | None, geometry, elevation, topology_values) -> None:
            if not geometry:
                raise OlsValidationError(f"{code} is completely controlled by other OLS surfaces")
            result[(code, direction_id)] = {"geometry": repo.metric_multipolygon_z(self._with_z(geometry, elevation), srid), "topology": topology_values}

        for item in items:
            direction, designator = item["direction"], item["direction"].DESIGNATOR
            notes = "; ".join(item["notes"])
            if "APPROACH" in params:
                expected = item["frame"]["threshold_station"] - self._number(params["APPROACH"], ("START_DISTANCE", "THRESHOLD_OFFSET"))
                delta = abs(expected - item["root"])
                # The actual Strip end is the authoritative topology boundary; the
                # configured threshold offset is retained as a QA comparison.
                message = f"RWY {designator} Approach starts at the actual Strip end; configured offset differs by {delta:.3f} m ({'within' if delta <= STRIP_OFFSET_TOLERANCE_M else 'outside'} {STRIP_OFFSET_TOLERANCE_M:.2f} m QA tolerance). {notes}."
                store("APPROACH", direction.RUN_DIR_ID, item["approach"], approach_z(item), await topology(item["approach"], [strip_shell], "ACTUAL_RUNWAY_STRIP_END", message, delta > STRIP_OFFSET_TOLERANCE_M))
            if "TAKE_OFF_CLIMB" in params:
                if item["clearway"]:
                    reference, message = "CLEARWAY_END_AND_RUNWAY_CENTERLINE", f"RWY {designator} Take-off starts at RWY {designator} Clearway outer end. {notes}."
                else:
                    reference, message = "THRESHOLD_NO_CLEARWAY", f"RWY {designator} has no active Clearway; Take-off starts at its threshold. {notes}."
                store("TAKE_OFF_CLIMB", direction.RUN_DIR_ID, item["takeoff"], takeoff_z(item), await topology(item["takeoff"], [item["clearway"]], reference, message, not item["clearway"]))
        if "INNER_HORIZONTAL" in params:
            store("INNER_HORIZONTAL", None, inner_horizontal, lambda x, y: ih_elevation, await topology(inner_horizontal, [], "PARTITIONED_OLS_ENVELOPE", "Inner Horizontal excludes Strip, Clearway, Transitional and the controlling Approach/Take-off parts."))
        if "CONICAL" in params:
            store("CONICAL", None, conical, lambda x, y: ih_elevation + min(conical_height, max(0.0, centerline_distance(x, y) - ih_radius) * conical_slope / 100), await topology(conical, [inner_horizontal], "PARTITIONED_OLS_ENVELOPE", "Conical is cut by the Approach and Take-off footprints."))
        if "TRANSITIONAL" in params:
            store("TRANSITIONAL", None, transitional, transitional_z, await topology(transitional, [strip_shell, *approaches], "RUNWAY_STRIP_AND_APPROACH_BOUNDARIES", "Transitional lower boundary is the actual Strip and Approach edge; outer edge is the Strip side offset by Inner Horizontal height / slope."))
        return result

    async def generate(self, standard_id: int, run_id: int, replace_existing: bool, user_id: int | None = None, revision_note: str | None = None) -> AutomaticOlsGenerationResponse:
        context = await self.repository.runway_context(run_id)
        if context is None: raise OlsNotFoundError("Runway does not exist")
        if not await self.repository.standard_exists(standard_id): raise OlsNotFoundError("Standard does not exist")
        configs = await self.repository.configurations(standard_id)
        if not configs: raise OlsValidationError("The standard has no active OLS surface configuration")
        unsupported = sorted({config["code"] for config in configs} - self.RUN_LEVEL - self.DIRECTION_LEVEL)
        if unsupported: raise OlsValidationError(f"Unsupported automatic OLS surface types: {', '.join(unsupported)}")
        method = await self.repository.automatic_method(); active = await self.repository.active_status()
        if method is None or active is None: raise OlsValidationError("Automatic generation method or Active status is not configured")
        runway, airport = context[0], context[1]
        directions = await self.repository.direction_contexts(run_id)
        if any(config["code"] in self.DIRECTION_LEVEL for config in configs) and not directions: raise OlsValidationError("Runway directions must be configured before generation")
        if any(config["code"] in self.RUN_LEVEL for config in configs) and len(directions) != 2: raise OlsValidationError("Inner Horizontal and Conical generation requires exactly two runway thresholds")
        canonical = lambda code: "TAKE_OFF_CLIMB" if code == "TAKEOFF_CLIMB" else code  # noqa: E731
        surfaces = await self._partitioned_surfaces({canonical(config["code"]): config for config in configs}, context, airport, directions, run_id)
        priority={"INNER_HORIZONTAL":0,"CONICAL":1,"APPROACH":2,"TAKE_OFF_CLIMB":3,"TAKEOFF_CLIMB":3,"TRANSITIONAL":4}
        configs=sorted(configs,key=lambda item:priority.get(item["code"],99))
        generated = []
        for config in configs:
            surface=config["surface"]; code=config["code"]
            targets = [(None, None)] if code in self.RUN_LEVEL else directions
            for direction_row in targets:
                direction = direction_row[0] if direction_row else None
                direction_id=direction.RUN_DIR_ID if direction else None
                computed=surfaces[(canonical(code), direction_id)]
                geom=computed["geometry"]; topology=computed["topology"]
                valid, reason = await self.repository.geometry_is_valid(geom)
                if not valid: raise OlsValidationError(f"Generated {code} geometry is invalid: {reason}")
                item=await self.repository.existing_surface(standard_ols_id=surface.STANDARD_OLS_ID,run_id=run_id,run_dir_id=direction_id,method_id=method.GENERATION_METHOD_ID)
                change_type="AUTOMATIC_REGENERATION" if item is not None else "AUTOMATIC_GENERATION"
                # Archived automatic surfaces are not operationally "existing".
                # Reuse their record to preserve revision continuity and reactivate
                # it without requiring replace_existing=true from the client.
                if item is not None and item.STATUS_ID == active.STATUS_ID and not replace_existing: raise OlsValidationError("Automatic OLS surfaces already exist; set replace_existing=true to regenerate them")
                values={"STANDARD_OLS_ID":surface.STANDARD_OLS_ID,"GENERATION_METHOD_ID":method.GENERATION_METHOD_ID,"AIR_ID":airport.AIR_ID,"RUN_ID":run_id,"RUN_DIR_ID":direction_id,"AZE_NAME":f"{config['aze_name'] or code} - {direction.DESIGNATOR if direction else runway.DESIGNATOR_1+'/'+runway.DESIGNATOR_2}","ENG_NAME":f"{config['eng_name'] or code} - {direction.DESIGNATOR if direction else runway.DESIGNATOR_1+'/'+runway.DESIGNATOR_2}","GEOM":geom,"STATUS_ID":active.STATUS_ID}
                if item is None: item=await self.repository.add_surface(**values)
                else:
                    for column,value in values.items(): setattr(item,column,value)
                    await self.session.flush()
                await self.revisions.create_snapshot(item,change_type=change_type,note=revision_note,user_id=user_id)
                generated.append(GeneratedOlsSurface(ols_surface_id=item.OLS_SURFACE_ID,standard_ols_id=surface.STANDARD_OLS_ID,surface_type=code,run_id=run_id,run_dir_id=direction.RUN_DIR_ID if direction else None,generation_method="AUTOMATIC",**topology))
        await self.session.commit()
        return AutomaticOlsGenerationResponse(air_id=airport.AIR_ID,run_id=run_id,standard_id=standard_id,generated_count=len(generated),surfaces=generated)


class ManualOlsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = OlsRepository(session)
        self.revisions = OlsRevisionRepository(session)

    @staticmethod
    def _response(row: Any) -> OlsSurfaceResponse:
        item = row[0]
        return OlsSurfaceResponse(
            ols_surface_id=item.OLS_SURFACE_ID,
            standard_ols_id=item.STANDARD_OLS_ID,
            standard_id=row.standard_id,
            standard_code=row.standard_code,
            surface_type=row.surface_type,
            generation_method_id=item.GENERATION_METHOD_ID,
            generation_method=row.generation_method,
            air_id=item.AIR_ID,
            run_id=item.RUN_ID,
            run_dir_id=item.RUN_DIR_ID,
            aze_name=item.AZE_NAME,
            eng_name=item.ENG_NAME,
            geometry=__import__("json").loads(row.geojson),
            status_id=item.STATUS_ID,
            status=row.status_name,
            created_date=item.CREATED_DATE,
            last_edited_date=item.LAST_EDITED_DATE,
        )

    async def list_surfaces(self, **filters: Any) -> OlsSurfaceListResponse:
        air_id = int(filters.pop("air_id"))
        if await self.repository.airport(air_id) is None:
            raise OlsNotFoundError("Airport does not exist")
        page = int(filters.pop("page")); page_size = int(filters.pop("page_size"))
        rows, total = await self.repository.list_surfaces(air_id=air_id, offset=(page-1)*page_size, limit=page_size, **filters)
        return OlsSurfaceListResponse(items=[self._response(row) for row in rows], total=total, page=page, page_size=page_size)

    async def get(self, surface_id: int) -> OlsSurfaceResponse:
        row = await self.repository.surface_row(surface_id)
        if row is None: raise OlsNotFoundError("OLS surface does not exist")
        return self._response(row)

    async def feature_collection(self, *, air_id: int, **filters: Any) -> dict[str, Any]:
        result = await self.list_surfaces(
            air_id=air_id,
            page=1,
            page_size=10000,
            **filters,
        )
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": surface.ols_surface_id,
                    "geometry": surface.geometry,
                    "properties": {
                        "ols_surface_id": surface.ols_surface_id,
                        "standard_ols_id": surface.standard_ols_id,
                        "standard_id": surface.standard_id,
                        "standard_code": surface.standard_code,
                        "surface_type": surface.surface_type,
                        "generation_method": surface.generation_method,
                        "air_id": surface.air_id,
                        "run_id": surface.run_id,
                        "run_dir_id": surface.run_dir_id,
                        "aze_name": surface.aze_name,
                        "eng_name": surface.eng_name,
                        "status_id": surface.status_id,
                        "status": surface.status,
                    },
                }
                for surface in result.items
            ],
        }

    async def summary(self, air_id: int) -> OlsSurfaceSummary:
        result = await self.list_surfaces(
            air_id=air_id,
            page=1,
            page_size=10000,
            run_id=None,
            run_dir_id=None,
            generation_method=None,
            status_id=None,
            standard_id=None,
            surface_type=None,
        )
        by_type: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in result.items:
            by_type[item.surface_type] = by_type.get(item.surface_type, 0) + 1
            by_method[item.generation_method] = by_method.get(item.generation_method, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
        return OlsSurfaceSummary(
            air_id=air_id,
            total=result.total,
            by_surface_type=by_type,
            by_generation_method=by_method,
            by_status=by_status,
        )

    async def _validate_links(self, *, standard_ols_id: int, air_id: int, run_id: int | None, run_dir_id: int | None) -> None:
        if await self.repository.standard_surface(standard_ols_id) is None: raise OlsValidationError("Standard OLS surface configuration does not exist")
        if await self.repository.airport(air_id) is None: raise OlsNotFoundError("Airport does not exist")
        runway = await self.repository.runway(run_id) if run_id is not None else None
        if run_id is not None and runway is None: raise OlsNotFoundError("Runway does not exist")
        if runway is not None and runway.AIR_ID != air_id: raise OlsValidationError("Runway does not belong to the selected airport")
        direction = await self.repository.direction(run_dir_id) if run_dir_id is not None else None
        if run_dir_id is not None and direction is None: raise OlsNotFoundError("Runway direction does not exist")
        if direction is not None and (run_id is None or direction.RUN_ID != run_id): raise OlsValidationError("Runway direction does not belong to the selected runway")

    async def create(self, payload: ManualOlsCreate, user_id: int) -> OlsSurfaceResponse:
        await self._validate_links(standard_ols_id=payload.standard_ols_id, air_id=payload.air_id, run_id=payload.run_id, run_dir_id=payload.run_dir_id)
        method=await self.repository.manual_method(); active=await self.repository.active_status()
        if method is None or active is None: raise OlsValidationError("Manual generation method or Active status is not configured")
        item=await self.repository.add_surface(STANDARD_OLS_ID=payload.standard_ols_id,GENERATION_METHOD_ID=method.GENERATION_METHOD_ID,AIR_ID=payload.air_id,RUN_ID=payload.run_id,RUN_DIR_ID=payload.run_dir_id,AZE_NAME=payload.aze_name,ENG_NAME=payload.eng_name,GEOM=self.repository.manual_geometry(payload.geometry.model_dump(),float(payload.default_elevation_m) if payload.default_elevation_m is not None else None),STATUS_ID=active.STATUS_ID)
        await self.revisions.create_snapshot(item,change_type="CREATE",note=payload.revision_note,user_id=user_id)
        await self.session.commit(); return await self.get(item.OLS_SURFACE_ID)

    async def update(self, surface_id: int, changes: dict[str, Any], user_id: int) -> OlsSurfaceResponse:
        item=await self.repository.surface_model(surface_id)
        if item is None: raise OlsNotFoundError("OLS surface does not exist")
        method=await self.repository.manual_method()
        if method is None or item.GENERATION_METHOD_ID != method.GENERATION_METHOD_ID: raise OlsValidationError("Automatically generated surfaces must be regenerated, not edited manually")
        revision_note=changes.pop("revision_note",None); changes.pop("default_elevation_m",None) if changes.get("geometry") is None else None
        standard_ols_id=int(changes.get("standard_ols_id",item.STANDARD_OLS_ID)); run_id=changes.get("run_id",item.RUN_ID); run_dir_id=changes.get("run_dir_id",item.RUN_DIR_ID)
        await self._validate_links(standard_ols_id=standard_ols_id,air_id=item.AIR_ID,run_id=run_id,run_dir_id=run_dir_id)
        for key,column in {"standard_ols_id":"STANDARD_OLS_ID","run_id":"RUN_ID","run_dir_id":"RUN_DIR_ID","aze_name":"AZE_NAME","eng_name":"ENG_NAME"}.items():
            if key in changes: setattr(item,column,changes[key])
        if changes.get("geometry") is not None: item.GEOM=self.repository.manual_geometry(changes["geometry"],float(changes["default_elevation_m"]) if changes.get("default_elevation_m") is not None else None)
        await self.session.flush(); await self.revisions.create_snapshot(item,change_type="UPDATE",note=revision_note,user_id=user_id)
        await self.session.commit(); return await self.get(surface_id)

    async def update_status(self, surface_id: int, status_id: int, user_id: int) -> None:
        item=await self.repository.surface_model(surface_id)
        if item is None: raise OlsNotFoundError("OLS surface does not exist")
        if await self.repository.status(status_id) is None: raise OlsValidationError("Status does not exist")
        item.STATUS_ID=status_id; await self.session.flush(); await self.revisions.create_snapshot(item,change_type="STATUS_CHANGE",note=None,user_id=user_id); await self.session.commit()

    async def archive(self, surface_id: int, user_id: int) -> None:
        item=await self.repository.surface_model(surface_id)
        if item is None: raise OlsNotFoundError("OLS surface does not exist")
        archived=await self.repository.status_by_name("archived")
        if archived is None: raise OlsValidationError("Archived status is not configured")
        item.STATUS_ID=archived.STATUS_ID; await self.session.flush(); await self.revisions.create_snapshot(item,change_type="ARCHIVE",note=None,user_id=user_id); await self.session.commit()
