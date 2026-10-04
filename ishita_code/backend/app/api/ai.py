from fastapi import APIRouter
from app.services.ai.ollama_client import ollama_client

router = APIRouter(tags=["system & ai"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "SENTINEL Content Intelligence API",
        "version": "1.0.0"
    }

@router.get("/ai/status")
async def ai_status():
    status_info = await ollama_client.check_health()
    return status_info
