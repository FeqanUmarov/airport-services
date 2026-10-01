import json
import math
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pyproj import Transformer

from app.modules.runways.models import Runway, RunwayArea, RunwayDirection, RunwayStrip
from app.modules.runways.repository import RunwayRepository
from app.modules.runways.schemas import (
    AreaCreate,
    AreaResponse,
    DirectionCreate,
    DirectionResponse,
    RunwayCreate,
    RunwayListResponse,
    RunwayResponse,
    ClearwayGenerateRequest,
    StripResponse,
    StripGenerateRequest,
    StripUpsert,
)


class RunwayNotFoundError(ValueError): pass
class RunwayConflictError(ValueError): pass
class RunwayValidationError(ValueError): pass


class RunwayService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = RunwayRepository(session)

    async def _active_id(self) -> int:
        status = await self.repository.active_status()
        if status is None:
            raise RunwayValidationError("Active status is not configured")
        return status.STATUS_ID

    @staticmethod
    def _bearing(start: tuple[float, float], end: tuple[float, float]) -> Decimal:
        lon1, lat1 = start
        lon2, lat2 = end
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        y = math.sin(delta_lon) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
        return Decimal(str(round((math.degrees(math.atan2(y, x)) + 360) % 360, 4)))

    @staticmethod
    def _designator_bearing(designator: str) -> float:
        match = re.match(r"(\d{1,2})", designator.strip())
        if match is None:
            raise RunwayValidationError(f"Cannot derive bearing from runway designator {designator}")
        return (int(match.group(1)) * 10) % 360

    @staticmethod
    def _bearing_difference(first: float, second: float) -> float:
        return abs(((first - second + 540) % 360) - 180)

    @classmethod
    def _automatic_direction_specs(
        cls,
        centerline: list[tuple[float, float]] | list[list[float]],
        designators: tuple[str, str],
        fallback_elevation: Decimal,
    ) -> list[dict[str, Any]]:
        if len(centerline) < 2:
            raise RunwayValidationError("Runway centerline requires at least two coordinates")
        first = (float(centerline[0][0]), float(centerline[0][1]))
        last = (float(centerline[-1][0]), float(centerline[-1][1]))
        forward = float(cls._bearing(first, last))
        specs: list[dict[str, Any]] = []
        for designator in designators:
            target = cls._designator_bearing(designator)
            use_forward = cls._bearing_difference(forward, target) <= cls._bearing_difference((forward + 180) % 360, target)
            threshold = first if use_forward else last
            bearing = Decimal(str(round(forward if use_forward else (forward + 180) % 360, 4)))
            specs.append({
                "designator": designator,
                "true_bearing_deg": bearing,
                "threshold_elevation_m": fallback_elevation,
                "threshold_geom": {"type": "Point", "coordinates": [threshold[0], threshold[1]]},
                "slope_pct": Decimal("0"),
            })
        return specs

    @staticmethod
    def _end_area_polygon(
        threshold: list[float] | tuple[float, float],
        runway_bearing: Decimal,
        length_m: Decimal,
        width_m: Decimal,
        start_offset_m: Decimal = Decimal("60"),
    ) -> dict[str, Any]:
        lon, lat = float(threshold[0]), float(threshold[1])
        zone = int((lon + 180) // 6) + 1
        epsg = 32600 + zone if lat >= 0 else 32700 + zone
        to_metric = Transformer.from_crs(4326, epsg, always_xy=True)
        to_wgs84 = Transformer.from_crs(epsg, 4326, always_xy=True)
        x, y = to_metric.transform(lon, lat)
        outward = math.radians((float(runway_bearing) + 180) % 360)
        along_x, along_y = math.sin(outward), math.cos(outward)
        side_x, side_y = math.cos(outward), -math.sin(outward)
        start = float(start_offset_m)
        end = start + float(length_m)
        half_width = float(width_m) / 2
        metric_points = [
            (x + along_x * start + side_x * half_width, y + along_y * start + side_y * half_width),
            (x + along_x * end + side_x * half_width, y + along_y * end + side_y * half_width),
            (x + along_x * end - side_x * half_width, y + along_y * end - side_y * half_width),
            (x + along_x * start - side_x * half_width, y + along_y * start - side_y * half_width),
        ]
        coordinates = [list(to_wgs84.transform(px, py)) for px, py in metric_points]
        coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}

    @staticmethod
    def _centered_parallel_polygon(
        centerline: list[list[float]] | list[tuple[float, float]],
        length_m: Decimal,
        width_m: Decimal,
    ) -> dict[str, Any]:
        """Build a rectangle whose long edges are parallel to the runway centerline."""
        first, last = centerline[0], centerline[-1]
        center_lon = (float(first[0]) + float(last[0])) / 2
        center_lat = (float(first[1]) + float(last[1])) / 2
        zone = int((center_lon + 180) // 6) + 1
        epsg = 32600 + zone if center_lat >= 0 else 32700 + zone
        to_metric = Transformer.from_crs(4326, epsg, always_xy=True)
        to_wgs84 = Transformer.from_crs(epsg, 4326, always_xy=True)
        first_x, first_y = to_metric.transform(float(first[0]), float(first[1]))
        last_x, last_y = to_metric.transform(float(last[0]), float(last[1]))
        delta_x, delta_y = last_x - first_x, last_y - first_y
        centerline_length = math.hypot(delta_x, delta_y)
        if centerline_length == 0:
            raise RunwayValidationError("Runway centerline endpoints must be different")

        along_x, along_y = delta_x / centerline_length, delta_y / centerline_length
        side_x, side_y = -along_y, along_x
        center_x, center_y = (first_x + last_x) / 2, (first_y + last_y) / 2
        half_length, half_width = float(length_m) / 2, float(width_m) / 2
        metric_points = [
            (center_x - along_x * half_length + side_x * half_width, center_y - along_y * half_length + side_y * half_width),
            (center_x + along_x * half_length + side_x * half_width, center_y + along_y * half_length + side_y * half_width),
            (center_x + along_x * half_length - side_x * half_width, center_y + along_y * half_length - side_y * half_width),
            (center_x - along_x * half_length - side_x * half_width, center_y - along_y * half_length - side_y * half_width),
        ]
        coordinates = [list(to_wgs84.transform(x, y)) for x, y in metric_points]
        coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}

    @staticmethod
    def _runway_response(row: Any) -> RunwayResponse:
        item = row[0]
        return RunwayResponse(run_id=item.RUN_ID, air_id=item.AIR_ID, airport_name=row.airport_name, aze_name=item.AZE_NAME, eng_name=item.ENG_NAME, designator_1=item.DESIGNATOR_1, designator_2=item.DESIGNATOR_2, length_m=item.LENGTH_M, width_m=item.WIDTH_M, geom=json.loads(row.geojson), centerline_geom=json.loads(row.centerline_geojson), status_id=item.STATUS_ID, status=row.status_name, created_date=item.CREATED_DATE, last_edited_date=item.LAST_EDITED_DATE)

    @staticmethod
    def _direction_response(row: Any) -> DirectionResponse:
        item = row[0]
        return DirectionResponse(run_dir_id=item.RUN_DIR_ID, run_id=item.RUN_ID, designator=item.DESIGNATOR, true_bearing_deg=item.TRUE_BEARING_DEG, threshold_elevation_m=item.THRESHOLD_ELEVATION_M, threshold_geom=json.loads(row.geojson), slope_pct=item.SLOPE_PCT, status_id=item.STATUS_ID, status=row.status_name, created_date=item.CREATED_DATE, last_edited_date=item.LAST_EDITED_DATE)

    @staticmethod
    def _strip_response(row: Any) -> StripResponse:
        item = row[0]
        return StripResponse(strip_id=item.STRIP_ID, run_id=item.RUN_ID, length_m=item.LENGTH_M, width_m=item.WIDTH_M, geom=json.loads(row.geojson), status_id=item.STATUS_ID, status=row.status_name, created_date=item.CREATED_DATE, last_edited_date=item.LAST_EDITED_DATE)

    @staticmethod
    def _area_response(row: Any) -> AreaResponse:
        item = row[0]
        return AreaResponse(runway_area_id=item.RUNWAY_AREA_ID, run_id=item.RUN_ID, run_dir_id=item.RUN_DIR_ID, area_type_id=item.AREA_TYPE_ID, area_type_code=row.area_type_code, length_m=item.LENGTH_M, width_m=item.WIDTH_M, geom=json.loads(row.geojson), status_id=item.STATUS_ID, status=row.status_name, created_date=item.CREATED_DATE, last_edited_date=item.LAST_EDITED_DATE)

    async def list_runways(self, air_id: int, search: str | None, status_id: int | None) -> RunwayListResponse:
        if not await self.repository.airport_exists(air_id):
            raise RunwayNotFoundError("Airport does not exist")
        rows = await self.repository.list_runways(air_id, search, status_id)
        return RunwayListResponse(items=[self._runway_response(row) for row in rows], total=len(rows))

    async def get_runway(self, run_id: int) -> RunwayResponse:
        row = await self.repository.runway_row(run_id)
        if row is None: raise RunwayNotFoundError("Runway does not exist")
        return self._runway_response(row)

    async def create_runway(self, air_id: int, data: RunwayCreate) -> RunwayResponse:
        airport = await self.repository.airport(air_id)
        if airport is None: raise RunwayNotFoundError("Airport does not exist")
        if await self.repository.duplicate_runway(air_id, data.designator_1, data.designator_2): raise RunwayConflictError("Runway designator pair already exists at this airport")
        active_id = await self._active_id()
        item = Runway(AIR_ID=air_id, AZE_NAME=data.aze_name, ENG_NAME=data.eng_name, DESIGNATOR_1=data.designator_1, DESIGNATOR_2=data.designator_2, LENGTH_M=data.length_m, WIDTH_M=data.width_m, GEOM=self.repository.geometry(data.geom.model_dump()), CENTERLINE_GEOM=self.repository.geometry(data.centerline_geom.model_dump()), STATUS_ID=active_id)
        self.session.add(item)
        await self.session.flush()
        specs = self._automatic_direction_specs(data.centerline_geom.coordinates, (data.designator_1, data.designator_2), airport.ELEVATION_M)
        directions = [RunwayDirection(RUN_ID=item.RUN_ID, DESIGNATOR=spec["designator"], TRUE_BEARING_DEG=spec["true_bearing_deg"], THRESHOLD_ELEVATION_M=spec["threshold_elevation_m"], THRESHOLD_GEOM=self.repository.geometry(spec["threshold_geom"]), SLOPE_PCT=spec["slope_pct"], STATUS_ID=active_id) for spec in specs]
        self.session.add_all(directions)
        await self.session.commit()
        return await self.get_runway(item.RUN_ID)

    async def update_runway(self, run_id: int, changes: dict[str, Any]) -> RunwayResponse:
        item = await self.repository.runway(run_id)
        if item is None: raise RunwayNotFoundError("Runway does not exist")
        d1, d2 = str(changes.get("designator_1", item.DESIGNATOR_1)), str(changes.get("designator_2", item.DESIGNATOR_2))
        if ("designator_1" in changes or "designator_2" in changes) and await self.repository.duplicate_runway(item.AIR_ID, d1, d2, run_id): raise RunwayConflictError("Runway designator pair already exists at this airport")
        for key, column in {"aze_name":"AZE_NAME","eng_name":"ENG_NAME","designator_1":"DESIGNATOR_1","designator_2":"DESIGNATOR_2","length_m":"LENGTH_M","width_m":"WIDTH_M"}.items():
            if key in changes: setattr(item, column, changes[key])
        if changes.get("geom") is not None: item.GEOM = self.repository.geometry(changes["geom"])
        if changes.get("centerline_geom") is not None: item.CENTERLINE_GEOM = self.repository.geometry(changes["centerline_geom"])
        await self.session.commit(); return await self.get_runway(run_id)

    async def set_status(self, kind: str, item_id: int, status_id: int) -> None:
        item = await self._model(kind, item_id)
        if await self.repository.status(status_id) is None: raise RunwayValidationError("Status does not exist")
        item.STATUS_ID = status_id; await self.session.commit()

    async def archive(self, kind: str, item_id: int) -> None:
        item = await self._model(kind, item_id)
        archived = await self.repository.status_by_name("archived")
        if archived is None: raise RunwayValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID; await self.session.commit()

    async def set_strip_status(self, run_id: int, status_id: int) -> None:
        item = await self.repository.strip(run_id)
        if item is None:
            raise RunwayNotFoundError("Runway strip does not exist")
        if await self.repository.status(status_id) is None:
            raise RunwayValidationError("Status does not exist")
        item.STATUS_ID = status_id
        await self.session.commit()

    async def archive_strip(self, run_id: int) -> None:
        item = await self.repository.strip(run_id)
        if item is None:
            raise RunwayNotFoundError("Runway strip does not exist")
        archived = await self.repository.status_by_name("archived")
        if archived is None:
            raise RunwayValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID
        await self.session.commit()

    async def _model(self, kind: str, item_id: int):
        item = await ({"runway": self.repository.runway, "direction": self.repository.direction, "area": self.repository.area}[kind])(item_id)
        if item is None: raise RunwayNotFoundError(f"{kind.title()} does not exist")
        return item

    async def list_directions(self, run_id: int) -> list[DirectionResponse]:
        if await self.repository.runway(run_id) is None: raise RunwayNotFoundError("Runway does not exist")
        return [self._direction_response(row) for row in await self.repository.direction_rows(run_id)]

    async def get_direction(self, direction_id: int) -> DirectionResponse:
        row = await self.repository.direction_row(direction_id)
        if row is None: raise RunwayNotFoundError("Direction does not exist")
        return self._direction_response(row)

    async def create_direction(self, run_id: int, data: DirectionCreate) -> DirectionResponse:
        runway = await self.repository.runway(run_id)
        if runway is None: raise RunwayNotFoundError("Runway does not exist")
        if data.designator not in {runway.DESIGNATOR_1, runway.DESIGNATOR_2}: raise RunwayValidationError("Direction designator must match one of the runway designators")
        if await self.repository.duplicate_direction(run_id, data.designator): raise RunwayConflictError("Runway direction already exists")
        item = RunwayDirection(RUN_ID=run_id, DESIGNATOR=data.designator, TRUE_BEARING_DEG=data.true_bearing_deg, THRESHOLD_ELEVATION_M=data.threshold_elevation_m, THRESHOLD_GEOM=self.repository.geometry(data.threshold_geom.model_dump()), SLOPE_PCT=data.slope_pct, STATUS_ID=await self._active_id())
        self.session.add(item); await self.session.commit(); return await self.get_direction(item.RUN_DIR_ID)

    async def regenerate_directions(self, run_id: int) -> list[DirectionResponse]:
        runway = await self.repository.runway(run_id)
        if runway is None: raise RunwayNotFoundError("Runway does not exist")
        airport = await self.repository.airport(runway.AIR_ID)
        row = await self.repository.runway_row(run_id)
        if airport is None or row is None: raise RunwayNotFoundError("Airport or runway does not exist")
        centerline = json.loads(row.centerline_geojson)["coordinates"]
        active_id = await self._active_id()
        archived = await self.repository.status_by_name("archived")
        specs = self._automatic_direction_specs(centerline, (runway.DESIGNATOR_1, runway.DESIGNATOR_2), airport.ELEVATION_M)
        existing = {item.DESIGNATOR: item for item, *_ in await self.repository.direction_rows(run_id)}
        current_designators = {spec["designator"] for spec in specs}
        for designator, item in existing.items():
            if designator not in current_designators and archived is not None:
                item.STATUS_ID = archived.STATUS_ID
        for spec in specs:
            item = existing.get(spec["designator"])
            if item is None:
                item = RunwayDirection(RUN_ID=run_id, DESIGNATOR=spec["designator"], THRESHOLD_ELEVATION_M=spec["threshold_elevation_m"], SLOPE_PCT=spec["slope_pct"])
                self.session.add(item)
            item.TRUE_BEARING_DEG = spec["true_bearing_deg"]
            item.THRESHOLD_GEOM = self.repository.geometry(spec["threshold_geom"])
            item.STATUS_ID = active_id
        await self.session.commit()
        return await self.list_directions(run_id)

    async def regenerate_clearway(self, direction_id: int, data: ClearwayGenerateRequest) -> AreaResponse:
        direction = await self.repository.direction(direction_id)
        if direction is None: raise RunwayNotFoundError("Direction does not exist")
        runway = await self.repository.runway(direction.RUN_ID)
        clearway_type = await self.repository.area_type_by_code("CWY")
        if runway is None or clearway_type is None: raise RunwayValidationError("Runway or Clearway area type is not configured")
        strip = await self.repository.strip(runway.RUN_ID)
        if strip is None:
            raise RunwayValidationError("Runway strip must be configured before calculating Clearway")
        active_id = await self._active_id()
        if strip.STATUS_ID != active_id:
            raise RunwayValidationError("Runway strip must be active before calculating Clearway")
        length = data.length_m
        minimum_width = Decimal(str(runway.WIDTH_M)) * 2
        width = data.width_m if data.width_m is not None else minimum_width
        if width < minimum_width:
            raise RunwayValidationError(f"Clearway width must be at least twice the runway width ({minimum_width} m)")
        geometry_row = (
            await self.session.execute(
                select(
                    func.ST_AsGeoJSON(RunwayDirection.THRESHOLD_GEOM),
                    func.ST_AsGeoJSON(RunwayStrip.GEOM),
                    func.ST_AsGeoJSON(Runway.CENTERLINE_GEOM),
                )
                .select_from(RunwayDirection)
                .join(Runway, Runway.RUN_ID == RunwayDirection.RUN_ID)
                .join(RunwayStrip, RunwayStrip.RUN_ID == RunwayDirection.RUN_ID)
                .where(
                    RunwayDirection.RUN_DIR_ID == direction_id,
                    RunwayStrip.RUN_ID == runway.RUN_ID,
                )
            )
        ).one_or_none()
        if geometry_row is None or any(value is None for value in geometry_row):
            raise RunwayValidationError("Direction, Strip or centerline geometry is not configured")
        threshold = json.loads(geometry_row[0])["coordinates"]
        strip_ring = json.loads(geometry_row[1])["coordinates"][0][:-1]
        centerline = json.loads(geometry_row[2])["coordinates"]
        lon, lat = float(threshold[0]), float(threshold[1])
        zone = int((lon + 180) // 6) + 1
        metric_srid = 32600 + zone if lat >= 0 else 32700 + zone
        to_metric = Transformer.from_crs(4326, metric_srid, always_xy=True)
        to_wgs84 = Transformer.from_crs(metric_srid, 4326, always_xy=True)
        threshold_xy = to_metric.transform(*threshold[:2])
        center_start = to_metric.transform(*centerline[0][:2])
        center_end = to_metric.transform(*centerline[-1][:2])
        delta_x, delta_y = center_end[0] - center_start[0], center_end[1] - center_start[1]
        centerline_length = math.hypot(delta_x, delta_y)
        if centerline_length == 0:
            raise RunwayValidationError("Runway centerline endpoints must be different")
        along_x, along_y = delta_x / centerline_length, delta_y / centerline_length
        strip_metric = [to_metric.transform(*point[:2]) for point in strip_ring]
        edge_candidates: list[tuple[float, tuple[float, float]]] = []
        for index, point in enumerate(strip_metric):
            next_point = strip_metric[(index + 1) % len(strip_metric)]
            edge_x, edge_y = next_point[0] - point[0], next_point[1] - point[1]
            edge_length = math.hypot(edge_x, edge_y)
            if edge_length == 0:
                continue
            parallel_score = abs((edge_x / edge_length) * along_x + (edge_y / edge_length) * along_y)
            midpoint = ((point[0] + next_point[0]) / 2, (point[1] + next_point[1]) / 2)
            edge_candidates.append((parallel_score, midpoint))
        end_midpoints = [item[1] for item in sorted(edge_candidates, key=lambda item: item[0])[:2]]
        if len(end_midpoints) != 2:
            raise RunwayValidationError("Runway Strip end edges could not be calculated")
        strip_end = min(
            end_midpoints,
            key=lambda point: math.hypot(point[0] - threshold_xy[0], point[1] - threshold_xy[1]),
        )
        center_midpoint = ((center_start[0] + center_end[0]) / 2, (center_start[1] + center_end[1]) / 2)
        if (strip_end[0] - center_midpoint[0]) * along_x + (strip_end[1] - center_midpoint[1]) * along_y < 0:
            along_x, along_y = -along_x, -along_y
        side_x, side_y = -along_y, along_x
        half_width = float(width) / 2
        end_x, end_y = strip_end[0] + along_x * float(length), strip_end[1] + along_y * float(length)
        metric_points = [
            (strip_end[0] + side_x * half_width, strip_end[1] + side_y * half_width),
            (end_x + side_x * half_width, end_y + side_y * half_width),
            (end_x - side_x * half_width, end_y - side_y * half_width),
            (strip_end[0] - side_x * half_width, strip_end[1] - side_y * half_width),
        ]
        coordinates = [list(to_wgs84.transform(x, y)) for x, y in metric_points]
        coordinates.append(coordinates[0])
        candidate = {"type": "Polygon", "coordinates": [coordinates]}
        item = await self.session.scalar(select(RunwayArea).where(RunwayArea.RUN_DIR_ID == direction_id, RunwayArea.AREA_TYPE_ID == clearway_type.AREA_TYPE_ID))
        clearway_geometry = self.repository.geometry(candidate)
        if item is None:
            item = RunwayArea(RUN_ID=runway.RUN_ID, RUN_DIR_ID=direction_id, AREA_TYPE_ID=clearway_type.AREA_TYPE_ID)
            self.session.add(item)
        item.LENGTH_M = length
        item.WIDTH_M = width
        item.GEOM = clearway_geometry
        item.STATUS_ID = active_id
        await self.session.commit()
        return await self.get_area(item.RUNWAY_AREA_ID)

    async def update_direction(self, direction_id: int, changes: dict[str, Any]) -> DirectionResponse:
        item = await self.repository.direction(direction_id)
        if item is None: raise RunwayNotFoundError("Direction does not exist")
        if "designator" in changes:
            runway = await self.repository.runway(item.RUN_ID)
            if runway is None or changes["designator"] not in {runway.DESIGNATOR_1, runway.DESIGNATOR_2}: raise RunwayValidationError("Direction designator must match one of the runway designators")
            if await self.repository.duplicate_direction(item.RUN_ID, changes["designator"], direction_id): raise RunwayConflictError("Runway direction already exists")
        for key, column in {"designator":"DESIGNATOR","true_bearing_deg":"TRUE_BEARING_DEG","threshold_elevation_m":"THRESHOLD_ELEVATION_M","slope_pct":"SLOPE_PCT"}.items():
            if key in changes: setattr(item, column, changes[key])
        if changes.get("threshold_geom") is not None: item.THRESHOLD_GEOM = self.repository.geometry(changes["threshold_geom"])
        await self.session.commit(); return await self.get_direction(direction_id)

    async def get_strip(self, run_id: int) -> StripResponse:
        row = await self.repository.strip_row(run_id)
        if row is None: raise RunwayNotFoundError("Runway strip does not exist")
        return self._strip_response(row)

    async def upsert_strip(self, run_id: int, data: StripUpsert) -> StripResponse:
        if await self.repository.runway(run_id) is None: raise RunwayNotFoundError("Runway does not exist")
        item = await self.repository.strip(run_id)
        if item is None:
            item = RunwayStrip(RUN_ID=run_id, STATUS_ID=await self._active_id()); self.session.add(item)
        item.LENGTH_M=data.length_m; item.WIDTH_M=data.width_m; item.GEOM=self.repository.geometry(data.geom.model_dump())
        await self.session.commit(); return await self.get_strip(run_id)

    async def generate_strip(self, run_id: int, data: StripGenerateRequest) -> StripResponse:
        runway = await self.repository.runway(run_id)
        row = await self.repository.runway_row(run_id)
        if runway is None or row is None: raise RunwayNotFoundError("Runway does not exist")
        if data.length_m < Decimal(str(runway.LENGTH_M)):
            raise RunwayValidationError(f"Strip length cannot be shorter than the runway ({runway.LENGTH_M} m)")
        coordinates = json.loads(row.centerline_geojson)["coordinates"]
        if len(coordinates) < 2: raise RunwayValidationError("Runway centerline requires at least two coordinates")
        width = data.centerline_offset_m * 2
        geometry = self._centered_parallel_polygon(coordinates, data.length_m, width)
        active_id = await self._active_id()
        item = await self.repository.strip(run_id)
        if item is None:
            item = RunwayStrip(RUN_ID=run_id, STATUS_ID=active_id); self.session.add(item)
        item.LENGTH_M = data.length_m
        item.WIDTH_M = width
        item.GEOM = self.repository.geometry(geometry)
        item.STATUS_ID = active_id
        await self.session.commit()
        return await self.get_strip(run_id)

    async def list_areas(self, direction_id: int) -> list[AreaResponse]:
        if await self.repository.direction(direction_id) is None: raise RunwayNotFoundError("Direction does not exist")
        return [self._area_response(row) for row in await self.repository.area_rows(direction_id)]

    async def get_area(self, area_id: int) -> AreaResponse:
        row = await self.repository.area_row(area_id)
        if row is None: raise RunwayNotFoundError("Runway area does not exist")
        return self._area_response(row)

    async def create_area(self, direction_id: int, data: AreaCreate) -> AreaResponse:
        direction = await self.repository.direction(direction_id)
        if direction is None: raise RunwayNotFoundError("Direction does not exist")
        if not await self.repository.area_type_exists(data.area_type_id): raise RunwayValidationError("Runway area type does not exist")
        if await self.repository.duplicate_area(direction_id, data.area_type_id): raise RunwayConflictError("This area type already exists for the direction")
        item = RunwayArea(RUN_ID=direction.RUN_ID, RUN_DIR_ID=direction_id, AREA_TYPE_ID=data.area_type_id, LENGTH_M=data.length_m, WIDTH_M=data.width_m, GEOM=self.repository.geometry(data.geom.model_dump()), STATUS_ID=await self._active_id())
        self.session.add(item); await self.session.commit(); return await self.get_area(item.RUNWAY_AREA_ID)

    async def update_area(self, area_id: int, changes: dict[str, Any]) -> AreaResponse:
        item = await self.repository.area(area_id)
        if item is None: raise RunwayNotFoundError("Runway area does not exist")
        if "area_type_id" in changes:
            if not await self.repository.area_type_exists(changes["area_type_id"]): raise RunwayValidationError("Runway area type does not exist")
            if await self.repository.duplicate_area(item.RUN_DIR_ID, changes["area_type_id"], area_id): raise RunwayConflictError("This area type already exists for the direction")
        for key, column in {"area_type_id":"AREA_TYPE_ID","length_m":"LENGTH_M","width_m":"WIDTH_M"}.items():
            if key in changes: setattr(item, column, changes[key])
        if changes.get("geom") is not None: item.GEOM=self.repository.geometry(changes["geom"])
        await self.session.commit(); return await self.get_area(area_id)
