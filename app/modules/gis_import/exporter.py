import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import shapefile
from pyproj import CRS
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Status
from app.modules.ols.models import OlsSurface, OlsSurfaceType, StandardOlsSurface
from app.modules.runways.models import Runway, RunwayArea, RunwayAreaType, RunwayDirection, RunwayStrip


class AirportShapefileExporter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]+", "_", value.upper()).strip("_")[:48] or "LAYER"

    @staticmethod
    def _parts(geometry: dict[str, Any]) -> list[list[list[float]]]:
        if geometry["type"] == "Polygon":
            return geometry["coordinates"]
        if geometry["type"] == "MultiPolygon":
            return [ring for polygon in geometry["coordinates"] for ring in polygon]
        raise ValueError(f"Unsupported export geometry: {geometry['type']}")

    @staticmethod
    def _has_z(parts: list[list[list[float]]]) -> bool:
        return any(len(point) >= 3 for ring in parts for point in ring)

    def _write_polygon_layer(self, root: Path, name: str, rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
        if not rows: return
        all_parts=[self._parts(geometry) for geometry,_ in rows]
        use_z=any(self._has_z(parts) for parts in all_parts)
        writer=shapefile.Writer(str(root/name),shapeType=shapefile.POLYGONZ if use_z else shapefile.POLYGON,encoding="utf-8")
        writer.field("OBJECT_ID","N",18,0); writer.field("LAYER","C",50); writer.field("RUNWAY","C",20); writer.field("DIRECTION","C",10); writer.field("NAME_AZ","C",120); writer.field("NAME_EN","C",120)
        for (geometry,attributes),parts in zip(rows,all_parts):
            if use_z:
                writer.polyz([[[float(p[0]),float(p[1]),float(p[2]) if len(p)>=3 else 0.0] for p in ring] for ring in parts])
            else: writer.poly(parts)
            writer.record(attributes.get("id"),attributes.get("layer"),attributes.get("runway",""),attributes.get("direction",""),attributes.get("aze_name",""),attributes.get("eng_name",""))
        writer.close(); (root/f"{name}.prj").write_text(CRS.from_epsg(4326).to_wkt(),encoding="utf-8"); (root/f"{name}.cpg").write_text("UTF-8",encoding="ascii")

    def _write_centerlines(self, root: Path, rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
        if not rows:return
        name="RUNWAY_CENTERLINES"; writer=shapefile.Writer(str(root/name),shapeType=shapefile.POLYLINE,encoding="utf-8"); writer.field("RUN_ID","N",18,0); writer.field("RUNWAY","C",20)
        for geometry,attrs in rows: writer.line([geometry["coordinates"]]); writer.record(attrs["id"],attrs["runway"])
        writer.close(); (root/f"{name}.prj").write_text(CRS.from_epsg(4326).to_wkt(),encoding="utf-8"); (root/f"{name}.cpg").write_text("UTF-8",encoding="ascii")

    async def export(self, air_id: int) -> bytes:
        active_id=await self.session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active"))
        if active_id is None: raise ValueError("Active status is not configured")
        runway_rows=(await self.session.execute(select(Runway,func.ST_AsGeoJSON(Runway.GEOM),func.ST_AsGeoJSON(Runway.CENTERLINE_GEOM)).where(Runway.AIR_ID==air_id,Runway.STATUS_ID==active_id))).all()
        run_ids=[row[0].RUN_ID for row in runway_rows]
        direction_map={item.RUN_DIR_ID:item.DESIGNATOR for item in (await self.session.scalars(select(RunwayDirection).where(RunwayDirection.RUN_ID.in_(run_ids)))).all()} if run_ids else {}
        runway_map={item.RUN_ID:f"{item.DESIGNATOR_1}/{item.DESIGNATOR_2}" for item,_,_ in runway_rows}
        runways=[]; centerlines=[]
        for item,geom,line in runway_rows:
            attrs={"id":item.RUN_ID,"layer":"RUNWAY","runway":runway_map[item.RUN_ID],"aze_name":item.AZE_NAME,"eng_name":item.ENG_NAME}; runways.append((json.loads(geom),attrs)); centerlines.append((json.loads(line),attrs))
        strips=[]
        if run_ids:
            for item,geom in (await self.session.execute(select(RunwayStrip,func.ST_AsGeoJSON(RunwayStrip.GEOM)).where(RunwayStrip.RUN_ID.in_(run_ids),RunwayStrip.STATUS_ID==active_id))).all(): strips.append((json.loads(geom),{"id":item.STRIP_ID,"layer":"STRIP","runway":runway_map.get(item.RUN_ID,"")}))
        areas_by_type:dict[str,list]= {}
        if run_ids:
            statement=select(RunwayArea,RunwayAreaType.CODE,func.ST_AsGeoJSON(RunwayArea.GEOM)).join(RunwayAreaType,RunwayAreaType.AREA_TYPE_ID==RunwayArea.AREA_TYPE_ID).where(RunwayArea.RUN_ID.in_(run_ids),RunwayArea.STATUS_ID==active_id)
            for item,code,geom in (await self.session.execute(statement)).all(): areas_by_type.setdefault(code,[]).append((json.loads(geom),{"id":item.RUNWAY_AREA_ID,"layer":code,"runway":runway_map.get(item.RUN_ID,""),"direction":direction_map.get(item.RUN_DIR_ID,"")}))
        ols_by_type:dict[str,list]= {}
        statement=select(OlsSurface,OlsSurfaceType.CODE,func.ST_AsGeoJSON(OlsSurface.GEOM,15)).join(StandardOlsSurface,StandardOlsSurface.STANDARD_OLS_ID==OlsSurface.STANDARD_OLS_ID).join(OlsSurfaceType,OlsSurfaceType.SURFACE_TYPE_ID==StandardOlsSurface.SURFACE_TYPE_ID).where(OlsSurface.AIR_ID==air_id,OlsSurface.STATUS_ID==active_id)
        for item,code,geom in (await self.session.execute(statement)).all(): ols_by_type.setdefault(code,[]).append((json.loads(geom),{"id":item.OLS_SURFACE_ID,"layer":code,"runway":runway_map.get(item.RUN_ID,""),"direction":direction_map.get(item.RUN_DIR_ID,""),"aze_name":item.AZE_NAME or "","eng_name":item.ENG_NAME or ""}))
        if not runways and not ols_by_type: raise ValueError("Selected airport has no active GIS layers to export")
        with tempfile.TemporaryDirectory(prefix="airport-gis-export-") as directory:
            root=Path(directory); self._write_polygon_layer(root,"RUNWAYS",runways); self._write_centerlines(root,centerlines); self._write_polygon_layer(root,"RUNWAY_STRIP",strips)
            for code,rows in areas_by_type.items(): self._write_polygon_layer(root,f"RUNWAY_AREA_{self._safe_name(code)}",rows)
            for code,rows in ols_by_type.items(): self._write_polygon_layer(root,f"OLS_{self._safe_name(code)}",rows)
            output=io.BytesIO()
            with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(root.iterdir()): archive.write(path,path.name)
            return output.getvalue()
