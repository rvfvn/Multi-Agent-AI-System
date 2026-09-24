from typing import Any, Optional
from pydantic import BaseModel

class TaskRequest(BaseModel):
    question: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None 
    error: Optional[str] = None 