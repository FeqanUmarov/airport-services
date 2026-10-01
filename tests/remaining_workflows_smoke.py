"""DTM sampling, manual check and Shapefile import end-to-end smoke test."""
import asyncio,io,json,tempfile,zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from uuid import uuid4
import numpy as np
import rasterio,shapefile
from pyproj import CRS,Transformer
from rasterio.transform import from_origin
from sqlalchemy import delete,func,select
from app.core.database import AsyncSessionFactory,close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport,City,Country,IcaoCode,Status
from app.modules.dtm.models import DtmSource
from app.modules.obstacles.models import Obstacle,ObstacleType
from app.modules.users.models import Role,User,UserRole
BASE="http://localhost:8000/api/v1"
def login(user,password):
    body=urlencode({"username":user,"password":password}).encode()
    with urlopen(Request(BASE+"/auth/login",data=body,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")) as r:return json.loads(r.read())["access_token"]
def json_call(path,method,data,token):
    body=json.dumps(data).encode()
    with urlopen(Request(BASE+path,data=body,headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},method=method),timeout=30) as r:return r.status,json.loads(r.read())
def multipart_call(path,fields,file_bytes,token):
    boundary="----AirportGIS"+uuid4().hex; chunks=[]
    for name,value in fields.items(): chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()])
    chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"obstacles.zip\"\r\nContent-Type: application/zip\r\n\r\n".encode(),file_bytes,f"\r\n--{boundary}--\r\n".encode()]); body=b"".join(chunks)
    with urlopen(Request(BASE+path,data=body,headers={"Content-Type":f"multipart/form-data; boundary={boundary}","Authorization":f"Bearer {token}"},method="POST"),timeout=30) as r:return r.status,json.loads(r.read())
def make_shapefile_zip():
    with tempfile.TemporaryDirectory() as tmp:
        base=str(Path(tmp)/"obstacles"); writer=shapefile.Writer(base,shapeType=shapefile.POINT); writer.field("NAME","C",size=80); writer.field("HEIGHT","N",decimal=3)
        x,y=Transformer.from_crs(4326,32639,always_xy=True).transform(49.9,40.4); writer.point(x,y); writer.record("Imported tower",25); writer.close(); Path(base+".prj").write_text(CRS.from_epsg(32639).to_wkt())
        output=io.BytesIO()
        with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
            for suffix in (".shp",".shx",".dbf",".prj"): archive.write(base+suffix,"obstacles"+suffix)
        return output.getvalue()
