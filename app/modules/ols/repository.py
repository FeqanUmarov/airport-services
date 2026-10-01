import json
from collections import defaultdict
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Airport, Status
from app.modules.ols.models import (
    OlsGenerationMethod,
    OlsParameter,
    OlsSurface,
    OlsSurfaceType,
    Standard,
    StandardOlsParameterValue,
    StandardOlsSurface,
)
from app.modules.runways.models import Runway, RunwayArea, RunwayAreaType, RunwayDirection, RunwayStrip


class OlsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def runway_context(self, run_id: int):
        statement = select(
            Runway,
            Airport,
            func.ST_AsGeoJSON(Runway.CENTERLINE_GEOM).label("centerline"),
        ).join(Airport, Airport.AIR_ID == Runway.AIR_ID).where(Runway.RUN_ID == run_id)
        return (await self.session.execute(statement)).one_or_none()

    async def direction_contexts(self, run_id: int):
        statement = (
            select(
                RunwayDirection,
                func.ST_AsGeoJSON(RunwayDirection.THRESHOLD_GEOM).label("threshold"),
            )
            .where(RunwayDirection.RUN_ID == run_id)
            .order_by(RunwayDirection.RUN_DIR_ID)
        )
        return list((await self.session.execute(statement)).all())

    async def standard_exists(self, standard_id: int) -> bool:
        return await self.session.get(Standard, standard_id) is not None

    async def automatic_method(self) -> OlsGenerationMethod | None:
        return await self.session.scalar(
            select(OlsGenerationMethod).where(OlsGenerationMethod.CODE == "AUTOMATIC")
        )

    async def active_status(self) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == "active")
        )

    async def configurations(self, standard_id: int):
        statement = (
            select(
                StandardOlsSurface,
                OlsSurfaceType.CODE.label("surface_code"),
                OlsSurfaceType.AZE_NAME.label("surface_aze_name"),
                OlsSurfaceType.ENG_NAME.label("surface_eng_name"),
                OlsParameter.CODE.label("parameter_code"),
                StandardOlsParameterValue.SECTION_NO,
                StandardOlsParameterValue.NUMERIC_VALUE,
                StandardOlsParameterValue.BOOLEAN_VALUE,
            )
            .join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID)
            .outerjoin(StandardOlsParameterValue, StandardOlsParameterValue.STANDARD_OLS_ID == StandardOlsSurface.STANDARD_OLS_ID)
            .outerjoin(OlsParameter, OlsParameter.PARAMETER_ID == StandardOlsParameterValue.PARAMETER_ID)
            .join(Status, Status.STATUS_ID == StandardOlsSurface.STATUS_ID)
            .where(StandardOlsSurface.STANDARD_ID == standard_id, func.lower(Status.ENG_NAME) == "active")
            .order_by(StandardOlsSurface.STANDARD_OLS_ID, StandardOlsParameterValue.SECTION_NO)
        )
        rows = (await self.session.execute(statement)).all()
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(row[0].STANDARD_OLS_ID, {"surface": row[0], "code": row.surface_code, "aze_name": row.surface_aze_name, "eng_name": row.surface_eng_name, "parameters": defaultdict(dict)})
            if row.parameter_code:
                value = row.NUMERIC_VALUE if row.NUMERIC_VALUE is not None else row.BOOLEAN_VALUE
                item["parameters"][int(row.SECTION_NO)][row.parameter_code.upper()] = value
        return list(grouped.values())

    async def delete_existing(self, standard_ols_ids: list[int], run_id: int, method_id: int) -> None:
        if standard_ols_ids:
            await self.session.execute(delete(OlsSurface).where(OlsSurface.STANDARD_OLS_ID.in_(standard_ols_ids), OlsSurface.RUN_ID == run_id, OlsSurface.GENERATION_METHOD_ID == method_id))

    async def existing_surface(
        self,
        *,
        standard_ols_id: int,
        run_id: int,
        run_dir_id: int | None,
        method_id: int,
    ) -> OlsSurface | None:
        statement = select(OlsSurface).where(
            OlsSurface.STANDARD_OLS_ID == standard_ols_id,
            OlsSurface.RUN_ID == run_id,
            OlsSurface.GENERATION_METHOD_ID == method_id,
        )
        if run_dir_id is None:
            statement = statement.where(OlsSurface.RUN_DIR_ID.is_(None))
        else:
            statement = statement.where(OlsSurface.RUN_DIR_ID == run_dir_id)
        return await self.session.scalar(statement)

    async def projected_point(self, longitude: float, latitude: float, distance_m: float, bearing_deg: float) -> tuple[float, float]:
        """Offset a WGS84 point in a local metric CRS.

        OLS dimensions are never applied directly to angular coordinates.
        """
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        zone = int((longitude + 180) // 6) + 1
        metric_srid = (32600 if latitude >= 0 else 32700) + zone
        metric = func.ST_Transform(point, metric_srid)
        radians = __import__("math").radians(bearing_deg)
        moved = func.ST_Translate(metric, distance_m * __import__("math").sin(radians), distance_m * __import__("math").cos(radians))
        geometry = func.ST_Transform(moved, 4326)
        row = (
            await self.session.execute(
                select(func.ST_X(geometry), func.ST_Y(geometry))
            )
        ).one()
        return float(row[0]), float(row[1])

    async def centerline_buffer_3d(self, run_id: int, radius_m: float, elevation_m: float, inner_radius_m: float | None = None):
        centerline = await self.session.scalar(select(Runway.CENTERLINE_GEOM).where(Runway.RUN_ID == run_id))
        if centerline is None:
            raise ValueError("Runway centerline is required")
        centroid = func.ST_Centroid(centerline)
        row = (await self.session.execute(select(func.ST_X(centroid), func.ST_Y(centroid)))).one()
        lon, lat = float(row[0]), float(row[1])
        zone = int((lon + 180) // 6) + 1
        metric_srid = (32600 if lat >= 0 else 32700) + zone
        metric_line = func.ST_Transform(centerline, metric_srid)
        footprint = func.ST_Buffer(metric_line, radius_m, "endcap=round join=round")
        if inner_radius_m is not None:
            footprint = func.ST_Difference(footprint, func.ST_Buffer(metric_line, inner_radius_m, "endcap=round join=round"))
        footprint = func.ST_Transform(footprint, 4326)
        return func.ST_Translate(func.ST_Force3D(footprint), 0, 0, elevation_m)

    async def conical_surface_3d(self, run_id: int, inner_radius_m: float, horizontal_width_m: float, inner_elevation_m: float, outer_elevation_m: float):
        centerline = await self.session.scalar(select(Runway.CENTERLINE_GEOM).where(Runway.RUN_ID == run_id))
        if centerline is None:
            raise ValueError("Runway centerline is required")
        centroid = func.ST_Centroid(centerline)
        row = (await self.session.execute(select(func.ST_X(centroid), func.ST_Y(centroid)))).one()
        lon, lat = float(row[0]), float(row[1])
        zone = int((lon + 180) // 6) + 1
        metric_srid = (32600 if lat >= 0 else 32700) + zone
        metric_line = func.ST_Transform(centerline, metric_srid)
        inner = func.ST_Buffer(metric_line, inner_radius_m, "endcap=round join=round")
        outer = func.ST_Buffer(metric_line, inner_radius_m + horizontal_width_m, "endcap=round join=round")
        outer_ring = func.ST_Translate(func.ST_Force3D(func.ST_ExteriorRing(outer)), 0, 0, outer_elevation_m)
        inner_ring = func.ST_Reverse(func.ST_Translate(func.ST_Force3D(func.ST_ExteriorRing(inner)), 0, 0, inner_elevation_m))
        polygon = func.ST_MakePolygon(outer_ring, array([inner_ring]))
        return func.ST_Transform(polygon, 4326)

    async def active_strip(self, run_id: int):
        statement = (
            select(RunwayStrip, func.ST_AsGeoJSON(RunwayStrip.GEOM).label("geojson"))
            .join(Status, Status.STATUS_ID == RunwayStrip.STATUS_ID)
            .where(RunwayStrip.RUN_ID == run_id, func.lower(Status.ENG_NAME) == "active")
        )
        return (await self.session.execute(statement)).one_or_none()

    async def active_clearway(self, direction_id: int):
        statement = (
            select(RunwayArea, func.ST_AsGeoJSON(RunwayArea.GEOM).label("geojson"))
            .join(RunwayAreaType, RunwayAreaType.AREA_TYPE_ID == RunwayArea.AREA_TYPE_ID)
            .join(Status, Status.STATUS_ID == RunwayArea.STATUS_ID)
            .where(
                RunwayArea.RUN_DIR_ID == direction_id,
                func.upper(RunwayAreaType.CODE).in_(("CWY", "CLEARWAY")),
                func.lower(Status.ENG_NAME) == "active",
            )
        )
        return (await self.session.execute(statement)).one_or_none()

    async def aggregate_threshold_circles_3d(
        self,
        run_id: int,
        radius_m: float,
        elevation_m: float,
        inner_radius_m: float | None = None,
    ):
        threshold_points = list(
            (
                await self.session.scalars(
                    select(RunwayDirection.THRESHOLD_GEOM)
                    .where(RunwayDirection.RUN_ID == run_id)
                    .order_by(RunwayDirection.RUN_DIR_ID)
                )
            ).all()
        )
        if len(threshold_points) != 2:
            raise ValueError("Exactly two runway thresholds are required")
        threshold_collection = func.ST_Collect(*threshold_points)
        centroid = await self.session.execute(
            select(
                func.ST_X(func.ST_Centroid(threshold_collection)),
                func.ST_Y(func.ST_Centroid(threshold_collection)),
            )
        )
        lon, lat = centroid.one()
        zone = int((float(lon) + 180) // 6) + 1
        metric_srid = (32600 if float(lat) >= 0 else 32700) + zone
        metric_thresholds = [
            func.ST_Transform(point, metric_srid) for point in threshold_points
        ]
        circles = [func.ST_Buffer(point, radius_m) for point in metric_thresholds]
        # ArcGIS Aggregate Polygons equivalent for this two-circle use case:
        # merge both circles and bridge their concave/common boundary with the
        # smallest convex outer envelope.
        footprint = func.ST_ConvexHull(func.ST_Collect(*circles))
        if inner_radius_m is not None:
            inner_circles = [
                func.ST_Buffer(point, inner_radius_m)
                for point in metric_thresholds
            ]
            inner_aggregate = func.ST_ConvexHull(func.ST_Collect(*inner_circles))
            footprint = func.ST_Difference(
                footprint,
                inner_aggregate,
            )
        footprint = func.ST_Transform(footprint, 4326)
        return func.ST_Translate(func.ST_Force3D(footprint), 0, 0, elevation_m)

    @staticmethod
    def polygon_z(points: list[tuple[float, float, float]]):
        closed = points if points[0] == points[-1] else [*points, points[0]]
        coordinates = ", ".join(f"{lon} {lat} {z}" for lon, lat, z in closed)
        return func.ST_GeomFromEWKT(f"SRID=4326;POLYGON Z (({coordinates}))")

    @staticmethod
    def multipolygon_z(polygons: list[list[tuple[float, float, float]]]):
        rings = []
        for points in polygons:
            closed = points if points[0] == points[-1] else [*points, points[0]]
            coordinates = ", ".join(f"{lon} {lat} {z}" for lon, lat, z in closed)
            rings.append(f"(({coordinates}))")
        return func.ST_GeomFromEWKT(f"SRID=4326;MULTIPOLYGON Z ({', '.join(rings)})")

    async def add_surface(self, **values: Any) -> OlsSurface:
        item = OlsSurface(**values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def geometry_is_valid(self, geometry: Any) -> tuple[bool, str]:
        row = (await self.session.execute(select(func.ST_IsValid(func.ST_Force2D(geometry)), func.ST_IsValidReason(func.ST_Force2D(geometry)), func.ST_IsEmpty(geometry)))).one()
        return bool(row[0]) and not bool(row[2]), str(row[1])

    def surface_details_statement(self):
        return (
            select(
                OlsSurface,
                Standard.STANDARD_ID.label("standard_id"),
                Standard.CODE.label("standard_code"),
                OlsSurfaceType.CODE.label("surface_type"),
                OlsGenerationMethod.CODE.label("generation_method"),
                Status.ENG_NAME.label("status_name"),
                func.ST_AsGeoJSON(OlsSurface.GEOM).label("geojson"),
            )
            .join(StandardOlsSurface, StandardOlsSurface.STANDARD_OLS_ID == OlsSurface.STANDARD_OLS_ID)
            .join(Standard, Standard.STANDARD_ID == StandardOlsSurface.STANDARD_ID)
            .join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID)
            .join(OlsGenerationMethod, OlsGenerationMethod.GENERATION_METHOD_ID == OlsSurface.GENERATION_METHOD_ID)
            .join(Status, Status.STATUS_ID == OlsSurface.STATUS_ID)
        )

    async def list_surfaces(self, *, air_id: int, offset: int, limit: int, run_id: int | None, run_dir_id: int | None, generation_method: str | None, status_id: int | None, standard_id: int | None = None, surface_type: str | None = None):
        conditions = [OlsSurface.AIR_ID == air_id]
        if run_id is not None: conditions.append(OlsSurface.RUN_ID == run_id)
        if run_dir_id is not None: conditions.append(OlsSurface.RUN_DIR_ID == run_dir_id)
        if generation_method is not None: conditions.append(OlsGenerationMethod.CODE == generation_method.upper())
        if status_id is not None:
            conditions.append(OlsSurface.STATUS_ID == status_id)
        else:
            # Preserve archived geometry for audit/revisions without exposing it
            # as an operational layer in default map and list responses.
            conditions.append(
                OlsSurface.STATUS_ID.in_(
                    select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) != "archived")
                )
            )
        if standard_id is not None: conditions.append(Standard.STANDARD_ID == standard_id)
        if surface_type is not None: conditions.append(OlsSurfaceType.CODE == surface_type.upper())
        statement = self.surface_details_statement().where(*conditions)
        total = int((await self.session.scalar(select(func.count(OlsSurface.OLS_SURFACE_ID)).join(StandardOlsSurface, StandardOlsSurface.STANDARD_OLS_ID == OlsSurface.STANDARD_OLS_ID).join(Standard, Standard.STANDARD_ID == StandardOlsSurface.STANDARD_ID).join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID).join(OlsGenerationMethod, OlsGenerationMethod.GENERATION_METHOD_ID == OlsSurface.GENERATION_METHOD_ID).where(*conditions))) or 0)
        rows = (await self.session.execute(statement.order_by(OlsSurface.OLS_SURFACE_ID).offset(offset).limit(limit))).all()
        return list(rows), total

    async def surface_row(self, surface_id: int):
        return (await self.session.execute(self.surface_details_statement().where(OlsSurface.OLS_SURFACE_ID == surface_id))).one_or_none()

    async def surface_model(self, surface_id: int) -> OlsSurface | None:
        return await self.session.get(OlsSurface, surface_id)

    async def standard_surface(self, standard_ols_id: int) -> StandardOlsSurface | None:
        return await self.session.get(StandardOlsSurface, standard_ols_id)

    async def airport(self, air_id: int) -> Airport | None:
        return await self.session.get(Airport, air_id)

    async def runway(self, run_id: int) -> Runway | None:
        return await self.session.get(Runway, run_id)

    async def direction(self, direction_id: int) -> RunwayDirection | None:
        return await self.session.get(RunwayDirection, direction_id)

    async def manual_method(self) -> OlsGenerationMethod | None:
        return await self.session.scalar(select(OlsGenerationMethod).where(OlsGenerationMethod.CODE == "MANUAL"))

    async def status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def status_by_name(self, name: str) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == name.casefold())
        )

    @staticmethod
    def manual_geometry(value: dict[str, Any], default_elevation: float | None):
        geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), 4326)
        if default_elevation is not None:
            geometry = func.ST_Translate(func.ST_Force3D(geometry), 0, 0, default_elevation)
        return geometry
