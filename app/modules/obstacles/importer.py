import tempfile,zipfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import shapefile
from pyproj import CRS,Transformer
from app.core.config import settings
from app.modules.obstacles.schemas import ObstacleGeometry
from app.modules.violations.schemas import ObstacleImportItem,ObstacleImportResponse
from app.modules.violations.service import ViolationService

class ShapefileImportError(ValueError): pass
class ShapefileImporter:
    def __init__(self,service:ViolationService): self.service=service
    @staticmethod
    def number(record,field):
        if not field: return None
        value=record.get(field)
        if value in (None,""): return None
        try: return Decimal(str(value))
        except (TypeError,ValueError): raise ShapefileImportError(f"Field {field} must contain numeric values")
    @staticmethod
    def transformed_geometry(shape,transformer):
        geo=dict(shape.__geo_interface__)
        if geo.get("type")=="Null": raise ShapefileImportError("Null geometry is not supported")
        def walk(value):
            if isinstance(value,(list,tuple)) and len(value)>=2 and all(isinstance(v,(int,float)) for v in value[:2]):
                x,y=transformer.transform(value[0],value[1]); return [x,y,*value[2:]]
            return [walk(v) for v in value]
        geo["coordinates"]=walk(geo["coordinates"]); return geo
    async def run(self,content:bytes,*,air_id:int,obstacle_type_id:int,name_field:str|None,ground_field:str|None,height_field:str|None,top_field:str|None,default_height:float|None):
        if len(content)>settings.import_max_bytes: raise ShapefileImportError("Upload exceeds the configured size limit")
        with tempfile.TemporaryDirectory(prefix="airport-gis-shp-") as directory:
            root=Path(directory)
            try: archive=zipfile.ZipFile(__import__("io").BytesIO(content))
            except zipfile.BadZipFile as exc: raise ShapefileImportError("Uploaded file is not a valid ZIP archive") from exc
            members=[m for m in archive.infolist() if not m.is_dir()]
            if len(members)>100 or sum(m.file_size for m in members)>settings.import_max_bytes*4: raise ShapefileImportError("Archive is too large")
            for member in members:
                if Path(member.filename).name!=member.filename: raise ShapefileImportError("Archive must not contain directories")
                if Path(member.filename).suffix.lower() in {".shp",".shx",".dbf",".prj"}: (root/member.filename).write_bytes(archive.read(member))
            shp_files=list(root.glob("*.shp"))+list(root.glob("*.SHP"))
            if len(shp_files)!=1: raise ShapefileImportError("ZIP must contain exactly one .shp file")
            shp=shp_files[0]; stem=shp.stem; companions={suffix:next((p for p in root.iterdir() if p.stem==stem and p.suffix.lower()==suffix),None) for suffix in (".shx",".dbf",".prj")}
            if any(v is None for v in companions.values()): raise ShapefileImportError("ZIP must contain matching .shp, .shx, .dbf and .prj files")
            try: source_crs=CRS.from_wkt(companions[".prj"].read_text(errors="strict"))
            except Exception as exc: raise ShapefileImportError("Shapefile .prj CRS is invalid") from exc
            transformer=Transformer.from_crs(source_crs,"EPSG:4326",always_xy=True)
            try: reader=shapefile.Reader(str(shp))
            except Exception as exc: raise ShapefileImportError("Shapefile cannot be read") from exc
            if len(reader)>settings.import_max_features: raise ShapefileImportError("Shapefile exceeds the configured feature limit")
            field_names={f[0] for f in reader.fields[1:]}
            for field in (name_field,ground_field,height_field,top_field):
                if field and field not in field_names: raise ShapefileImportError(f"Field {field} does not exist in the Shapefile")
            results=[]
            for index,feature in enumerate(reader.iterShapeRecords()):
                try:
                    record=feature.record.as_dict(); geometry=self.transformed_geometry(feature.shape,transformer)
                    payload=SimpleNamespace(air_id=air_id,obstacle_type_id=obstacle_type_id,geometry=ObstacleGeometry.model_validate(geometry),aze_name=None,eng_name=str(record.get(name_field))[:255] if name_field and record.get(name_field) is not None else None,ground_elevation_m=self.number(record,ground_field),object_height_m=self.number(record,height_field) if height_field else (Decimal(str(default_height)) if default_height is not None else None),top_elevation_m=self.number(record,top_field),persist=True)
                    response=await self.service.manual_check(payload); results.append(ObstacleImportItem(feature_index=index,success=response.analyzable,obstacle_id=response.obstacle_id,has_violation=response.has_violation,violation_count=len(response.violations),error=response.message))
                except Exception as exc:
                    await self.service.session.rollback(); results.append(ObstacleImportItem(feature_index=index,success=False,error=str(exc)))
            return ObstacleImportResponse(imported_count=sum(i.success for i in results),failed_count=sum(not i.success for i in results),items=results)
