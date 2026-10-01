from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DatabaseSession
from app.modules.dictionaries.schemas import DictionaryListResponse
from app.modules.dictionaries.service import DictionaryService


router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])


async def dictionary_response(
    name: str,
    session: DatabaseSession,
    *,
    active_only: bool = True,
    parent_id: int | None = None,
) -> DictionaryListResponse:
    return await DictionaryService(session).list_items(
        name,
        active_only=active_only,
        parent_id=parent_id,
    )


@router.get("/statuses", response_model=DictionaryListResponse)
async def statuses(current: CurrentUser, session: DatabaseSession) -> DictionaryListResponse:
    del current
    return await dictionary_response("statuses", session, active_only=False)


@router.get("/roles", response_model=DictionaryListResponse)
async def roles(
    current: CurrentUser,
    session: DatabaseSession,
    active_only: bool = True,
) -> DictionaryListResponse:
    del current
    return await dictionary_response("roles", session, active_only=active_only)


@router.get("/countries", response_model=DictionaryListResponse)
async def countries(
    current: CurrentUser,
    session: DatabaseSession,
    active_only: bool = True,
) -> DictionaryListResponse:
    del current
    return await dictionary_response("countries", session, active_only=active_only)


@router.get("/cities", response_model=DictionaryListResponse)
async def cities(
    current: CurrentUser,
    session: DatabaseSession,
    country_id: int | None = Query(default=None, gt=0),
    active_only: bool = True,
) -> DictionaryListResponse:
    del current
    return await dictionary_response(
        "cities",
        session,
        active_only=active_only,
        parent_id=country_id,
    )


def dictionary_endpoint(name: str):
    async def endpoint(
        current: CurrentUser,
        session: DatabaseSession,
        active_only: bool = True,
    ) -> DictionaryListResponse:
        del current
        return await dictionary_response(name, session, active_only=active_only)

    return endpoint


router.add_api_route(
    "/icao-codes",
    dictionary_endpoint("icao-codes"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/standard-types",
    dictionary_endpoint("standard-types"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/ols-surface-types",
    dictionary_endpoint("ols-surface-types"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/ols-generation-methods",
    dictionary_endpoint("ols-generation-methods"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/units",
    dictionary_endpoint("units"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/ols-parameters",
    dictionary_endpoint("ols-parameters"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/obstacle-types",
    dictionary_endpoint("obstacle-types"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
router.add_api_route(
    "/runway-area-types",
    dictionary_endpoint("runway-area-types"),
    methods=["GET"],
    response_model=DictionaryListResponse,
)
