"""End-to-end obstacles API smoke test."""
import asyncio,json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from uuid import uuid4
from sqlalchemy import delete,func,select
from app.core.database import AsyncSessionFactory,close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport,City,Country,IcaoCode,Status
from app.modules.obstacles.models import Obstacle,ObstacleType
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
    suffix=uuid4().hex[:8]; username=f"obs_admin_{suffix}"; password=f"Obs-{uuid4().hex}!"
    async with AsyncSessionFactory() as s:
        active=await s.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active")); inactive=await s.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="inactive")); role=await s.scalar(select(Role.ROLE_ID).where(Role.CODE=="ADMIN"))
        country=Country(AZE_NAME="Maneə ölkə",ENG_NAME=f"Obstacle Country {suffix}",ISO_CODE=f"O{suffix[:4]}".upper(),STATUS_ID=active); s.add(country); await s.flush()
        city=City(COUNTRY_ID=country.COUNTRY_ID,AZE_NAME="Maneə şəhər",ENG_NAME="Obstacle City",STATUS_ID=active); icao=IcaoCode(ICAO_CODE=("O"+suffix[:3]).upper(),DESCRIPTION="Obstacle smoke",STATUS_ID=active); user=User(USERNAME=username,EMAIL=f"{username}@example.com",PASSWORD_HASH=hash_password(password),FIRST_NAME="Obstacle",LAST_NAME="Admin",STATUS_ID=active); otype=ObstacleType(CODE=f"TOWER_{suffix}",AZE_NAME="Qüllə",ENG_NAME="Tower",DESCRIPTION="Test",STATUS_ID=active); s.add_all([city,icao,user,otype]); await s.flush()
        airport=Airport(ICAO_ID=icao.ICAO_ID,IATA_CODE=None,AZE_NAME="Maneə aeroport",ENG_NAME="Obstacle Airport",COUNTRY_ID=country.COUNTRY_ID,CITY_ID=city.CITY_ID,ELEVATION_M=10,ARP_GEOM=func.ST_GeomFromText("POINT(49.9 40.4)",4326),BOUNDARY_GEOM=func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))",4326),STATUS_ID=active); s.add(airport); await s.flush(); s.add(UserRole(USER_ID=user.USER_ID,ROLE_ID=role)); await s.commit(); ids=(airport.AIR_ID,user.USER_ID,city.CITY_ID,country.COUNTRY_ID,icao.ICAO_ID,otype.OBSTACLE_TYPE_ID)
        try:
            token=login(username,password); base={"eng_name":"Test tower","obstacle_type_id":ids[5],"object_height_m":"25","geometry":{"type":"Point","coordinates":[49.9,40.4]}}
            code,_=call(f"/airports/{ids[0]}/obstacles","POST",base,token); assert code==422
            payload={**base,"ground_elevation_m":"487.3"}; code,item=call(f"/airports/{ids[0]}/obstacles","POST",payload,token); assert code==201,(code,item); oid=item["obstacle_id"]; assert float(item["top_elevation_m"])==512.3
            code,listed=call(f"/airports/{ids[0]}/obstacles?search=tower",token=token); assert code==200 and listed["total"]==1
            code,geo=call(f"/airports/{ids[0]}/obstacles/geojson",token=token); assert code==200 and len(geo["features"])==1
            code,updated=call(f"/obstacles/{oid}","PATCH",{"object_height_m":"30"},token); assert code==200 and float(updated["top_elevation_m"])==517.3
            code,_=call(f"/obstacles/{oid}/status","PATCH",{"status_id":inactive},token); assert code==204
            code,_=call(f"/obstacles/{oid}","DELETE",token=token); assert code==204
        finally:
            await s.execute(delete(Obstacle).where(Obstacle.AIR_ID==ids[0])); await s.execute(delete(Airport).where(Airport.AIR_ID==ids[0])); await s.execute(delete(User).where(User.USER_ID==ids[1])); await s.execute(delete(ObstacleType).where(ObstacleType.OBSTACLE_TYPE_ID==ids[5])); await s.execute(delete(City).where(City.CITY_ID==ids[2])); await s.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID==ids[4])); await s.execute(delete(Country).where(Country.COUNTRY_ID==ids[3])); await s.commit()
    await close_database(); print("Obstacles smoke test passed.")
if __name__=="__main__": asyncio.run(main())
