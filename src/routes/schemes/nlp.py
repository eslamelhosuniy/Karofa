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

# New models for chat history support
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatAnswerRequest(BaseModel):
    text: str
    chat_history: Optional[List[ChatMessage]] = None
    session_entities: Optional[List[str]] = None
    limit: Optional[int] = 5

class TaggedChatAnswerRequest(BaseModel):
    text: str
    chat_history: Optional[List[ChatMessage]] = None
    session_entities: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    limit: Optional[int] = 5
