from pydantic import BaseModel
from typing import Optional, Dict, Any

class EngineStatusResponse(BaseModel):
    online: bool
    model: str
    base_url: str
    latency_ms: Optional[float] = None
    detail: str = ""
