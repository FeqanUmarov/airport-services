"""Import every ORM model so Alembic can discover the complete metadata."""

from app.modules.airports.models import Airport, City, Country, IcaoCode, Status
from app.modules.auth.models import UserToken
from app.modules.dtm.models import DtmSource
from app.modules.declared_distances.models import DeclaredDistance
from app.modules.obstacles.models import Obstacle, ObstacleType, OlsViolation
from app.modules.ols.models import (
    OlsGenerationMethod,
    OlsParameter,
    OlsSurface,
    OlsSurfaceType,
    Standard,
    StandardOlsParameterValue,
    StandardOlsSurface,
    StandardType,
    Unit,
)
from app.modules.ols_revisions.models import OlsSurfaceRevision
from app.modules.runways.models import (
    Runway,
    RunwayArea,
    RunwayAreaType,
    RunwayDirection,
    RunwayStrip,
)
from app.modules.users.models import Role, User, UserRole

__all__ = [
    "Airport",
    "City",
    "Country",
    "DeclaredDistance",
    "DtmSource",
    "IcaoCode",
    "Obstacle",
    "ObstacleType",
    "OlsParameter",
    "OlsGenerationMethod",
    "OlsSurface",
    "OlsSurfaceType",
    "OlsViolation",
    "OlsSurfaceRevision",
    "Role",
    "Runway",
    "RunwayArea",
    "RunwayAreaType",
    "RunwayDirection",
    "RunwayStrip",
    "Standard",
    "StandardOlsParameterValue",
    "StandardOlsSurface",
    "StandardType",
    "Status",
    "Unit",
    "User",
    "UserRole",
    "UserToken",
]
