"""Regression of automatic OLS generation against the Lankaran ArcGIS reference.

The ArcGIS layers in ``data/reference/lankaran_ols_arcgis.zip`` (EPSG:32639)
supply the actual Strip and Clearways and the expected OLS partition. The
runway, thresholds and standard parameters are the official UBBL/AIP values.

Known reference properties (see the comparison report):
* along-axis distances are compressed by k = drawn runway / AIP length
  (3290.177 / 3300), so far ends differ by up to ``length * (1 - k)``;
* Inner Horizontal / Conical arcs are polylines up to ~3 m inside the true
  circle, and some vertices are drafted by hand (e.g. Transitional SE apex).
All metrics are evaluated in EPSG:32639.
"""

import asyncio
import functools
import io
import itertools
import json
import zipfile
from datetime import date
from pathlib import Path
from uuid import uuid4

import shapefile
from sqlalchemy import delete, func, select

import app.models  # noqa: F401 - register complete SQLAlchemy metadata
from app.core.database import AsyncSessionFactory, close_database
from app.modules.airports.models import Airport, City, Country, IcaoCode, Status
from app.modules.ols.models import OlsParameter, OlsSurface, OlsSurfaceType, Standard, StandardOlsParameterValue, StandardOlsSurface, StandardType, Unit
from app.modules.ols.service import AutomaticOlsService
from app.modules.runways.models import Runway, RunwayArea, RunwayAreaType, RunwayDirection, RunwayStrip

REFERENCE = Path(__file__).resolve().parents[1] / "data" / "reference" / "lankaran_ols_arcgis.zip"
SRID = 32639
AIP_LENGTH_M = 3300.0
LAYERS = {
    ("APPROACH", "15"): ["approach_15"], ("APPROACH", "33"): ["approach_33"],
    ("TAKE_OFF_CLIMB", "15"): ["takeoff_15"], ("TAKE_OFF_CLIMB", "33"): ["takeoff_33"],
    ("INNER_HORIZONTAL", None): ["inner_horizontal"], ("CONICAL", None): ["conical"],
    ("TRANSITIONAL", None): ["transitional_left", "transitional_right"],
}
# Expected components: Approach = two side bands near the Strip + one outer
# part (the reference additionally splits it at the 6660 m section end).
COMPONENTS = {"APPROACH": 3, "TAKE_OFF_CLIMB": 3, "INNER_HORIZONTAL": 1, "CONICAL": 2, "TRANSITIONAL": 2}
STANDARD = {
    "INNER_HORIZONTAL": {0: {"HORIZONTAL_OFFSET": 4000, "HEIGHT": 45}},
    "CONICAL": {0: {"HORIZONTAL_WIDTH": 2000, "HEIGHT": 100, "SLOPE": 5}},
    "APPROACH": {0: {"START_DISTANCE": 60, "INNER_EDGE": 280, "DIVERGENCE": 15}, 1: {"LENGTH": 3000, "SLOPE": 2, "END_WIDTH": 1180}, 2: {"LENGTH": 3600, "SLOPE": 2.5, "END_WIDTH": 2260}, 3: {"LENGTH": 8400, "SLOPE": 0, "END_WIDTH": 4780}},
    "TAKE_OFF_CLIMB": {0: {"CLEARWAY": 240, "INNER_EDGE": 180, "DIVERGENCE": 12.5, "FINAL_WIDTH": 1200, "LENGTH": 15000, "SLOPE": 2}},
    "TRANSITIONAL": {0: {"SLOPE": 14.285714}},
}


def reference_layers() -> dict[str, list[dict]]:
    layers: dict[str, list[dict]] = {}
    with zipfile.ZipFile(REFERENCE) as archive:
        names = {Path(name).stem for name in archive.namelist() if name.endswith(".shp")}
        for name in names:
            reader = shapefile.Reader(shp=io.BytesIO(archive.read(f"{name}.shp")), shx=io.BytesIO(archive.read(f"{name}.shx")), dbf=io.BytesIO(archive.read(f"{name}.dbf")))
            layers[name] = [shape.__geo_interface__ for shape in reader.shapes()]
    return layers


