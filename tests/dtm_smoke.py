"""End-to-end DTM metadata API smoke test."""
import asyncio,json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from uuid import uuid4
from sqlalchemy import delete,func,select
from app.core.database import AsyncSessionFactory,close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport,City,Country,IcaoCode,Status
from app.modules.dtm.models import DtmSource
from app.modules.users.models import Role,User,UserRole
BASE="http://localhost:8000/api/v1"
def call(path,method="GET",data=None,token=None):
    h={"Authorization":f"Bearer {token}"} if token else {}; body=json.dumps(data).encode() if data is not None else None
    if body: h["Content-Type"]="application/json"
    try:
        with urlopen(Request(BASE+path,data=body,headers=h,method=method),timeout=15) as r:
            raw=r.read(); return r.status,json.loads(raw) if raw else None
    except HTTPError as e:
        raw=e.read(); return e.code,json.loads(raw) if raw else None
def login(user,password):
    body=urlencode({"username":user,"password":password}).encode()
    with urlopen(Request(BASE+"/auth/login",data=body,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST"),timeout=15) as r: return json.loads(r.read())["access_token"]
async def main():
    suffix=uuid4().hex[:8]; username=f"dtm_admin_{suffix}"; password=f"Dtm-{uuid4().hex}!"
    async with AsyncSessionFactory() as s:
        active=await s.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active")); inactive=await s.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="inactive")); role=await s.scalar(select(Role.ROLE_ID).where(Role.CODE=="ADMIN"))
        country=Country(AZE_NAME="DTM ölkə",ENG_NAME=f"DTM Country {suffix}",ISO_CODE=f"D{suffix[:4]}".upper(),STATUS_ID=active); s.add(country); await s.flush()
        city=City(COUNTRY_ID=country.COUNTRY_ID,AZE_NAME="DTM şəhər",ENG_NAME="DTM City",STATUS_ID=active); icao=IcaoCode(ICAO_CODE=("D"+suffix[:3]).upper(),DESCRIPTION="DTM smoke",STATUS_ID=active); user=User(USERNAME=username,EMAIL=f"{username}@example.com",PASSWORD_HASH=hash_password(password),FIRST_NAME="DTM",LAST_NAME="Admin",STATUS_ID=active); s.add_all([city,icao,user]); await s.flush()
        airport=Airport(ICAO_ID=icao.ICAO_ID,IATA_CODE=None,AZE_NAME="DTM aeroport",ENG_NAME="DTM Airport",COUNTRY_ID=country.COUNTRY_ID,CITY_ID=city.CITY_ID,ELEVATION_M=10,ARP_GEOM=func.ST_GeomFromText("POINT(49.9 40.4)",4326),BOUNDARY_GEOM=func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))",4326),STATUS_ID=active); s.add(airport); await s.flush(); s.add(UserRole(USER_ID=user.USER_ID,ROLE_ID=role)); await s.commit()
        ids=(airport.AIR_ID,user.USER_ID,city.CITY_ID,country.COUNTRY_ID,icao.ICAO_ID)
        try:
            token=login(username,password); payload={"name":"Airport COG 2026","source_path":"s3://airport-gis/dtm/test.tif","source_type":"COG","crs":"EPSG:32639","resolution_m":"2.5","nodata_value":"-9999","is_primary":True,"coverage_geom":{"type":"Polygon","coordinates":[[[49.8,40.3],[50,40.3],[50,40.5],[49.8,40.5],[49.8,40.3]]]}}
            code,item=call(f"/airports/{ids[0]}/dtm-sources","POST",payload,token); assert code==201,(code,item); dtm=item["dtm_id"]
            code,listed=call(f"/airports/{ids[0]}/dtm-sources",token=token); assert code==200 and listed["total"]==1
            code,current=call(f"/airports/{ids[0]}/dtm-sources/active",token=token); assert code==200 and current["dtm_id"]==dtm
            code,updated=call(f"/dtm-sources/{dtm}","PATCH",{"resolution_m":"1.5","name":"Updated COG"},token); assert code==200 and updated["name"]=="Updated COG"
            code,_=call(f"/dtm-sources/{dtm}/status","PATCH",{"status_id":inactive},token); assert code==204
            code,_=call(f"/dtm-sources/{dtm}","DELETE",token=token); assert code==204
        finally:
            await s.execute(delete(DtmSource).where(DtmSource.AIR_ID==ids[0])); await s.execute(delete(Airport).where(Airport.AIR_ID==ids[0])); await s.execute(delete(User).where(User.USER_ID==ids[1])); await s.execute(delete(City).where(City.CITY_ID==ids[2])); await s.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID==ids[4])); await s.execute(delete(Country).where(Country.COUNTRY_ID==ids[3])); await s.commit()
    await close_database(); print("DTM smoke test passed.")
if __name__=="__main__": asyncio.run(main())
