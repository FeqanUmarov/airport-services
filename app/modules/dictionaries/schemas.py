from pydantic import BaseModel


class DictionaryItem(BaseModel):
    id: int
    code: str | None = None
    aze_name: str | None = None
    eng_name: str | None = None
    description: str | None = None
    status_id: int | None = None
    parent_id: int | None = None
    symbol: str | None = None


class DictionaryListResponse(BaseModel):
    items: list[DictionaryItem]
    total: int
