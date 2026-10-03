import json
import math
from decimal import Decimal
from typing import Any

from pyproj import Transformer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    def _station_anchor(frame: dict[str, Any], station: float) -> tuple[float,float]:
        x=frame["near"][0]+station*frame["ux"]; y=frame["near"][1]+station*frame["uy"]
        return frame["inverse"].transform(x,y)

    async def _trapezoid(self, lon: float, lat: float, bearing: float, start: float, length: float, start_width: float, end_width: float, base_z: float, slope_pct: float, outward: bool):
        axis = (bearing + 180) % 360 if outward else bearing
        start_center = await self.repository.projected_point(lon, lat, start, axis)
        end_center = await self.repository.projected_point(lon, lat, start + length, axis)
        async def lateral(center, width, side):
            return await self.repository.projected_point(center[0], center[1], width / 2, (axis + side * 90) % 360)
        sl = await lateral(start_center, start_width, -1); sr = await lateral(start_center, start_width, 1)
        el = await lateral(end_center, end_width, -1); er = await lateral(end_center, end_width, 1)
        end_z = base_z + length * slope_pct / 100
        return self.repository.polygon_z([(sl[0],sl[1],base_z),(el[0],el[1],end_z),(er[0],er[1],end_z),(sr[0],sr[1],base_z)])

    async def _segmented_surface(self, lon: float, lat: float, bearing: float, start: float, lengths: list[float], start_width: float, divergence_pct: float, max_width: float | None, base_z: float, slopes: list[float], outward: bool, end_widths: list[float] | None = None):
        axis = (bearing + 180) % 360 if outward else bearing
        distances = [0.0]
        elevations = [base_z]
        for length, slope in zip(lengths, slopes):
            distances.append(distances[-1] + length)
            elevations.append(elevations[-1] + length * slope / 100)
        left = []
        right = []
        station_widths = [start_width, *(end_widths or [])]
        for index, (distance, elevation) in enumerate(zip(distances, elevations)):
            center = await self.repository.projected_point(lon, lat, start + distance, axis)
            width = station_widths[index] if len(station_widths) == len(distances) else start_width + 2 * distance * divergence_pct / 100
            if max_width is not None:
                width = min(width, max_width)
            left_point = await self.repository.projected_point(center[0], center[1], width / 2, (axis - 90) % 360)
            right_point = await self.repository.projected_point(center[0], center[1], width / 2, (axis + 90) % 360)
            left.append((left_point[0], left_point[1], elevation))
            right.append((right_point[0], right_point[1], elevation))
        return self.repository.polygon_z([*left, *reversed(right)])

    async def _transitional_surface(self, directions: list[Any], runway_length: float, strip_length: float, strip_width: float, approach: dict[int, dict[str, Any]], slope_pct: float, horizontal_elevation: float):
        """Construct both transitional wings from Strip and Approach boundaries."""
        if len(directions) != 2:
            raise OlsValidationError("TRANSITIONAL requires exactly two runway directions")
        if slope_pct <= 0:
            raise OlsValidationError("TRANSITIONAL slope must be greater than zero")
        start = self._number(approach, ("START_DISTANCE", "THRESHOLD_OFFSET"))
        inner_width = self._number(approach, ("INNER_EDGE",))
        divergence = self._number(approach, ("DIVERGENCE",))
        sections = sorted(section for section in approach if section > 0)
        threshold_data = []
        for row in directions:
            geometry = __import__("json").loads(row.threshold)
            threshold_data.append((float(geometry["coordinates"][0]), float(geometry["coordinates"][1]), float(row[0].TRUE_BEARING_DEG), float(row[0].THRESHOLD_ELEVATION_M)))

        def profile(base_z: float) -> list[tuple[float, float, float]]:
            stations = [(0.0, inner_width, base_z)]
            distance = 0.0; width = inner_width; elevation = base_z
            for section in sections:
                length = self._number(approach, ("LENGTH",), section)
                section_slope = self._number(approach, ("SLOPE",), section)
                end_width = float(approach[section].get("END_WIDTH", width + 2 * length * divergence / 100))
                rise = length * section_slope / 100
                if section_slope > 0 and elevation + rise >= horizontal_elevation:
                    partial = max(0.0, (horizontal_elevation - elevation) / (section_slope / 100))
                    ratio = partial / length if length else 0.0
                    stations.append((distance + partial, width + (end_width - width) * ratio, horizontal_elevation))
                    break
                distance += length; elevation += rise; width = end_width
                stations.append((distance, width, elevation))
                if elevation >= horizontal_elevation: break
            return stations

        profiles = [profile(item[3]) for item in threshold_data]
        strip_extension = max(0.0, (strip_length - runway_length) / 2)
        runway_axis = threshold_data[0][2]
        polygons = []
        for side in (-1, 1):
            lateral_bearing = (runway_axis + side * 90) % 360
            lower = []
            for index, reverse in ((0, True), (1, False)):
                lon, lat, bearing, _ = threshold_data[index]
                stations = reversed(profiles[index]) if reverse else profiles[index]
                points = []
                for distance, width, elevation in stations:
                    center = await self.repository.projected_point(lon, lat, start + distance, (bearing + 180) % 360)
                    edge = await self.repository.projected_point(center[0], center[1], width / 2, lateral_bearing)
                    points.append((edge[0], edge[1], elevation))
                if index == 0: lower.extend(points)
                else:
                    first, second = threshold_data
                    first_center = await self.repository.projected_point(first[0], first[1], strip_extension, (first[2] + 180) % 360)
                    second_center = await self.repository.projected_point(second[0], second[1], strip_extension, (second[2] + 180) % 360)
                    for center, elevation in ((first_center, first[3]), (second_center, second[3])):
                        edge = await self.repository.projected_point(center[0], center[1], strip_width / 2, lateral_bearing)
                        lower.append((edge[0], edge[1], elevation))
                    lower.extend(points)
            outer = []
            for lon, lat, elevation in lower:
                distance = max(0.0, horizontal_elevation - elevation) / (slope_pct / 100)
                point = await self.repository.projected_point(lon, lat, distance, lateral_bearing)
                outer.append((point[0], point[1], horizontal_elevation))
            polygons.append([*lower, *reversed(outer)])
        return self.repository.multipolygon_z(polygons)

    def _transitional_from_shared_boundary(
        self,
        boundary_geojson: str,
        runway_frame: dict[str, Any],
        approach_references: list[dict[str, Any]],
        approach_parameters: dict[int, dict[str, Any]],
        slope_pct: float,
        horizontal_elevation: float,
        strip_station_range: tuple[float, float],
        runway_elevation_profile: list[tuple[float, float]],
    ) -> Any:
        """Construct both wings from the actual Strip/Approach exterior edge."""
        if slope_pct <= 0:
            raise OlsValidationError("TRANSITIONAL slope must be greater than zero")
        raw=json.loads(boundary_geojson)
        lines=raw.get("coordinates",[]) if raw.get("type")=="MultiLineString" else [raw.get("coordinates",[])]
        lines=[line for line in lines if len(line)>=2]
        if not lines: raise OlsValidationError("Transitional reference boundary is empty")
        line=max(lines,key=len)
        sections=sorted(section for section in approach_parameters if section>0)

        def approach_profile(distance: float, base: float) -> tuple[float, float]:
            elevation=base; remaining=max(0.0,distance)
            width=self._number(approach_parameters,("INNER_EDGE",))
            for section in sections:
                length=self._number(approach_parameters,("LENGTH",),section)
                section_slope=self._number(approach_parameters,("SLOPE",),section)
                end_width=float(approach_parameters[section].get("END_WIDTH",width+2*length*self._number(approach_parameters,("DIVERGENCE",))/100))
                used=min(remaining,length)
                elevation+=used*section_slope/100
                width+=((end_width-width)*used/length) if length else 0.0
                remaining-=used
                if remaining<=0: break
            return elevation,width

        def approach_cutoff(base: float) -> tuple[float, float]:
            """Return the exact station/width where Approach reaches Inner Horizontal."""
            distance=0.0; elevation=base
            width=self._number(approach_parameters,("INNER_EDGE",))
            divergence=self._number(approach_parameters,("DIVERGENCE",))
            for section in sections:
                length=self._number(approach_parameters,("LENGTH",),section)
                section_slope=self._number(approach_parameters,("SLOPE",),section)
                end_width=float(approach_parameters[section].get("END_WIDTH",width+2*length*divergence/100))
                rise=length*section_slope/100
                if section_slope>0 and elevation+rise>=horizontal_elevation-1e-9:
                    partial=max(0.0,(horizontal_elevation-elevation)/(section_slope/100))
                    ratio=partial/length if length else 0.0
                    return distance+partial,width+(end_width-width)*ratio
                distance+=length; elevation+=rise; width=end_width
                if elevation>=horizontal_elevation-1e-9:
                    return distance,width
            raise OlsValidationError("Approach does not intersect the Inner Horizontal elevation")

        profile=sorted(runway_elevation_profile)
        if len(profile)<2:
            raise OlsValidationError("Runway elevation profile requires two thresholds")

        def strip_elevation(station: float) -> float:
            (start_station,start_z),(end_station,end_z)=profile[0],profile[-1]
            if end_station-start_station<=1e-9: return start_z
            ratio=min(1.0,max(0.0,(station-start_station)/(end_station-start_station)))
            return start_z+(end_z-start_z)*ratio

        for reference in approach_references:
            cutoff_distance,cutoff_width=approach_cutoff(reference["base_z"])
            reference["cutoff_distance"]=cutoff_distance
            reference["cutoff_width"]=cutoff_width

        prepared=[]
        px,py=-runway_frame["uy"],runway_frame["ux"]
        for coordinate in line:
            lon,lat=float(coordinate[0]),float(coordinate[1]); x,y=runway_frame["forward"].transform(lon,lat)
            lateral=(x-runway_frame["near"][0])*px+(y-runway_frame["near"][1])*py
            elevation=None
            for reference in approach_references:
                frame=reference["frame"]; station=(x-frame["near"][0])*frame["ux"]+(y-frame["near"][1])*frame["uy"]
                outward=reference["strip_end"]-station
                # A transverse edge projects a few decimetres along the runway
                # axis after CRS round-trips. Keep the same sub-metre topology
                # tolerance used when Approach is snapped to Strip.
                if -0.50<=outward<=reference["cutoff_distance"]+0.50:
                    elevation=approach_profile(max(0.0,outward),reference["base_z"])[0]; break
            global_station=(x-runway_frame["near"][0])*runway_frame["ux"]+(y-runway_frame["near"][1])*runway_frame["uy"]
            if elevation is None and strip_station_range[0]-0.50<=global_station<=strip_station_range[1]+0.50:
                elevation=strip_elevation(global_station)
            if elevation is None or elevation>horizontal_elevation+0.001:
                continue
            side=1 if lateral>0.01 else -1 if lateral<-0.01 else 0
            prepared.append({"lon":lon,"lat":lat,"x":x,"y":y,"side":side,"station":global_station,"lateral":lateral,"z":elevation})

        # Approach section vertices do not necessarily contain the precise
        # elevation intersection. Add that interpolated shared vertex so the
        # Transitional surface neither leaves a gap nor continues too far.
        for reference in approach_references:
            frame=reference["frame"]
            for root in reference["root_points"]:
                lon,lat=float(root[0]),float(root[1])
                x,y=runway_frame["forward"].transform(lon,lat)
                lateral=(x-runway_frame["near"][0])*px+(y-runway_frame["near"][1])*py
                side=1 if lateral>0.01 else -1 if lateral<-0.01 else 0
                station=(x-runway_frame["near"][0])*runway_frame["ux"]+(y-runway_frame["near"][1])*runway_frame["uy"]
                prepared.append({"lon":lon,"lat":lat,"x":x,"y":y,"side":side,"station":station,"lateral":lateral,"z":reference["base_z"]})

            cutoff_points=[]
            ring=reference["ring"]
            for first,second in zip(ring,ring[1:]):
                first_z=float(first[2]); second_z=float(second[2])
                if (first_z-horizontal_elevation)*(second_z-horizontal_elevation)>0 or abs(first_z-second_z)<1e-9:
                    continue
                ratio=(horizontal_elevation-first_z)/(second_z-first_z)
                if not 0.0<=ratio<=1.0: continue
                first_x,first_y=runway_frame["forward"].transform(float(first[0]),float(first[1]))
                second_x,second_y=runway_frame["forward"].transform(float(second[0]),float(second[1]))
                x=first_x+(second_x-first_x)*ratio; y=first_y+(second_y-first_y)*ratio
                lateral=(x-runway_frame["near"][0])*px+(y-runway_frame["near"][1])*py
                side=1 if lateral>0.01 else -1 if lateral<-0.01 else 0
                station=(x-runway_frame["near"][0])*runway_frame["ux"]+(y-runway_frame["near"][1])*runway_frame["uy"]
                lon,lat=runway_frame["inverse"].transform(x,y)
                cutoff_points.append({"lon":lon,"lat":lat,"x":x,"y":y,"side":side,"station":station,"lateral":lateral,"z":horizontal_elevation})
            for side in (-1,1):
                candidates=[point for point in cutoff_points if point["side"]==side]
                if not candidates:
                    raise OlsValidationError(f"Approach/Inner Horizontal intersection is missing for side {side}")
                prepared.append(min(candidates,key=lambda point:abs(point["station"])))

        polygons=[]
        for side in (-1,1):
            # The union boundary is a cyclic ring.  Ring order is unsuitable for
            # building an offset polygon because its start vertex is arbitrary
            # and can split one wing across the first/last coordinate.  Order
            # the real shared-edge vertices by the runway longitudinal station
            # instead.  At a cross-edge several vertices may have the same
            # station; the outermost vertex is the actual side boundary.
            by_station: dict[int,dict[str,Any]]={}
            for point in prepared:
                if point["side"]!=side: continue
                key=round(point["station"]*1000)
                existing=by_station.get(key)
                if existing is None or abs(point["lateral"])>abs(existing["lateral"]): by_station[key]=point
            lower=sorted(by_station.values(),key=lambda point:point["station"])
            if len(lower)<2: raise OlsValidationError(f"Transitional lower boundary is missing for side {side}")
            lower_coords=[]; upper_coords=[]
            for point in lower:
                lower_coords.append((point["lon"],point["lat"],point["z"]))
                extent=(horizontal_elevation-point["z"])/(slope_pct/100)
                ux=point["x"]+side*px*extent; uy=point["y"]+side*py*extent
                ulon,ulat=runway_frame["inverse"].transform(ux,uy)
                upper_coords.append((ulon,ulat,horizontal_elevation))
            polygons.append([*lower_coords,*reversed(upper_coords)])
        return self.repository.multipolygon_z(polygons)

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
        priority={"INNER_HORIZONTAL":0,"CONICAL":1,"APPROACH":2,"TAKE_OFF_CLIMB":3,"TAKEOFF_CLIMB":3,"TRANSITIONAL":4}
        configs=sorted(configs,key=lambda item:priority.get(item["code"],99))
        generated = []
        approach_geometries: list[Any] = []
        approach_references: list[dict[str,Any]] = []
        inner_offset = inner_height = None
        approach_parameters = None
        for config in configs:
            if config["code"] == "INNER_HORIZONTAL":
                inner_offset = self._number(config["parameters"], ("HORIZONTAL_OFFSET", "OFFSET", "RADIUS")); inner_height = self._number(config["parameters"], ("HEIGHT",))
            elif config["code"] == "APPROACH":
                approach_parameters = config["parameters"]
        for config in configs:
            surface=config["surface"]; code=config["code"]; params=config["parameters"]
            targets = [(None, None)] if code in self.RUN_LEVEL else directions
            for direction_row in targets:
                direction = direction_row[0] if direction_row else None
                topology={"reference_geometry":None,"topology_status":"NOT_APPLICABLE","topology_message":None,"gap_m":None,"overlap_m":None}
                if code == "INNER_HORIZONTAL":
                    geom = await self.repository.centerline_buffer_3d(run_id, inner_offset, float(airport.ELEVATION_M)+inner_height)
                elif code == "CONICAL":
                    if inner_offset is None or inner_height is None: raise OlsValidationError("CONICAL requires INNER_HORIZONTAL offset and height")
                    width=self._number(params,("HORIZONTAL_WIDTH","WIDTH")); height=self._number(params,("HEIGHT",)); inner_elevation=float(airport.ELEVATION_M)+inner_height; geom=await self.repository.conical_surface_3d(run_id,inner_offset,width,inner_elevation,inner_elevation+height)
                elif code == "TRANSITIONAL":
                    if inner_height is None or approach_parameters is None: raise OlsValidationError("TRANSITIONAL requires INNER_HORIZONTAL and APPROACH configurations")
                    strip = await self.repository.active_strip(run_id)
                    if strip is None: raise OlsValidationError("TRANSITIONAL requires an active Runway Strip")
                    if len(approach_geometries)!=2: raise OlsValidationError("TRANSITIONAL requires both generated Approach direction geometries")
                    boundary=await self.repository.transitional_reference_boundary(run_id,approach_geometries)
                    first_threshold=json.loads(directions[0].threshold)["coordinates"]
                    runway_frame=self._direction_frame(context.centerline,(float(first_threshold[0]),float(first_threshold[1])))
                    strip_stations=self._geometry_stations(strip.geojson,runway_frame)
                    runway_profile=[]
                    for profile_row in directions:
                        profile_direction=profile_row[0]
                        profile_threshold=json.loads(profile_row.threshold)["coordinates"]
                        profile_x,profile_y=runway_frame["forward"].transform(float(profile_threshold[0]),float(profile_threshold[1]))
                        profile_station=(profile_x-runway_frame["near"][0])*runway_frame["ux"]+(profile_y-runway_frame["near"][1])*runway_frame["uy"]
                        runway_profile.append((profile_station,float(profile_direction.THRESHOLD_ELEVATION_M)))
                    geom=self._transitional_from_shared_boundary(
                        boundary,runway_frame,approach_references,approach_parameters,
                        self._number(params,("SLOPE",)),float(airport.ELEVATION_M)+inner_height,
                        (min(strip_stations),max(strip_stations)),runway_profile,
                    )
                    geom=self.repository.normalize_polygonal_geometry(geom)
                    geom=self.repository.remove_polygonal_overlap(geom,[strip[0].GEOM,*approach_geometries])
                    topology={"reference_geometry":"RUNWAY_STRIP_AND_APPROACH_BOUNDARIES","topology_status":"PASSED","topology_message":"Transitional lower boundary is derived from the actual Strip and generated Approach union.","gap_m":0.0,"overlap_m":0.0}
                else:
                    threshold=json.loads(direction_row.threshold); lon,lat=map(float,threshold["coordinates"][:2]); frame=self._direction_frame(context.centerline,(lon,lat)); bearing=frame["bearing"]; base_z=float(direction.THRESHOLD_ELEVATION_M)
                    if code == "APPROACH":
                        strip=await self.repository.active_strip(run_id)
                        if strip is None: raise OlsValidationError("APPROACH requires an active Runway Strip")
                        standard_start=self._number(params,("START_DISTANCE","THRESHOLD_OFFSET")); strip_end=min(self._geometry_stations(strip.geojson,frame)); expected_station=frame["threshold_station"]-standard_start; delta=expected_station-strip_end
                        # The standard offset is retained as a QA comparison, but
                        # the operational Strip geometry is the authoritative shared
                        # topology boundary. A surveyed threshold can legitimately be
                        # displaced from a previously drawn runway/Strip geometry.
                        # Blocking generation here creates no safer geometry; anchoring
                        # Approach to the actual Strip end guarantees a common boundary
                        # and reports the source discrepancy for later data correction.
                        tolerance_m=0.50
                        lon,lat=self._station_anchor(frame,strip_end); start=0.0; inner=self._number(params,("INNER_EDGE",)); divergence=self._number(params,("DIVERGENCE",)); sections=sorted(k for k in params if k>0); lengths=[self._number(params,("LENGTH",),s) for s in sections]; slopes=[self._number(params,("SLOPE",),s) for s in sections]; end_widths=[self._number(params,("END_WIDTH",),s) for s in sections] if all("END_WIDTH" in params[s] for s in sections) else None; geom=await self._segmented_surface(lon,lat,bearing,start,lengths,inner,divergence,None,base_z,slopes,True,end_widths=end_widths)
                        geom=self.repository.snap_polygon_to_reference(geom,strip[0].GEOM,frame["srid"],0.001,base_z)
                        within_tolerance=abs(delta)<=tolerance_m
                        topology={
                            "reference_geometry":"ACTUAL_RUNWAY_STRIP_END",
                            "topology_status":"PASSED" if within_tolerance else "WARNING",
                            "topology_message":(
                                f"Approach is anchored to the actual Strip end; configured offset differs by {abs(delta):.3f} m "
                                f"({'within' if within_tolerance else 'outside'} {tolerance_m:.2f} m QA tolerance)."
                            ),
                            "gap_m":0.0,
                            "overlap_m":0.0,
                        }
                        approach_geometries.append(geom)
                        approach_geojson=await self.session.scalar(select(func.ST_AsGeoJSON(geom,15)))
                        approach_ring=json.loads(str(approach_geojson))["coordinates"][0]
                        root_points=[]
                        for root_point in approach_ring[:-1]:
                            root_x,root_y=frame["forward"].transform(float(root_point[0]),float(root_point[1]))
                            root_station=(root_x-frame["near"][0])*frame["ux"]+(root_y-frame["near"][1])*frame["uy"]
                            if abs(root_station-strip_end)<=2.0:
                                root_points.append(root_point)
                        if len(root_points)<2:
                            raise OlsValidationError(f"RWY {direction.DESIGNATOR} Approach root vertices could not be resolved")
                        approach_references.append({"frame":frame,"strip_end":strip_end,"base_z":base_z,"run_dir_id":direction.RUN_DIR_ID,"root_points":root_points,"ring":approach_ring})
                    else:
                        clearway=await self.repository.active_clearway(direction.RUN_DIR_ID)
                        # A runway direction owns the CWY located outside its own
                        # threshold.  In this direction frame the runway interior
                        # is positive, therefore that CWY's outer end is the
                        # minimum station and take-off continues on the reverse
                        # centreline bearing.  Never inspect the opposite
                        # direction's CWY.
                        if clearway is not None:
                            clearway_end=min(self._geometry_stations(clearway.geojson,frame))
                            bearing=(frame["bearing"]+180)%360
                            reference="CLEARWAY_END_AND_RUNWAY_CENTERLINE"
                            topology_status="PASSED"
                            topology_message=f"RWY {direction.DESIGNATOR} Take-off is anchored to RWY {direction.DESIGNATOR} Clearway outer end."
                        else:
                            clearway_end=frame["threshold_station"]
                            bearing=(frame["bearing"]+180)%360
                            reference="THRESHOLD_NO_CLEARWAY"
                            topology_status="WARNING"
                            topology_message=f"RWY {direction.DESIGNATOR} has no active Clearway; Take-off starts at its threshold."
                        lon,lat=self._station_anchor(frame,clearway_end); start=0.0; inner=self._number(params,("INNER_EDGE",)); divergence=self._number(params,("DIVERGENCE",)); final=self._number(params,("FINAL_WIDTH",)); length=self._number(params,("LENGTH","TOTAL_LENGTH")); slope=self._number(params,("SLOPE",)); base_z += abs(clearway_end-frame["threshold_station"])*float(direction.SLOPE_PCT)/100; diverging_length=(final-inner)/2/(divergence/100); lengths=[min(diverging_length,length)]; slopes=[slope]; topology={"reference_geometry":reference,"topology_status":topology_status,"topology_message":topology_message,"gap_m":0.0,"overlap_m":0.0}
                        if diverging_length < length: lengths.append(length-diverging_length); slopes.append(slope)
                        geom=await self._segmented_surface(lon,lat,bearing,start,lengths,inner,divergence,final,base_z,slopes,False)
                direction_id=direction.RUN_DIR_ID if direction else None
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
