from datetime import datetime, timezone
from pydantic import BaseModel, HttpUrl

class Source(BaseModel):
    original_url: HttpUrl
    final_url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str = ''
    text: str = ''
    retrieved_at: datetime = datetime.now(timezone.utc)
    status_code: int = 200
    error: str | None = None
