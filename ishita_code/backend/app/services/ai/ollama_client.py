import asyncio
import httpx
import time
from typing import Dict, Any, Optional
from app.core.config import settings

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self.max_retries = settings.OLLAMA_MAX_RETRIES
        self.headers = {
            "ngrok-skip-browser-warning": "true",
            "User-Agent": "SENTINEL-Inference-Client/1.0",
            "Connection": "close"
        }

    async def check_health(self) -> Dict[str, Any]:
        """Verify connectivity to configured Ollama instance."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=self.headers, http2=False) as client:
                # 1. Test base tags or version endpoint
                resp = await client.get(f"{self.base_url}/api/tags")
                latency_ms = round((time.time() - start_time) * 1000, 2)
                
                if resp.status_code != 200:
                    return {
                        "online": False,
                        "model": self.model,
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                        "detail": f"Ollama returned HTTP status {resp.status_code}."
                    }
                
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                model_found = any(self.model.lower() in (m or "").lower() for m in models)
                
                return {
                    "online": True,
                    "model": self.model,
                    "model_available": model_found,
                    "available_models": models,
                    "base_url": self.base_url,
                    "latency_ms": latency_ms,
                    "detail": "Connected to Ollama engine." if model_found else f"Ollama is online but model '{self.model}' was not found in tags."
                }
        except httpx.ConnectTimeout:
            return {
                "online": False,
                "model": self.model,
                "base_url": self.base_url,
                "detail": "Connection timed out connecting to Ollama at " + self.base_url
            }
        except httpx.ConnectError:
            return {
                "online": False,
                "model": self.model,
                "base_url": self.base_url,
                "detail": "Could not connect to Ollama. Check OLLAMA_BASE_URL."
            }
        except Exception as e:
            return {
                "online": False,
                "model": self.model,
                "base_url": self.base_url,
                "detail": f"AI service diagnostic error: {type(e).__name__}"
            }

    async def generate_completion(self, system_prompt: str, user_prompt: str, json_format: bool = True) -> str:
        """Call Ollama /api/generate with strict error handling."""
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for factual fidelity
                "top_p": 0.9,
            }
        }
        if json_format:
            payload["format"] = "json"

        timeout_config = httpx.Timeout(self.timeout, connect=25.0, read=self.timeout)
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout_config, headers=self.headers, http2=False) as client:
                    resp = await client.post(f"{self.base_url}/api/generate", json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "")
                    if not response_text:
                        raise RuntimeError("Ollama returned an empty response.")
                    return response_text

                # Retry gateway/transient failures. Other status codes are deterministic
                # request failures and must be returned immediately.
                if resp.status_code not in {429, 502, 503, 504}:
                    raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
                failure = RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                failure = RuntimeError(
                    f"AI engine unavailable. Check the Ollama connection ({self.base_url}): {str(exc)}"
                )
            except httpx.ReadTimeout:
                failure = RuntimeError(
                    f"AI generation timed out after {self.timeout}s waiting for Ollama response ({self.model}). "
                    "The model may be cold-starting or prompt is too long."
                )
            except RuntimeError:
                raise
            except Exception as exc:
                err_msg = str(exc) or type(exc).__name__
                raise RuntimeError(f"AI generation failed: {err_msg}") from exc

            if attempt < self.max_retries:
                # Bounded backoff for transient connection recovery.
                await asyncio.sleep(attempt + 1)
                continue
            raise failure

        # The loop always returns or raises; this satisfies static analyzers.
        raise RuntimeError("AI generation failed before an Ollama response was received.")

ollama_client = OllamaClient()