def metric(geojson: dict):
    return func.ST_Force2D(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geojson)), SRID))


def union(geometries):
    return functools.reduce(func.ST_Union, geometries)


def metric_union(features: list[dict]):
    return union([metric(feature) for feature in features])


async def main() -> None:
    reference = reference_layers()
    suffix = uuid4().hex[:7]
    async with AsyncSessionFactory() as session:
        active = await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active"))
        clearway_type = await session.scalar(select(RunwayAreaType.AREA_TYPE_ID).where(RunwayAreaType.CODE == "CWY"))
        assert active and clearway_type
        strip = metric(reference["strip"][0])
        # Runway centreline from the runway pavement (Strip hole).
        hole = func.ST_MakePolygon(func.ST_InteriorRingN(strip, 1))
        envelope = json.loads(await session.scalar(select(func.ST_AsGeoJSON(func.ST_OrientedEnvelope(hole)))))["coordinates"][0][:4]
        edges = sorted(((envelope[i], envelope[(i + 1) % 4]) for i in range(4)), key=lambda edge: (edge[0][0] - edge[1][0]) ** 2 + (edge[0][1] - edge[1][1]) ** 2)[:2]
        ends = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in edges]
        centerline = metric({"type": "LineString", "coordinates": ends})
        runway_length = float(await session.scalar(select(func.ST_Length(centerline))))
        k = runway_length / AIP_LENGTH_M
        wgs84 = lambda geometry: func.ST_Transform(geometry, 4326)  # noqa: E731

        created: dict = {"parameters": [], "surface_types": []}
        meter = Unit(CODE=f"M_{suffix}", SYMBOL="m", AZE_NAME="Metr", ENG_NAME="Meter", DESCRIPTION=None, STATUS_ID=active)
        percent = Unit(CODE=f"P_{suffix}", SYMBOL="%", AZE_NAME="Faiz", ENG_NAME="Percent", DESCRIPTION=None, STATUS_ID=active)
        session.add_all([meter, percent]); await session.flush()
        parameters = {}
        for code in {parameter for sections in STANDARD.values() for values in sections.values() for parameter in values}:
            item = await session.scalar(select(OlsParameter).where(OlsParameter.CODE == code))
            if item is None:
                item = OlsParameter(CODE=code, AZE_NAME=code, ENG_NAME=code, UNIT_ID=(percent if code in {"SLOPE", "DIVERGENCE"} else meter).UNIT_ID, DESCRIPTION=None, STATUS_ID=active)
                session.add(item); await session.flush(); created["parameters"].append(item.PARAMETER_ID)
            parameters[code] = item
        standard_type = StandardType(CODE=f"OLS_{suffix}", AZE_NAME="OLS", ENG_NAME="OLS", DESCRIPTION="Lankaran reference", STATUS_ID=active)
        session.add(standard_type); await session.flush()
        standard = Standard(STANDARD_TYPE_ID=standard_type.STANDARD_TYPE_ID, CODE=f"LNK_{suffix}", AZE_NAME="Lankaran", ENG_NAME="Lankaran", EDITION="1", AMENDMENT=None, EFFECTIVE_DATE=date(2026, 1, 1), DESCRIPTION=None, STATUS_ID=active)
        session.add(standard); await session.flush()
        for code, sections in STANDARD.items():
            surface_type = await session.scalar(select(OlsSurfaceType).where(OlsSurfaceType.CODE == code))
            if surface_type is None:
                surface_type = OlsSurfaceType(CODE=code, AZE_NAME=code, ENG_NAME=code, DESCRIPTION=None, STATUS_ID=active)
                session.add(surface_type); await session.flush(); created["surface_types"].append(surface_type.SURFACE_TYPE_ID)
            config = StandardOlsSurface(STANDARD_ID=standard.STANDARD_ID, SURFACE_TYPE_ID=surface_type.SURFACE_TYPE_ID, DESCRIPTION=None, STATUS_ID=active)
            session.add(config); await session.flush()
            for section, values in sections.items():
                for parameter, value in values.items():
                    session.add(StandardOlsParameterValue(STANDARD_OLS_ID=config.STANDARD_OLS_ID, PARAMETER_ID=parameters[parameter].PARAMETER_ID, SECTION_NO=section, NUMERIC_VALUE=value, BOOLEAN_VALUE=None, DESCRIPTION=None, STATUS_ID=active))
        country = Country(AZE_NAME="Test", ENG_NAME="Test", ISO_CODE=f"L{suffix[:5].upper()}", STATUS_ID=active); session.add(country); await session.flush()
        city = City(COUNTRY_ID=country.COUNTRY_ID, AZE_NAME="Test", ENG_NAME=f"Lankaran {suffix}", STATUS_ID=active)
        icao = IcaoCode(ICAO_CODE=f"L{suffix[:3].upper()}", DESCRIPTION="Lankaran reference test", STATUS_ID=active)
        session.add_all([city, icao]); await session.flush()
        airport = Airport(ICAO_ID=icao.ICAO_ID, IATA_CODE=None, AZE_NAME="Lənkəran", ENG_NAME="Lankaran reference", COUNTRY_ID=country.COUNTRY_ID, CITY_ID=city.CITY_ID, ELEVATION_M=-11, ARP_GEOM=func.ST_SetSRID(func.ST_MakePoint(48.8063888889, 38.7586111111), 4326), BOUNDARY_GEOM=wgs84(func.ST_Envelope(strip)), STATUS_ID=active)
        session.add(airport); await session.flush()
        runway = Runway(AIR_ID=airport.AIR_ID, AZE_NAME="15/33", ENG_NAME="15/33", DESIGNATOR_1="15", DESIGNATOR_2="33", LENGTH_M=AIP_LENGTH_M, WIDTH_M=45, GEOM=wgs84(hole), CENTERLINE_GEOM=wgs84(centerline), STATUS_ID=active)
        session.add(runway); await session.flush()
        session.add(RunwayStrip(RUN_ID=runway.RUN_ID, LENGTH_M=3420, WIDTH_M=280, GEOM=wgs84(strip), STATUS_ID=active))
        directions = {
            "15": RunwayDirection(RUN_ID=runway.RUN_ID, DESIGNATOR="15", TRUE_BEARING_DEG=151.03, THRESHOLD_ELEVATION_M=-15.85, THRESHOLD_GEOM=func.ST_SetSRID(func.ST_MakePoint(48.7971222222, 38.7717194444), 4326), SLOPE_PCT=0.16, STATUS_ID=active),
            "33": RunwayDirection(RUN_ID=runway.RUN_ID, DESIGNATOR="33", TRUE_BEARING_DEG=331.03, THRESHOLD_ELEVATION_M=-10.668, THRESHOLD_GEOM=func.ST_SetSRID(func.ST_MakePoint(48.8155, 38.7457083333), 4326), SLOPE_PCT=-0.16, STATUS_ID=active),
        }
        session.add_all(directions.values()); await session.flush()
        for designator, direction in directions.items():
            session.add(RunwayArea(RUN_ID=runway.RUN_ID, RUN_DIR_ID=direction.RUN_DIR_ID, AREA_TYPE_ID=clearway_type, LENGTH_M=240, WIDTH_M=160, GEOM=wgs84(metric(reference[f"clearway_{designator}"][0])), STATUS_ID=active))
        await session.commit()
        ids = {"runway": runway.RUN_ID, "airport": airport.AIR_ID, "city": city.CITY_ID, "country": country.COUNTRY_ID, "icao": icao.ICAO_ID, "standard": standard.STANDARD_ID, "standard_type": standard_type.STANDARD_TYPE_ID, "units": [meter.UNIT_ID, percent.UNIT_ID]}
        direction_codes = {direction.RUN_DIR_ID: designator for designator, direction in directions.items()}
        try:
            result = await AutomaticOlsService(session).generate(standard_id=ids["standard"], run_id=ids["runway"], replace_existing=True)
            assert result.generated_count == 7, result
            rows = (await session.execute(
                select(OlsSurfaceType.CODE, OlsSurface.RUN_DIR_ID, func.ST_Transform(func.ST_Force2D(OlsSurface.GEOM), SRID))
                .join(StandardOlsSurface, StandardOlsSurface.STANDARD_OLS_ID == OlsSurface.STANDARD_OLS_ID)
                .join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID)
                .where(OlsSurface.RUN_ID == ids["runway"])
            )).all()
            generated = {(code, direction_codes.get(direction_id)): geometry for code, direction_id, geometry in rows}
            assert set(generated) == set(LAYERS), generated.keys()
            # Along-axis allowance from the reference compression, plus the
            # reference arc/drafting deviations documented in the report.
            longest = max(STANDARD["APPROACH"][s]["LENGTH"] for s in (1, 2, 3)) + 6600
            limits = {"APPROACH": longest * (1 - k) + 1, "TAKE_OFF_CLIMB": STANDARD["TAKE_OFF_CLIMB"][0]["LENGTH"] * (1 - k) + 1, "INNER_HORIZONTAL": 25, "CONICAL": 25, "TRANSITIONAL": 35}
            report = []
            for key, names in LAYERS.items():
                expected = metric_union([feature for name in names for feature in reference[name]])
                actual = generated[key]
                ref_area, sys_area, hausdorff, symmetric, components = (await session.execute(select(
                    func.ST_Area(expected), func.ST_Area(actual), func.ST_HausdorffDistance(expected, actual),
                    func.ST_Area(func.ST_SymDifference(expected, actual)), func.ST_NumGeometries(actual),
                ))).one()
                report.append((key, round(ref_area, 1), round(sys_area, 1), round(hausdorff, 2), round(symmetric, 1), components))
                assert abs(sys_area - ref_area) / ref_area < 0.005, report[-1]
                assert symmetric / ref_area < 0.03, report[-1]
                assert hausdorff <= limits[key[0]], (report[-1], limits[key[0]])
                assert components == COMPONENTS[key[0]], report[-1]
            for (first_key, first), (second_key, second) in itertools.combinations(generated.items(), 2):
                overlap = float(await session.scalar(select(func.ST_Area(func.ST_Intersection(first, second)))))
                assert overlap < 0.1, (first_key, second_key, overlap)
            # No topology gap: OLS + Strip + Clearways leave only the runway pavement uncovered.
            covered = union([*generated.values(), strip, *(metric(reference[f"clearway_{d}"][0]) for d in ("15", "33"))])
            holes = func.ST_Difference(func.ST_MakePolygon(func.ST_ExteriorRing(func.ST_GeometryN(covered, 1))), covered)
            gap_area, pavement = (await session.execute(select(func.ST_Area(holes), func.ST_Area(hole)))).one()
            assert abs(gap_area - pavement) < 1.0, (gap_area, pavement)
            for row in report:
                print(*row)
        finally:
            await session.rollback()
            await session.execute(delete(OlsSurface).where(OlsSurface.RUN_ID == ids["runway"]))
            await session.execute(delete(Standard).where(Standard.STANDARD_ID == ids["standard"]))
            await session.execute(delete(Runway).where(Runway.RUN_ID == ids["runway"]))
            await session.execute(delete(Airport).where(Airport.AIR_ID == ids["airport"]))
            await session.execute(delete(City).where(City.CITY_ID == ids["city"]))
            await session.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID == ids["icao"]))
            await session.execute(delete(Country).where(Country.COUNTRY_ID == ids["country"]))
            await session.execute(delete(StandardType).where(StandardType.STANDARD_TYPE_ID == ids["standard_type"]))
            await session.execute(delete(OlsParameter).where(OlsParameter.PARAMETER_ID.in_(created["parameters"])))
            await session.execute(delete(OlsSurfaceType).where(OlsSurfaceType.SURFACE_TYPE_ID.in_(created["surface_types"])))
            await session.execute(delete(Unit).where(Unit.UNIT_ID.in_(ids["units"])))
            await session.commit()
    await close_database()
    print("Lankaran OLS reference smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
