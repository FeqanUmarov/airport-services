"""End-to-end runway, direction, strip and area smoke test."""

import asyncio, json, math
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from pyproj import Transformer
from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport, City, Country, IcaoCode, Status
from app.modules.runways.models import Runway, RunwayArea, RunwayAreaType, RunwayStrip
from app.modules.users.models import Role, User, UserRole

BASE_URL = "http://localhost:8000/api/v1"


def call(path, method="GET", data=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = json.dumps(data).encode() if data is not None else None
    if data is not None: headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(BASE_URL + path, data=body, headers=headers, method=method), timeout=15) as response:
            content = response.read(); return response.status, json.loads(content) if content else None
    except HTTPError as exc:
        content = exc.read(); return exc.code, json.loads(content) if content else None


def login(username, password):
    body = urlencode({"username": username, "password": password}).encode()
    with urlopen(Request(BASE_URL + "/auth/login", data=body, headers={"Content-Type":"application/x-www-form-urlencoded"}, method="POST"), timeout=15) as response:
        return json.loads(response.read())["access_token"]


async def main():
    suffix = uuid4().hex[:7]; username = f"runway_admin_{suffix}"; password = f"Runway-{uuid4().hex}!"; run_id = None
    async with AsyncSessionFactory() as session:
        active = await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active")); inactive = await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="inactive")); admin_role = await session.scalar(select(Role.ROLE_ID).where(Role.CODE=="ADMIN"))
        assert active and inactive and admin_role
        country=Country(AZE_NAME="Test",ENG_NAME="Test",ISO_CODE=f"R{suffix[:5].upper()}",STATUS_ID=active); session.add(country); await session.flush()
        city=City(COUNTRY_ID=country.COUNTRY_ID,AZE_NAME="Test",ENG_NAME=f"Runway City {suffix}",STATUS_ID=active); icao=IcaoCode(ICAO_CODE=f"R{suffix[:3].upper()}",DESCRIPTION="Test",STATUS_ID=active); session.add_all([city,icao]); await session.flush()
        airport=Airport(ICAO_ID=icao.ICAO_ID,IATA_CODE=None,AZE_NAME="Test",ENG_NAME="Runway Airport",COUNTRY_ID=country.COUNTRY_ID,CITY_ID=city.CITY_ID,ELEVATION_M=10,ARP_GEOM=func.ST_SetSRID(func.ST_GeomFromText("POINT(49.9 40.4)"),4326),BOUNDARY_GEOM=func.ST_SetSRID(func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))"),4326),STATUS_ID=active)
        area_type=RunwayAreaType(CODE=f"RESA_{suffix}",AZE_NAME="RESA",ENG_NAME="RESA",DESCRIPTION=None,STATUS_ID=active)
        user=User(USERNAME=username,EMAIL=f"{username}@example.com",PASSWORD_HASH=hash_password(password),FIRST_NAME="Runway",LAST_NAME="Admin",STATUS_ID=active)
        session.add_all([airport,area_type,user]); await session.flush(); session.add(UserRole(USER_ID=user.USER_ID,ROLE_ID=admin_role)); await session.commit()
        ids=(country.COUNTRY_ID,city.CITY_ID,icao.ICAO_ID,airport.AIR_ID,area_type.AREA_TYPE_ID,user.USER_ID)
        try:
            token=login(username,password); polygon={"type":"Polygon","coordinates":[[[49.85,40.39],[49.95,40.39],[49.95,40.41],[49.85,40.41],[49.85,40.39]]]}
            runway={"aze_name":"Uçuş-enmə zolağı","eng_name":"Runway 09/27","designator_1":"09","designator_2":"27","length_m":"3000","width_m":"45","geom":polygon,"centerline_geom":{"type":"LineString","coordinates":[[49.85,40.4],[49.95,40.4]]}}
            code, created=call(f"/airports/{airport.AIR_ID}/runways","POST",runway,token); assert code==201 and created; run_id=int(created["run_id"])
            code,_=call(f"/airports/{airport.AIR_ID}/runways","POST",runway,token); assert code==409
            code,listed=call(f"/airports/{airport.AIR_ID}/runways?search=09",token=token); assert code==200 and listed["total"]==1
            code,auto_directions=call(f"/runways/{run_id}/directions",token=token); assert code==200 and len(auto_directions)==2
            direction_out=next(item for item in auto_directions if item["designator"]=="09"); direction_id=int(direction_out["run_dir_id"])
            assert abs(float(direction_out["true_bearing_deg"])-90.0)<0.1 and direction_out["threshold_geom"]["coordinates"]==[49.85,40.4]
            code,auto_areas=call(f"/runway-directions/{direction_id}/areas",token=token); assert code==200 and auto_areas==[]
            code,_=call(f"/runway-directions/{direction_id}/areas/regenerate-clearway","POST",{"length_m":240,"width_m":90},token); assert code==400
            direction={"designator":"09","true_bearing_deg":"90","threshold_elevation_m":"10","threshold_geom":{"type":"Point","coordinates":[49.85,40.4]},"slope_pct":"0.5"}
            code,_=call(f"/runways/{run_id}/directions","POST",direction,token); assert code==409
            code,_=call(f"/runways/{run_id}/directions","POST",{**direction,"designator":"10"},token); assert code==400
            code,updated_direction=call(f"/runway-directions/{direction_id}","PATCH",{"slope_pct":"0.5"},token); assert code==200 and float(updated_direction["slope_pct"])==0.5
            code,regenerated=call(f"/runways/{run_id}/directions/regenerate","POST",token=token); assert code==200 and len(regenerated)==2 and float(next(item for item in regenerated if item["designator"]=="09")["slope_pct"])==0.5
            distances={"tora_m":"3000","toda_m":"3240","asda_m":"3060","lda_m":"3000"}
            code,declared=call(f"/runway-directions/{direction_id}/declared-distances","PUT",distances,token); assert code==200 and declared and float(declared["toda_m"])==3240.0
            code,_=call(f"/runway-directions/{direction_id}/declared-distances","PUT",{**distances,"toda_m":"2900"},token); assert code==422
            code,_=call(f"/runway-directions/{direction_id}/declared-distances/status","PATCH",{"status_id":inactive},token); assert code==204
            code,declared_inactive=call(f"/runway-directions/{direction_id}/declared-distances",token=token); assert code==200 and declared_inactive["status"].lower()=="inactive"
            code,_=call(f"/runway-directions/{direction_id}/declared-distances","DELETE",token=token); assert code==204
            code,declared_archived=call(f"/runway-directions/{direction_id}/declared-distances",token=token); assert code==200 and declared_archived["status"].lower()=="archived"
            code,strip=call(f"/runways/{run_id}/strip/generate","POST",{"length_m":"3240","centerline_offset_m":"120"},token); assert code==200 and strip and float(strip["length_m"])==3240 and float(strip["width_m"])==240
            to_metric=Transformer.from_crs(4326,32639,always_xy=True)
            center_start=to_metric.transform(49.85,40.4); center_end=to_metric.transform(49.95,40.4)
            strip_start=to_metric.transform(*strip["geom"]["coordinates"][0][0]); strip_end=to_metric.transform(*strip["geom"]["coordinates"][0][1])
            center_vector=(center_end[0]-center_start[0],center_end[1]-center_start[1]); strip_vector=(strip_end[0]-strip_start[0],strip_end[1]-strip_start[1])
            cross=center_vector[0]*strip_vector[1]-center_vector[1]*strip_vector[0]
            assert abs(cross)/(math.hypot(*center_vector)*math.hypot(*strip_vector)) < 1e-7
            code,generated_clearway=call(f"/runway-directions/{direction_id}/areas/regenerate-clearway","POST",{"length_m":240,"width_m":90},token); assert code==200, (code,generated_clearway); assert generated_clearway["area_type_code"]=="CWY" and float(generated_clearway["length_m"])==240 and float(generated_clearway["width_m"])==90
            code,_=call(f"/runway-areas/{generated_clearway['runway_area_id']}","DELETE",token=token); assert code==204
            code,archived_clearway=call(f"/runway-areas/{generated_clearway['runway_area_id']}",token=token); assert code==200 and archived_clearway["status"].lower()=="archived"
            area={"area_type_id":area_type.AREA_TYPE_ID,"length_m":"240","width_m":"90","geom":polygon}
            code,area_out=call(f"/runway-directions/{direction_id}/areas","POST",area,token); assert code==201 and area_out; area_id=int(area_out["runway_area_id"])
            code,updated=call(f"/runway-areas/{area_id}","PATCH",{"length_m":"250"},token); assert code==200 and float(updated["length_m"])==250.0
            code,_=call(f"/runway-directions/{direction_id}/status","PATCH",{"status_id":inactive},token); assert code==204
            code,direction_status=call(f"/runway-directions/{direction_id}",token=token); assert code==200 and direction_status["status"].lower()=="inactive"
            code,_=call(f"/runway-areas/{area_id}/status","PATCH",{"status_id":inactive},token); assert code==204
            code,area_status=call(f"/runway-areas/{area_id}",token=token); assert code==200 and area_status["status"].lower()=="inactive"
            code,_=call(f"/runways/{run_id}/strip/status","PATCH",{"status_id":inactive},token); assert code==204
            code,strip_status=call(f"/runways/{run_id}/strip",token=token); assert code==200 and strip_status["status"].lower()=="inactive"
            code,_=call(f"/runways/{run_id}/strip","DELETE",token=token); assert code==204
            code,strip_archived=call(f"/runways/{run_id}/strip",token=token); assert code==200 and strip_archived["status"].lower()=="archived"
            code,_=call(f"/runways/{run_id}","DELETE",token=token); assert code==204
            code,archived=call(f"/runways/{run_id}",token=token); assert code==200 and archived["status"].lower()=="archived"
        finally:
            if run_id: await session.execute(delete(Runway).where(Runway.RUN_ID==run_id))
            country_id,city_id,icao_id,airport_id,area_type_id,user_id=ids
            await session.execute(delete(Airport).where(Airport.AIR_ID==airport_id)); await session.execute(delete(RunwayAreaType).where(RunwayAreaType.AREA_TYPE_ID==area_type_id)); await session.execute(delete(User).where(User.USER_ID==user_id)); await session.execute(delete(City).where(City.CITY_ID==city_id)); await session.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID==icao_id)); await session.execute(delete(Country).where(Country.COUNTRY_ID==country_id)); await session.commit()
    await close_database(); print("Runways smoke test passed.")


if __name__ == "__main__": asyncio.run(main())
