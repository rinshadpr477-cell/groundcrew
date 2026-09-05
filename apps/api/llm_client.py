import json
import os
import time

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN is not set — check apps/api/.env")

LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

_client = InferenceClient(api_key=HF_TOKEN)

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def _call_model(system_prompt: str, user_prompt: str, model: str) -> str:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _client.chat.completions.create(
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
                raise  # client error (bad request, bad model) — retrying won't help
            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(f"  (LLM call failed: {exc}; retrying in {wait_seconds}s, attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
    raise last_error


def chat_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """Calls the LLM and parses its reply as JSON."""
    content = _call_model(system_prompt, user_prompt, model or LLM_MODEL)

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON:\n{content}") from exc