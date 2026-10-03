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


# Fixed-precision (snap-rounded) overlay grid in metres. It keeps repeated
# Difference/Intersection/Union operations robust without moving any boundary
# by a measurable amount.
OVERLAY_GRID_M = 1e-6


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

    @staticmethod
    def _metric(value: dict[str, Any], srid: int):
        return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), srid)

    async def _polygonal_geojson(self, expression: Any) -> dict[str, Any] | None:
        polygonal = func.ST_Multi(func.ST_CollectionExtract(func.ST_Force2D(expression), 3))
        row = (await self.session.execute(select(func.ST_IsEmpty(polygonal), func.ST_AsGeoJSON(polygonal, 15)))).one()
        return None if row[0] is None or bool(row[0]) else json.loads(row[1])

    async def metric_geometry(self, geometry: Any, srid: int, *, shell: bool = False) -> dict[str, Any] | None:
        """Return a stored WGS84 polygon in the metric CRS (exterior shell optional)."""
        value = func.ST_Transform(func.ST_Force2D(geometry), srid)
        if shell:
            value = func.ST_MakePolygon(func.ST_ExteriorRing(value))
        return await self._polygonal_geojson(value)

    async def buffer_line(self, coordinates: list[tuple[float, float]], radius_m: float, quad_segs: int, srid: int) -> dict[str, Any] | None:
        line = self._metric({"type": "LineString", "coordinates": [list(point) for point in coordinates]}, srid)
        return await self._polygonal_geojson(func.ST_Buffer(line, radius_m, f"quad_segs={quad_segs} endcap=round join=round"))

    async def union(self, srid: int, geometries: list[dict[str, Any] | None]) -> dict[str, Any] | None:
        items = [self._metric(item, srid) for item in geometries if item]
        if not items:
            return None
        return await self._polygonal_geojson(func.ST_UnaryUnion(func.ST_Collect(array(items)), OVERLAY_GRID_M))

    async def intersection(self, srid: int, first: dict[str, Any] | None, second: dict[str, Any] | None) -> dict[str, Any] | None:
        if not first or not second:
            return None
        return await self._polygonal_geojson(func.ST_Intersection(self._metric(first, srid), self._metric(second, srid), OVERLAY_GRID_M))

    async def difference(self, srid: int, geometry: dict[str, Any] | None, *subtract: dict[str, Any] | None) -> dict[str, Any] | None:
        removal = await self.union(srid, list(subtract))
        if not geometry or not removal:
            return geometry
        return await self._polygonal_geojson(func.ST_Difference(self._metric(geometry, srid), self._metric(removal, srid), OVERLAY_GRID_M))

    async def snap(self, srid: int, geometry: dict[str, Any], reference: dict[str, Any] | None, tolerance_m: float) -> dict[str, Any]:
        """Remove CRS round-trip noise against a shared reference boundary."""
        if not reference:
            return geometry
        snapped = await self._polygonal_geojson(func.ST_Snap(self._metric(geometry, srid), self._metric(reference, srid), tolerance_m))
        return snapped or geometry

    async def node(self, srid: int, geometry: dict[str, Any] | None, neighbours: list[dict[str, Any] | None], tolerance_m: float) -> dict[str, Any] | None:
        """Insert neighbour vertices lying on this boundary (shared nodes).

        Edges that are collinear in the metric CRS are only collinear in WGS84
        when both sides carry the same vertices, so every shared boundary gets
        the union of both vertex sets.
        """
        reference = await self.union(srid, neighbours)
        if not geometry or not reference:
            return geometry
        noded = func.ST_Snap(self._metric(geometry, srid), func.ST_Boundary(self._metric(reference, srid)), tolerance_m)
        return await self._polygonal_geojson(noded) or geometry

    async def topology_metrics(self, srid: int, geometry: dict[str, Any] | None, references: list[dict[str, Any] | None]) -> tuple[float, float, float]:
        """Return gap distance, overlap area and overlap sliver width in metres."""
        reference = await self.union(srid, references)
        if not geometry or not reference:
            return 0.0, 0.0, 0.0
        first, second = self._metric(geometry, srid), self._metric(reference, srid)
        overlap = func.ST_CollectionExtract(func.ST_Intersection(first, second, OVERLAY_GRID_M), 3)
        row = (await self.session.execute(select(func.ST_Distance(first, second), func.ST_Area(overlap), func.ST_Perimeter(overlap)))).one()
        area = float(row[1] or 0.0); perimeter = float(row[2] or 0.0)
        return float(row[0] or 0.0), area, (2 * area / perimeter if perimeter > 0 else 0.0)

    @staticmethod
    def metric_multipolygon_z(polygons: list[list[list[tuple[float, float, float]]]], srid: int):
        """Build a 3D MultiPolygon from metric rings and store it in WGS84."""
        parts = []
        for rings in polygons:
            ring_text = []
            for ring in rings:
                closed = ring if ring[0] == ring[-1] else [*ring, ring[0]]
                ring_text.append("(" + ", ".join(f"{x!r} {y!r} {z!r}" for x, y, z in closed) + ")")
            parts.append("(" + ", ".join(ring_text) + ")")
        return func.ST_Transform(func.ST_GeomFromEWKT(f"SRID={srid};MULTIPOLYGON Z ({', '.join(parts)})"), 4326)

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