async def main():
    suffix=uuid4().hex[:7]; username=f"flow_{suffix}"; password=f"Flow-{uuid4().hex}!"; raster_path=Path(f"/app/data/dtm/smoke-{suffix}.tif"); raster_path.parent.mkdir(parents=True,exist_ok=True)
    with rasterio.open(raster_path,"w",driver="GTiff",height=10,width=10,count=1,dtype="float32",crs="EPSG:4326",transform=from_origin(49.8,40.5,0.02,0.02),nodata=-9999) as ds: ds.write(np.full((1,10,10),100,dtype="float32"))
    async with AsyncSessionFactory() as s:
        active=await s.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active")); role=await s.scalar(select(Role.ROLE_ID).where(Role.CODE=="ADMIN"))
        country=Country(AZE_NAME="Flow",ENG_NAME=f"Flow {suffix}",ISO_CODE=f"F{suffix[:4]}".upper(),STATUS_ID=active); s.add(country); await s.flush(); city=City(COUNTRY_ID=country.COUNTRY_ID,AZE_NAME="Flow",ENG_NAME="Flow city",STATUS_ID=active); icao=IcaoCode(ICAO_CODE=("F"+suffix[:3]).upper(),DESCRIPTION="Flow",STATUS_ID=active); user=User(USERNAME=username,EMAIL=f"{username}@x.test",PASSWORD_HASH=hash_password(password),FIRST_NAME="Flow",LAST_NAME="Admin",STATUS_ID=active); kind=ObstacleType(CODE=f"FLOW_{suffix}",AZE_NAME="Qüllə",ENG_NAME="Tower",STATUS_ID=active); s.add_all([city,icao,user,kind]); await s.flush()
        airport=Airport(ICAO_ID=icao.ICAO_ID,AZE_NAME="Flow",ENG_NAME="Flow airport",COUNTRY_ID=country.COUNTRY_ID,CITY_ID=city.CITY_ID,ELEVATION_M=10,ARP_GEOM=func.ST_GeomFromText("POINT(49.9 40.4)",4326),BOUNDARY_GEOM=func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))",4326),STATUS_ID=active); s.add(airport); await s.flush(); dtm=DtmSource(AIR_ID=airport.AIR_ID,NAME="Smoke raster",SOURCE_PATH=raster_path.name,SOURCE_TYPE="GEOTIFF",CRS="EPSG:4326",RESOLUTION_M=2000,NODATA_VALUE=-9999,COVERAGE_GEOM=func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))",4326),IS_PRIMARY=True,STATUS_ID=active); s.add(dtm); await s.flush(); s.add(UserRole(USER_ID=user.USER_ID,ROLE_ID=role)); await s.commit(); ids=(airport.AIR_ID,user.USER_ID,city.CITY_ID,country.COUNTRY_ID,icao.ICAO_ID,kind.OBSTACLE_TYPE_ID,dtm.DTM_ID)
        try:
            token=login(username,password); code,sample=json_call(f"/dtm-sources/{ids[6]}/sample","POST",{"longitude":49.9,"latitude":40.4},token); assert code==200 and float(sample["elevation_m"])==100
            payload={"air_id":ids[0],"obstacle_type_id":ids[5],"eng_name":"Sampled tower","object_height_m":25,"geometry":{"type":"Point","coordinates":[49.9,40.4]},"persist":False}
            code,result=json_call("/obstacles/check","POST",payload,token); assert code==200 and result["analyzable"] and result["dtm_used"] and float(result["ground_elevation_m"])==100 and float(result["top_elevation_m"])==125 and result["obstacle_id"] is None
            unavailable={**payload,"geometry":{"type":"Point","coordinates":[48.0,40.0]},"persist":False}; code,no_dtm=json_call("/obstacles/check","POST",unavailable,token); assert code==200 and not no_dtm["analyzable"] and not no_dtm["dtm_used"] and no_dtm["top_elevation_m"] is None
            payload["persist"]=True; code,saved=json_call("/obstacles/check","POST",payload,token); assert code==200 and saved["obstacle_id"]
            code,imported=multipart_call("/obstacles/import",{"air_id":ids[0],"obstacle_type_id":ids[5],"name_field":"NAME","height_field":"HEIGHT"},make_shapefile_zip(),token); assert code==200 and imported["imported_count"]==1 and imported["failed_count"]==0,(code,imported)
            code,preview=multipart_call("/gis-import/shapefile/preview",{},make_shapefile_zip(),token); assert code==200 and preview["feature_count"]==1 and preview["geometry_types"]==["Point"] and preview["source_crs"],(code,preview)
        finally:
            await s.execute(delete(Obstacle).where(Obstacle.AIR_ID==ids[0])); await s.execute(delete(DtmSource).where(DtmSource.AIR_ID==ids[0])); await s.execute(delete(Airport).where(Airport.AIR_ID==ids[0])); await s.execute(delete(User).where(User.USER_ID==ids[1])); await s.execute(delete(ObstacleType).where(ObstacleType.OBSTACLE_TYPE_ID==ids[5])); await s.execute(delete(City).where(City.CITY_ID==ids[2])); await s.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID==ids[4])); await s.execute(delete(Country).where(Country.COUNTRY_ID==ids[3])); await s.commit()
    raster_path.unlink(missing_ok=True); await close_database(); print("Remaining workflows smoke test passed.")
if __name__=="__main__": asyncio.run(main())
