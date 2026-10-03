import json
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError

from app.core.dependencies import DatabaseSession, EditorUser
from app.modules.gis_import.importer import GisImportError, ShapefilePreviewer
from app.modules.gis_import.schemas import ShapefileImportMetadata, ShapefileImportResponse, ShapefilePreviewResponse
from app.modules.gis_import.service import ShapefileImportService
from app.modules.gis_import.exporter import AirportShapefileExporter
from app.modules.ols.service import OlsNotFoundError, OlsValidationError
from app.modules.runways.service import RunwayConflictError, RunwayNotFoundError, RunwayValidationError


router = APIRouter(prefix="/gis-import", tags=["gis-import"])


@router.post("/shapefile/preview", response_model=ShapefilePreviewResponse)
async def preview_shapefile(editor: EditorUser, file: UploadFile = File(...)) -> ShapefilePreviewResponse:
    del editor
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="A .zip Shapefile archive is required")
    try:
        return ShapefilePreviewer().run(await file.read(), file.filename)
    except GisImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/shapefile/import", response_model=ShapefileImportResponse, status_code=201)
async def import_shapefile(editor: EditorUser, session: DatabaseSession, metadata: str = Form(...), file: UploadFile = File(...)) -> ShapefileImportResponse:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="A .zip Shapefile archive is required")
    try:
        parsed=ShapefileImportMetadata.model_validate(json.loads(metadata))
        return await ShapefileImportService(session).import_archive(await file.read(),file.filename,parsed,editor.user.USER_ID)
    except (json.JSONDecodeError,ValidationError) as exc:
        raise HTTPException(status_code=422,detail="Import metadata is invalid") from exc
    except (GisImportError,RunwayConflictError,RunwayNotFoundError,RunwayValidationError,OlsNotFoundError,OlsValidationError) as exc:
        await session.rollback()
        raise HTTPException(status_code=400,detail=str(exc)) from exc


@router.get("/airports/{air_id}/shapefile/export")
async def export_airport_shapefiles(air_id: int, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try: content=await AirportShapefileExporter(session).export(air_id)
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc
    return Response(content=content,media_type="application/zip",headers={"Content-Disposition":f'attachment; filename="airport_{air_id}_gis_layers.zip"'})
