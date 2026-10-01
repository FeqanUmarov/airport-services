import io
import tempfile
import zipfile
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer

from app.core.config import settings
from app.modules.gis_import.schemas import ShapefilePreviewResponse


class GisImportError(ValueError):
    pass


class ShapefilePreviewer:
    allowed_suffixes = {".shp", ".shx", ".dbf", ".prj", ".cpg"}

    @staticmethod
    def _transform_geometry(shape: shapefile.Shape, transformer: Transformer) -> dict:
        geometry = dict(shape.__geo_interface__)
        if geometry.get("type") == "Null":
            raise GisImportError("Null geometry is not supported")

        def walk(value):
            if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
                isinstance(item, (int, float)) for item in value[:2]
            ):
                longitude, latitude = transformer.transform(value[0], value[1])
                return [longitude, latitude, *value[2:]]
            return [walk(item) for item in value]

        geometry["coordinates"] = walk(geometry["coordinates"])
        return geometry

    def run(self, content: bytes, file_name: str) -> ShapefilePreviewResponse:
        if len(content) > settings.import_max_bytes:
            raise GisImportError("Upload exceeds the configured size limit")
        with tempfile.TemporaryDirectory(prefix="airport-gis-preview-") as directory:
            root = Path(directory)
            try:
                archive = zipfile.ZipFile(io.BytesIO(content))
            except zipfile.BadZipFile as exc:
                raise GisImportError("Uploaded file is not a valid ZIP archive") from exc
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) > 100 or sum(member.file_size for member in members) > settings.import_max_bytes * 4:
                raise GisImportError("Archive is too large")
            for member in members:
                member_path = Path(member.filename)
                if member_path.name != member.filename:
                    raise GisImportError("Archive must not contain directories")
                if member_path.suffix.lower() in self.allowed_suffixes:
                    (root / member_path.name).write_bytes(archive.read(member))
            shape_files = [path for path in root.iterdir() if path.suffix.lower() == ".shp"]
            if len(shape_files) != 1:
                raise GisImportError("ZIP must contain exactly one .shp file")
            shape_path = shape_files[0]
            companions = {
                suffix: next((path for path in root.iterdir() if path.stem == shape_path.stem and path.suffix.lower() == suffix), None)
                for suffix in (".shx", ".dbf", ".prj")
            }
            if any(path is None for path in companions.values()):
                raise GisImportError("ZIP must contain matching .shp, .shx, .dbf and .prj files")
            try:
                source_crs = CRS.from_wkt(companions[".prj"].read_text(errors="strict"))
            except Exception as exc:
                raise GisImportError("Shapefile .prj CRS is invalid") from exc
            transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
            try:
                reader = shapefile.Reader(str(shape_path))
            except Exception as exc:
                raise GisImportError("Shapefile cannot be read") from exc
            if len(reader) == 0:
                raise GisImportError("Shapefile contains no features")
            if len(reader) > settings.import_max_features:
                raise GisImportError("Shapefile exceeds the configured feature limit")
            fields = [field[0] for field in reader.fields[1:]]
            features = []
            geometry_types: set[str] = set()
            for index, shape_record in enumerate(reader.iterShapeRecords()):
                geometry = self._transform_geometry(shape_record.shape, transformer)
                geometry_types.add(str(geometry["type"]))
                features.append({
                    "type": "Feature",
                    "id": index,
                    "geometry": geometry,
                    "properties": shape_record.record.as_dict(),
                })
            bbox = None
            if reader.bbox:
                minimum = transformer.transform(reader.bbox[0], reader.bbox[1])
                maximum = transformer.transform(reader.bbox[2], reader.bbox[3])
                bbox = [minimum[0], minimum[1], maximum[0], maximum[1]]
            return ShapefilePreviewResponse(
                file_name=file_name,
                source_crs=source_crs.to_string(),
                feature_count=len(features),
                geometry_types=sorted(geometry_types),
                fields=fields,
                bbox=bbox,
                feature_collection={"type": "FeatureCollection", "features": features},
            )
