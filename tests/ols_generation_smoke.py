"""End-to-end automatic OLS generation smoke test."""

import asyncio, json, math
from datetime import date
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from geoalchemy2 import Geography
from sqlalchemy import delete, func, select, true
from sqlalchemy.orm import aliased

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport, City, Country, IcaoCode, Status
from app.modules.ols.models import OlsParameter, OlsSurface, OlsSurfaceType, Standard, StandardOlsParameterValue, StandardOlsSurface, StandardType, Unit
from app.modules.ols_revisions.models import OlsSurfaceRevision
from app.modules.obstacles.models import Obstacle, ObstacleType, OlsViolation
from app.modules.runways.models import Runway, RunwayDirection, RunwayStrip
from app.modules.users.models import Role, User, UserRole

BASE_URL="http://localhost:8000/api/v1"


def login(username,password):
    body=urlencode({"username":username,"password":password}).encode()
    with urlopen(Request(BASE_URL+"/auth/login",data=body,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST"),timeout=15) as response: return json.loads(response.read())["access_token"]


def generate(token,standard_id,run_id,replace_existing=True):
    body=json.dumps({"standard_id":standard_id,"run_id":run_id,"replace_existing":replace_existing}).encode()
    with urlopen(Request(BASE_URL+"/ols/generate",data=body,headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},method="POST"),timeout=30) as response: return response.status,json.loads(response.read())


def call(path, method="GET", data=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = json.dumps(data).encode() if data is not None else None
    if data is not None: headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(BASE_URL+path,data=body,headers=headers,method=method),timeout=30) as response:
            content=response.read(); return response.status,json.loads(content) if content else None
    except HTTPError as exc:
        content=exc.read(); return exc.code,json.loads(content) if content else None

def call_text(path, token):
    with urlopen(Request(BASE_URL+path,headers={"Authorization":f"Bearer {token}"}),timeout=30) as response:
        return response.status,response.read().decode(),response.headers.get_content_type()


async def main():
    suffix=uuid4().hex[:7]; username=f"ols_admin_{suffix}"; password=f"Ols-{uuid4().hex}!"
    async with AsyncSessionFactory() as session:
        active=await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="active")); admin_role=await session.scalar(select(Role.ROLE_ID).where(Role.CODE=="ADMIN")); assert active and admin_role
        meter=Unit(CODE=f"METER_{suffix}",SYMBOL="m",AZE_NAME="Metr",ENG_NAME="Meter",DESCRIPTION=None,STATUS_ID=active); percent=Unit(CODE=f"PERCENT_{suffix}",SYMBOL="%",AZE_NAME="Faiz",ENG_NAME="Percent",DESCRIPTION=None,STATUS_ID=active); session.add_all([meter,percent]); await session.flush()
        parameter_units={"HORIZONTAL_OFFSET":meter,"HEIGHT":meter,"HORIZONTAL_WIDTH":meter,"START_DISTANCE":meter,"INNER_EDGE":meter,"DIVERGENCE":percent,"LENGTH":meter,"SLOPE":percent,"CLEARWAY":meter,"FINAL_WIDTH":meter}
        parameters={}; created_parameter_ids=[]
        for code,unit in parameter_units.items():
            item=await session.scalar(select(OlsParameter).where(OlsParameter.CODE==code))
            if item is None:
                item=OlsParameter(CODE=code,AZE_NAME=code,ENG_NAME=code,UNIT_ID=unit.UNIT_ID,DESCRIPTION=None,STATUS_ID=active); session.add(item); await session.flush(); created_parameter_ids.append(item.PARAMETER_ID)
            parameters[code]=item
        surface_types={}; created_surface_type_ids=[]
        for code in ("INNER_HORIZONTAL","CONICAL","APPROACH","TAKE_OFF_CLIMB","TRANSITIONAL"):
            item=await session.scalar(select(OlsSurfaceType).where(OlsSurfaceType.CODE==code))
            if item is None:
                item=OlsSurfaceType(CODE=code,AZE_NAME=code,ENG_NAME=code,DESCRIPTION=None,STATUS_ID=active); session.add(item); await session.flush(); created_surface_type_ids.append(item.SURFACE_TYPE_ID)
            surface_types[code]=item
        standard_type=StandardType(CODE=f"OLS_{suffix}",AZE_NAME="OLS",ENG_NAME="OLS",DESCRIPTION="Test",STATUS_ID=active); session.add(standard_type); await session.flush()
        standard=Standard(STANDARD_TYPE_ID=standard_type.STANDARD_TYPE_ID,CODE=f"OLS_STD_{suffix}",AZE_NAME="OLS test",ENG_NAME="OLS test",EDITION="1",AMENDMENT=None,EFFECTIVE_DATE=date(2026,1,1),DESCRIPTION=None,STATUS_ID=active); session.add(standard)
        country=Country(AZE_NAME="Test",ENG_NAME="Test",ISO_CODE=f"O{suffix[:5].upper()}",STATUS_ID=active); session.add(country); await session.flush(); city=City(COUNTRY_ID=country.COUNTRY_ID,AZE_NAME="Test",ENG_NAME=f"OLS City {suffix}",STATUS_ID=active); icao=IcaoCode(ICAO_CODE=f"O{suffix[:3].upper()}",DESCRIPTION="Test",STATUS_ID=active); session.add_all([city,icao]); await session.flush()
        airport=Airport(ICAO_ID=icao.ICAO_ID,IATA_CODE=None,AZE_NAME="Test",ENG_NAME="OLS Airport",COUNTRY_ID=country.COUNTRY_ID,CITY_ID=city.CITY_ID,ELEVATION_M=100,ARP_GEOM=func.ST_GeomFromText("POINT(49.9 40.4)",4326),BOUNDARY_GEOM=func.ST_GeomFromText("POLYGON((49.8 40.3,50 40.3,50 40.5,49.8 40.5,49.8 40.3))",4326),STATUS_ID=active); session.add(airport); await session.flush()
        runway=Runway(AIR_ID=airport.AIR_ID,AZE_NAME="09/27",ENG_NAME="09/27",DESIGNATOR_1="09",DESIGNATOR_2="27",LENGTH_M=3000,WIDTH_M=45,GEOM=func.ST_GeomFromText("POLYGON((49.88 40.395,49.92 40.395,49.92 40.405,49.88 40.405,49.88 40.395))",4326),CENTERLINE_GEOM=func.ST_GeomFromText("LINESTRING(49.88 40.4,49.92 40.4)",4326),STATUS_ID=active); session.add(runway); await session.flush()
        strip=RunwayStrip(RUN_ID=runway.RUN_ID,LENGTH_M=3240,WIDTH_M=240,GEOM=func.ST_GeomFromText("POLYGON((49.878 40.399,49.922 40.399,49.922 40.401,49.878 40.401,49.878 40.399))",4326),STATUS_ID=active); session.add(strip)
        directions=[RunwayDirection(RUN_ID=runway.RUN_ID,DESIGNATOR="09",TRUE_BEARING_DEG=90,THRESHOLD_ELEVATION_M=100,THRESHOLD_GEOM=func.ST_GeomFromText("POINT(49.88 40.4)",4326),SLOPE_PCT=0,STATUS_ID=active),RunwayDirection(RUN_ID=runway.RUN_ID,DESIGNATOR="27",TRUE_BEARING_DEG=270,THRESHOLD_ELEVATION_M=100,THRESHOLD_GEOM=func.ST_GeomFromText("POINT(49.92 40.4)",4326),SLOPE_PCT=0,STATUS_ID=active)]; session.add_all(directions)
        user=User(USERNAME=username,EMAIL=f"{username}@example.com",PASSWORD_HASH=hash_password(password),FIRST_NAME="OLS",LAST_NAME="Admin",STATUS_ID=active); session.add(user); await session.flush(); session.add(UserRole(USER_ID=user.USER_ID,ROLE_ID=admin_role)); await session.flush()
        obstacle_type=ObstacleType(CODE=f"TOWER_{suffix}",AZE_NAME="Qüllə",ENG_NAME="Tower",DESCRIPTION="Violation test",STATUS_ID=active); session.add(obstacle_type); await session.flush()
        configs={}
        for code,surface_type in surface_types.items():
            item=StandardOlsSurface(STANDARD_ID=standard.STANDARD_ID,SURFACE_TYPE_ID=surface_type.SURFACE_TYPE_ID,DESCRIPTION=None,STATUS_ID=active); session.add(item); configs[code]=item
        await session.flush()
        values={"INNER_HORIZONTAL":{0:{"HORIZONTAL_OFFSET":4000,"HEIGHT":45}},"CONICAL":{0:{"HORIZONTAL_WIDTH":2000,"HEIGHT":100,"SLOPE":5}},"APPROACH":{0:{"START_DISTANCE":60,"INNER_EDGE":280,"DIVERGENCE":15},1:{"LENGTH":3000,"SLOPE":2},2:{"LENGTH":3600,"SLOPE":2.5},3:{"LENGTH":8400,"SLOPE":0}},"TAKE_OFF_CLIMB":{0:{"CLEARWAY":240,"INNER_EDGE":180,"DIVERGENCE":12.5,"FINAL_WIDTH":1200,"LENGTH":15000,"SLOPE":2}},"TRANSITIONAL":{0:{"SLOPE":14.3}}}
        for surface_code,sections in values.items():
            for section,section_values in sections.items():
                for parameter_code,value in section_values.items(): session.add(StandardOlsParameterValue(STANDARD_OLS_ID=configs[surface_code].STANDARD_OLS_ID,PARAMETER_ID=parameters[parameter_code].PARAMETER_ID,SECTION_NO=section,NUMERIC_VALUE=value,BOOLEAN_VALUE=None,DESCRIPTION=None,STATUS_ID=active))
        await session.commit()
        ids={"user":user.USER_ID,"runway":runway.RUN_ID,"directions":[d.RUN_DIR_ID for d in directions],"airport":airport.AIR_ID,"city":city.CITY_ID,"country":country.COUNTRY_ID,"icao":icao.ICAO_ID,"standard":standard.STANDARD_ID,"standard_type":standard_type.STANDARD_TYPE_ID,"obstacle_type":obstacle_type.OBSTACLE_TYPE_ID,"configs":{code:item.STANDARD_OLS_ID for code,item in configs.items()},"units":[meter.UNIT_ID,percent.UNIT_ID],"parameters":created_parameter_ids,"surface_types":created_surface_type_ids}
        try:
            token=login(username,password)
            status_code,result=generate(token,standard.STANDARD_ID,runway.RUN_ID); assert status_code==201 and result["generated_count"]==7
            count=await session.scalar(select(func.count(OlsSurface.OLS_SURFACE_ID)).where(OlsSurface.RUN_ID==runway.RUN_ID)); dimensions=await session.scalars(select(func.ST_NDims(OlsSurface.GEOM)).where(OlsSurface.RUN_ID==runway.RUN_ID)); validity=await session.scalars(select(func.ST_IsValid(OlsSurface.GEOM)).where(OlsSurface.RUN_ID==runway.RUN_ID)); assert count==7 and set(dimensions.all())=={3} and set(validity.all())=={True}
            first_direction = aliased(RunwayDirection)
            second_direction = aliased(RunwayDirection)
            threshold_distance = float(
                await session.scalar(
                    select(
                        func.ST_Distance(
                            first_direction.THRESHOLD_GEOM.cast(Geography),
                            second_direction.THRESHOLD_GEOM.cast(Geography),
                        )
                    )
                    .select_from(first_direction)
                    .join(second_direction, true())
                    .where(
                        first_direction.RUN_DIR_ID == ids["directions"][0],
                        second_direction.RUN_DIR_ID == ids["directions"][1],
                    )
                )
            )
            inner_area = float(
                await session.scalar(
                    select(func.ST_Area(func.ST_Transform(OlsSurface.GEOM, 32639)))
                    .where(
                        OlsSurface.STANDARD_OLS_ID
                        == ids["configs"]["INNER_HORIZONTAL"]
                    )
                )
            )
            conical_area = float(
                await session.scalar(
                    select(func.ST_Area(func.ST_Transform(OlsSurface.GEOM, 32639)))
                    .where(
                        OlsSurface.STANDARD_OLS_ID
                        == ids["configs"]["CONICAL"]
                    )
                )
            )
            expected_inner = math.pi * 4000**2 + 2 * 4000 * threshold_distance
            expected_outer = math.pi * 6000**2 + 2 * 6000 * threshold_distance
            assert abs(inner_area - expected_inner) / expected_inner < 0.02
            assert (
                abs(conical_area - (expected_outer - expected_inner))
                / (expected_outer - expected_inner)
                < 0.02
            )
            _,second=generate(token,standard.STANDARD_ID,runway.RUN_ID); assert second["generated_count"]==7; count=await session.scalar(select(func.count(OlsSurface.OLS_SURFACE_ID)).where(OlsSurface.RUN_ID==runway.RUN_ID)); assert count==7
            automatic_revision_count=await session.scalar(select(func.count()).select_from(OlsSurfaceRevision).where(OlsSurfaceRevision.OLS_SURFACE_ID==int(second["surfaces"][0]["ols_surface_id"]))); assert automatic_revision_count==2
            archived_status=await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME)=="archived")); archived_id=int(second["surfaces"][0]["ols_surface_id"]); await session.execute(__import__("sqlalchemy").update(OlsSurface).where(OlsSurface.RUN_ID==runway.RUN_ID).values(STATUS_ID=archived_status)); await session.commit()
            _,reactivated=generate(token,standard.STANDARD_ID,runway.RUN_ID,replace_existing=False); assert reactivated["generated_count"]==7 and int(reactivated["surfaces"][0]["ols_surface_id"])==archived_id
            obstacle_payload={"eng_name":"Penetrating tower","obstacle_type_id":ids["obstacle_type"],"ground_elevation_m":100,"object_height_m":60,"geometry":{"type":"Point","coordinates":[49.9,40.4]}}
            code,obstacle=call(f"/airports/{ids['airport']}/obstacles","POST",obstacle_payload,token); assert code==201; obstacle_id=int(obstacle["obstacle_id"])
            code,analysis=call(f"/obstacles/{obstacle_id}/analyze","POST",token=token); assert code==200 and analysis["has_violation"] and analysis["checked_surface_count"]>=1
            inner_violation=next(v for v in analysis["violations"] if v["surface_type"]=="INNER_HORIZONTAL"); assert abs(float(inner_violation["surface_elevation_m"])-145)<0.01 and abs(float(inner_violation["penetration_m"])-15)<0.01
            code,violation_list=call(f"/airports/{ids['airport']}/violations?surface_type=INNER_HORIZONTAL",token=token); assert code==200 and violation_list["total"]==1
            code,violation_summary=call(f"/airports/{ids['airport']}/reports/violations/summary",token=token); assert code==200 and violation_summary["affected_obstacles"]==1
            code,csv_report,content_type=call_text(f"/airports/{ids['airport']}/reports/violations.csv",token); assert code==200 and content_type=="text/csv" and "penetration_m" in csv_report and "Penetrating tower" in csv_report
            code,reanalysis=call(f"/obstacles/{obstacle_id}/analyze","POST",token=token); assert code==200 and len(reanalysis["violations"])==len(analysis["violations"])
            manual_payload={"standard_ols_id":ids["configs"]["APPROACH"],"air_id":ids["airport"],"run_id":ids["runway"],"run_dir_id":ids["directions"][0],"aze_name":"Manual yanaşma","eng_name":"Manual approach","geometry":{"type":"Polygon","coordinates":[[[49.87,40.39],[49.86,40.38],[49.88,40.38],[49.87,40.39]]]},"default_elevation_m":130}
            code,manual=call("/ols/manual","POST",manual_payload,token); assert code==201 and manual["generation_method"]=="MANUAL"; manual_id=int(manual["ols_surface_id"]); assert len(manual["geometry"]["coordinates"][0][0])==3
            code,manual_list=call(f"/ols/airports/{ids['airport']}/surfaces?generation_method=MANUAL",token=token); assert code==200 and manual_list["total"]==1
            code,canonical_list=call(f"/airports/{ids['airport']}/ols-surfaces?surface_type=APPROACH",token=token); assert code==200 and canonical_list["total"]==3 and all(item["standard_id"]==ids["standard"] for item in canonical_list["items"])
            code,geojson=call(f"/airports/{ids['airport']}/ols-surfaces/geojson?generation_method=MANUAL",token=token); assert code==200 and geojson["type"]=="FeatureCollection" and len(geojson["features"])==1
            code,summary=call(f"/airports/{ids['airport']}/ols-surfaces/summary",token=token); assert code==200 and summary["total"]==8 and summary["by_generation_method"]=={"AUTOMATIC":7,"MANUAL":1}
            code,canonical_detail=call(f"/ols-surfaces/{manual_id}",token=token); assert code==200 and canonical_detail["ols_surface_id"]==manual_id
            update_geometry={"type":"Polygon","coordinates":[[[49.87,40.39],[49.85,40.37],[49.89,40.37],[49.87,40.39]]]}
            code,updated=call(f"/ols/surfaces/{manual_id}","PATCH",{"eng_name":"Edited manual approach","geometry":update_geometry,"default_elevation_m":140},token); assert code==200 and updated["eng_name"]=="Edited manual approach" and float(updated["geometry"]["coordinates"][0][0][2])==140
            automatic_id=int(second["surfaces"][0]["ols_surface_id"]); code,_=call(f"/ols/surfaces/{automatic_id}","PATCH",{"eng_name":"Forbidden edit"},token); assert code==400
            code,revisions=call(f"/ols-surfaces/{manual_id}/revisions",token=token); assert code==200 and [item["revision_no"] for item in revisions]==[2,1] and revisions[0]["change_type"]=="UPDATE" and revisions[0]["created_by"]==ids["user"]
            code,first_revision=call(f"/ols-surfaces/{manual_id}/revisions/1",token=token); assert code==200 and first_revision["eng_name"]=="Manual approach" and float(first_revision["geometry"]["coordinates"][0][0][2])==130
            code,restored=call(f"/ols-surfaces/{manual_id}/revisions/1/restore","POST",{"note":"Restore original manual surface"},token); assert code==200 and restored["revision_no"]==3 and restored["change_type"]=="RESTORE"
            code,restored_surface=call(f"/ols-surfaces/{manual_id}",token=token); assert code==200 and restored_surface["eng_name"]=="Manual approach" and float(restored_surface["geometry"]["coordinates"][0][0][2])==130
            code,_=call(f"/ols/surfaces/{manual_id}/status","PATCH",{"status_id":active},token); assert code==204
            code,_=call(f"/ols/surfaces/{manual_id}","DELETE",token=token); assert code==204
            code,archived=call(f"/ols/surfaces/{manual_id}",token=token); assert code==200 and archived["status"].lower()=="archived"
        finally:
            await session.execute(delete(OlsViolation).where(OlsViolation.OBSTACLE_ID.in_(select(Obstacle.OBSTACLE_ID).where(Obstacle.AIR_ID==ids["airport"])))); await session.execute(delete(Obstacle).where(Obstacle.AIR_ID==ids["airport"])); await session.execute(delete(ObstacleType).where(ObstacleType.OBSTACLE_TYPE_ID==ids["obstacle_type"]));
            await session.execute(delete(OlsSurface).where(OlsSurface.RUN_ID==ids["runway"])); await session.execute(delete(Standard).where(Standard.STANDARD_ID==ids["standard"])); await session.execute(delete(Runway).where(Runway.RUN_ID==ids["runway"])); await session.execute(delete(Airport).where(Airport.AIR_ID==ids["airport"])); await session.execute(delete(User).where(User.USER_ID==ids["user"])); await session.execute(delete(City).where(City.CITY_ID==ids["city"])); await session.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID==ids["icao"])); await session.execute(delete(Country).where(Country.COUNTRY_ID==ids["country"])); await session.execute(delete(StandardType).where(StandardType.STANDARD_TYPE_ID==ids["standard_type"])); await session.execute(delete(OlsParameter).where(OlsParameter.PARAMETER_ID.in_(ids["parameters"]))); await session.execute(delete(OlsSurfaceType).where(OlsSurfaceType.SURFACE_TYPE_ID.in_(ids["surface_types"]))); await session.execute(delete(Unit).where(Unit.UNIT_ID.in_(ids["units"]))); await session.commit()
    await close_database(); print("Automatic OLS generation smoke test passed.")


if __name__=="__main__": asyncio.run(main())
