from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dictionaries.repository import DictionaryRepository, DictionarySpec
from app.modules.dictionaries.schemas import DictionaryItem, DictionaryListResponse


class DictionaryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DictionaryRepository(session)

    @staticmethod
    def _value(record: object, field: str | None) -> object | None:
        return getattr(record, field, None) if field else None

    @classmethod
    def _item(cls, record: object, spec: DictionarySpec) -> DictionaryItem:
        return DictionaryItem(
            id=int(getattr(record, spec.id_field)),
            code=cls._value(record, spec.code_field),
            aze_name=getattr(record, "AZE_NAME", None),
            eng_name=getattr(record, "ENG_NAME", None),
            description=getattr(record, "DESCRIPTION", None),
            status_id=getattr(record, "STATUS_ID", None),
            parent_id=cls._value(record, spec.parent_field),
            symbol=cls._value(record, spec.symbol_field),
        )

    async def list_items(
        self,
        name: str,
        *,
        active_only: bool = True,
        parent_id: int | None = None,
    ) -> DictionaryListResponse:
        spec, records = await self.repository.list_items(
            name,
            active_only=active_only,
            parent_id=parent_id,
        )
        items = [self._item(record, spec) for record in records]
        return DictionaryListResponse(items=items, total=len(items))
