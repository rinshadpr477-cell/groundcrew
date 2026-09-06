import json
import os
import time

import httpx
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface").lower()  # "huggingface" | "ollama"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

if LLM_PROVIDER == "huggingface":
    HF_TOKEN = os.getenv("HF_TOKEN")
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set — check apps/api/.env")
    _DEFAULT_MODEL = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    _hf_client = InferenceClient(api_key=HF_TOKEN)
elif LLM_PROVIDER == "ollama":
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    _DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
else:
    raise RuntimeError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}' — use 'huggingface' or 'ollama'")


def _call_huggingface(system_prompt: str, user_prompt: str, model: str) -> str:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _hf_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except HfHubHTTPError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status is not None and status < 500:
                raise
            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(f"  (HF call failed: {exc}; retrying in {wait_seconds}s, attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
    raise last_error


def _call_ollama(system_prompt: str, user_prompt: str, model: str) -> str:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {OLLAMA_URL} — is the Ollama app running "
                "(check for its icon in the Windows system tray)?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500:
                raise
            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(f"  (Ollama call failed: {exc}; retrying in {wait_seconds}s, attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
    raise last_error


def _call_model(system_prompt: str, user_prompt: str, model: str) -> str:
    if LLM_PROVIDER == "ollama":
        return _call_ollama(system_prompt, user_prompt, model)
    return _call_huggingface(system_prompt, user_prompt, model)


def chat_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    content = _call_model(system_prompt, user_prompt, model or _DEFAULT_MODEL)
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON:\n{content}") from exc