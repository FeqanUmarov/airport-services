import math
from decimal import Decimal
from typing import Any

from pyproj import Transformer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gis_import.importer import GisImportError, ShapefilePreviewer
from app.modules.gis_import.schemas import ShapefileImportMetadata, ShapefileImportResponse
from app.modules.ols.schemas import ManualOlsCreate, ManualOlsGeometry
from app.modules.ols.service import ManualOlsService
from app.modules.runways.schemas import AreaCreate, PolygonGeometry, RunwayCreate, StripUpsert
from app.modules.runways.service import RunwayService


class ShapefileImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _polygon_features(preview) -> list[dict[str, Any]]:
        geometries = [feature["geometry"] for feature in preview.feature_collection["features"]]
        if not geometries or any(item.get("type") not in {"Polygon", "MultiPolygon"} for item in geometries):
            raise GisImportError("Selected target requires Polygon or MultiPolygon geometry")
        return geometries

    @staticmethod
    def _single_polygon(geometries: list[dict[str, Any]]) -> dict[str, Any]:
        if len(geometries) != 1 or geometries[0]["type"] != "Polygon":
            raise GisImportError("Runway, Strip and Runway Area imports require exactly one Polygon feature")
        return geometries[0]

    @staticmethod
    def _footprint_metrics(geometry: dict[str, Any]) -> tuple[float, float, dict[str, Any]]:
        ring = geometry["coordinates"][0]
        if len(ring) < 4:
            raise GisImportError("Polygon exterior ring is invalid")
        lon = sum(float(point[0]) for point in ring[:-1]) / (len(ring) - 1)
        lat = sum(float(point[1]) for point in ring[:-1]) / (len(ring) - 1)
        zone = int((lon + 180) // 6) + 1
        srid = (32600 if lat >= 0 else 32700) + zone
        forward = Transformer.from_crs(4326, srid, always_xy=True)
        inverse = Transformer.from_crs(srid, 4326, always_xy=True)
        points = [forward.transform(float(point[0]), float(point[1])) for point in ring[:-1]]
        cx = sum(point[0] for point in points) / len(points); cy = sum(point[1] for point in points) / len(points)
        xx = sum((x-cx)**2 for x, _ in points); yy = sum((y-cy)**2 for _, y in points); xy = sum((x-cx)*(y-cy) for x, y in points)
        angle = .5 * math.atan2(2*xy, xx-yy); ux, uy = math.cos(angle), math.sin(angle); vx, vy = -uy, ux
        along = [(x-cx)*ux+(y-cy)*uy for x, y in points]; across = [(x-cx)*vx+(y-cy)*vy for x, y in points]
        if max(across)-min(across) > max(along)-min(along):
            along, across, ux, uy = across, along, vx, vy
        minimum, maximum = min(along), max(along)
        first = inverse.transform(cx+minimum*ux, cy+minimum*uy); last = inverse.transform(cx+maximum*ux, cy+maximum*uy)
        return maximum-minimum, max(across)-min(across), {"type":"LineString","coordinates":[list(first),list(last)]}

    async def import_archive(self, content: bytes, file_name: str, metadata: ShapefileImportMetadata, user_id: int) -> ShapefileImportResponse:
        preview = ShapefilePreviewer().run(content, file_name)
        geometries = self._polygon_features(preview)
        target = metadata.target
        ids: list[int] = []
        runway_service = RunwayService(self.session)
        if target == "RUNWAY":
            polygon = self._single_polygon(geometries); measured_length, measured_width, centerline = self._footprint_metrics(polygon)
            if not metadata.designator_1 or not metadata.designator_2:
                raise GisImportError("Both runway designators are required")
            result = await runway_service.create_runway(metadata.air_id, RunwayCreate(
                aze_name=metadata.aze_name or f"RWY {metadata.designator_1}/{metadata.designator_2}", eng_name=metadata.eng_name or f"RWY {metadata.designator_1}/{metadata.designator_2}",
                designator_1=metadata.designator_1, designator_2=metadata.designator_2,
                length_m=metadata.length_m or Decimal(str(round(measured_length,3))), width_m=metadata.width_m or Decimal(str(round(measured_width,3))),
                geom=PolygonGeometry(**polygon), centerline_geom=centerline,
            )); ids=[result.run_id]
        elif target == "STRIP":
            if not metadata.run_id: raise GisImportError("Runway is required for Strip import")
            polygon=self._single_polygon(geometries); measured_length, measured_width, _=self._footprint_metrics(polygon)
            result=await runway_service.upsert_strip(metadata.run_id,StripUpsert(length_m=metadata.length_m or Decimal(str(round(measured_length,3))),width_m=metadata.width_m or Decimal(str(round(measured_width,3))),geom=PolygonGeometry(**polygon))); ids=[result.strip_id]
        elif target == "RUNWAY_AREA":
            if not metadata.run_dir_id or not metadata.area_type_id: raise GisImportError("Runway direction and area type are required")
            polygon=self._single_polygon(geometries); measured_length, measured_width, _=self._footprint_metrics(polygon)
            result=await runway_service.create_area(metadata.run_dir_id,AreaCreate(area_type_id=metadata.area_type_id,length_m=metadata.length_m or Decimal(str(round(measured_length,3))),width_m=metadata.width_m or Decimal(str(round(measured_width,3))),geom=PolygonGeometry(**polygon))); ids=[result.runway_area_id]
        else:
            if not metadata.standard_ols_id: raise GisImportError("Standard OLS surface configuration is required")
            polygons=[]
            for geometry in geometries:
                polygons.extend(geometry["coordinates"] if geometry["type"]=="MultiPolygon" else [geometry["coordinates"]])
            combined={"type":"MultiPolygon","coordinates":polygons}
            result=await ManualOlsService(self.session).create(ManualOlsCreate(standard_ols_id=metadata.standard_ols_id,air_id=metadata.air_id,run_id=metadata.run_id,run_dir_id=metadata.run_dir_id,aze_name=metadata.aze_name,eng_name=metadata.eng_name,geometry=ManualOlsGeometry(**combined),default_elevation_m=metadata.default_elevation_m or Decimal("0"),revision_note=f"Imported from {file_name}"),user_id); ids=[result.ols_surface_id]
        return ShapefileImportResponse(target=target,imported_count=len(ids),object_ids=ids,source_crs=preview.source_crs,geometry_types=preview.geometry_types)
