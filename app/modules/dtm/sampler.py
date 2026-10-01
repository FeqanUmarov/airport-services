import asyncio
from dataclasses import dataclass
from pathlib import Path
import rasterio
from pyproj import Transformer
from app.core.config import settings

class DtmSamplingError(ValueError): pass
@dataclass(frozen=True)
class DtmSample:
    dtm_id:int; elevation_m:float

class DtmSampler:
    @staticmethod
    def _safe_path(source_path:str)->Path:
        root=Path(settings.dtm_raster_root).resolve(); candidate=Path(source_path)
        if not candidate.is_absolute(): candidate=root/candidate
        candidate=candidate.resolve()
        if candidate!=root and root not in candidate.parents: raise DtmSamplingError("DTM source_path must be inside the configured DTM raster directory")
        if not candidate.is_file(): raise DtmSamplingError("DTM raster file does not exist")
        return candidate
    @classmethod
    def _sample_sync(cls,source_path:str,longitude:float,latitude:float,nodata_value:float|None)->float:
        path=cls._safe_path(source_path)
        with rasterio.open(path) as dataset:
            if dataset.crs is None: raise DtmSamplingError("DTM raster CRS is missing")
            transformer=Transformer.from_crs("EPSG:4326",dataset.crs,always_xy=True); x,y=transformer.transform(longitude,latitude)
            if not (dataset.bounds.left<=x<=dataset.bounds.right and dataset.bounds.bottom<=y<=dataset.bounds.top): raise DtmSamplingError("Coordinate is outside DTM raster coverage")
            value=float(next(dataset.sample([(x,y)],indexes=1,masked=True))[0])
            nodata=dataset.nodata if dataset.nodata is not None else nodata_value
            if nodata is not None and abs(value-float(nodata))<1e-9: raise DtmSamplingError("DTM has NoData at this coordinate")
            if not (-12000<=value<=10000): raise DtmSamplingError("Sampled DTM elevation is outside a plausible range")
            return value
    async def sample(self,dtm,longitude:float,latitude:float)->DtmSample:
        if not dtm.SOURCE_PATH: raise DtmSamplingError("DTM source path is not configured")
        value=await asyncio.to_thread(self._sample_sync,dtm.SOURCE_PATH,longitude,latitude,float(dtm.NODATA_VALUE) if dtm.NODATA_VALUE is not None else None)
        return DtmSample(dtm_id=dtm.DTM_ID,elevation_m=round(value,3))
