from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.database import check_database, close_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await check_database()
    yield
    await close_database()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)
app.include_router(api_router, prefix=settings.api_v1_prefix)
