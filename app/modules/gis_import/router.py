from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.dependencies import EditorUser
from app.modules.gis_import.importer import GisImportError, ShapefilePreviewer
from app.modules.gis_import.schemas import ShapefilePreviewResponse


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
