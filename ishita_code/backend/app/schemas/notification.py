from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    link: str = ""
    type: str = "info"
    read: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
