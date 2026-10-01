from decimal import Decimal
from typing import Any

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
        generated = []
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
                if code == "INNER_HORIZONTAL":
                    geom = await self.repository.centerline_buffer_3d(run_id, inner_offset, float(airport.ELEVATION_M)+inner_height)
                elif code == "CONICAL":
                    if inner_offset is None or inner_height is None: raise OlsValidationError("CONICAL requires INNER_HORIZONTAL offset and height")
                    width=self._number(params,("HORIZONTAL_WIDTH","WIDTH")); height=self._number(params,("HEIGHT",)); inner_elevation=float(airport.ELEVATION_M)+inner_height; geom=await self.repository.conical_surface_3d(run_id,inner_offset,width,inner_elevation,inner_elevation+height)
                elif code == "TRANSITIONAL":
                    if inner_height is None or approach_parameters is None: raise OlsValidationError("TRANSITIONAL requires INNER_HORIZONTAL and APPROACH configurations")
                    strip = await self.repository.active_strip(run_id)
                    if strip is None: raise OlsValidationError("TRANSITIONAL requires an active Runway Strip")
                    geom = await self._transitional_surface(directions, float(runway.LENGTH_M), float(strip[0].LENGTH_M), float(strip[0].WIDTH_M), approach_parameters, self._number(params,("SLOPE",)), float(airport.ELEVATION_M)+inner_height)
                else:
                    threshold=__import__("json").loads(direction_row.threshold); lon,lat=threshold["coordinates"][:2]; bearing=float(direction.TRUE_BEARING_DEG); base_z=float(direction.THRESHOLD_ELEVATION_M)
                    if code == "APPROACH":
                        start=self._number(params,("START_DISTANCE","THRESHOLD_OFFSET")); inner=self._number(params,("INNER_EDGE",)); divergence=self._number(params,("DIVERGENCE",)); sections=sorted(k for k in params if k>0); lengths=[self._number(params,("LENGTH",),s) for s in sections]; slopes=[self._number(params,("SLOPE",),s) for s in sections]; end_widths=[self._number(params,("END_WIDTH",),s) for s in sections] if all("END_WIDTH" in params[s] for s in sections) else None; geom=await self._segmented_surface(lon,lat,bearing,start,lengths,inner,divergence,None,base_z,slopes,True,end_widths=end_widths)
                    else:
                        clearway=await self.repository.active_clearway(direction.RUN_DIR_ID); clearway_length=float(clearway[0].LENGTH_M) if clearway is not None else 0.0; start=float(runway.LENGTH_M)+clearway_length; inner=self._number(params,("INNER_EDGE",)); divergence=self._number(params,("DIVERGENCE",)); final=self._number(params,("FINAL_WIDTH",)); length=self._number(params,("LENGTH","TOTAL_LENGTH")); slope=self._number(params,("SLOPE",)); base_z += start * float(direction.SLOPE_PCT) / 100; diverging_length=(final-inner)/2/(divergence/100); lengths=[min(diverging_length,length)]; slopes=[slope];
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
                generated.append(GeneratedOlsSurface(ols_surface_id=item.OLS_SURFACE_ID,standard_ols_id=surface.STANDARD_OLS_ID,surface_type=code,run_id=run_id,run_dir_id=direction.RUN_DIR_ID if direction else None,generation_method="AUTOMATIC"))
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
