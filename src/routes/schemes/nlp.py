from pydantic import BaseModel
from typing import Optional, List

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5

# New models for tagged single collection
class TaggedPushRequest(BaseModel):
    project_id: int
    tags: List[str]
    do_reset: Optional[int] = 0

class TaggedSearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    tags: Optional[List[str]] = None
