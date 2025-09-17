# app/llm.py

"""
HF-only Llama 3.1 8B Instruct client with resilient chat + fallback.

- Enforces the single allowed model: meta-llama/Meta-Llama-3.1-8B-Instruct
- Accepts token from HF_TOKEN or HUGGINGFACEHUB_API_TOKEN
- Retries on transient 429/5xx
- Fallback to text_generation for older hub versions
- Robustly extracts content (handles list-of-chunks responses)
"""

import os
import time
import random
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

load_dotenv()

# --- MODEL ENFORCEMENT (requirement: ONLY this model via HF) ---
ALLOWED_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
ENV_MODEL = (os.getenv("LLM_MODEL") or ALLOWED_MODEL).strip()
if ENV_MODEL != ALLOWED_MODEL:
    raise RuntimeError(
        f"Model must be exactly '{ALLOWED_MODEL}'. Found '{ENV_MODEL}'. "
        "This app is restricted to Llama-3.1-8B-Instruct on Hugging Face."
    )
DEFAULT_MODEL = ALLOWED_MODEL

# Accept both env var names for convenience
_TOKEN_ENV_1 = os.getenv("HF_TOKEN", "").strip()
_TOKEN_ENV_2 = os.getenv("HUGGINGFACEHUB_API_TOKEN", "").strip()
HF_TOKEN = _TOKEN_ENV_1 or _TOKEN_ENV_2
if not HF_TOKEN:
    raise RuntimeError(
        "Brak tokenu HF. Ustaw zmienną środowiskową HF_TOKEN lub HUGGINGFACEHUB_API_TOKEN."
    )

HF_TIMEOUT = float(os.getenv("HF_TIMEOUT_S", "60"))

_client = InferenceClient(model=DEFAULT_MODEL, token=HF_TOKEN, timeout=HF_TIMEOUT)


def _chat_completion_safe(kwargs: Dict[str, Any]) -> Any:
    """Call client.chat_completion with retries; fallback to text_generation if needed."""
    last_err: Optional[Exception] = None
    for attempt in range(4):
        try:
            # huggingface_hub >= 0.24
            return _client.chat_completion(**kwargs)
        except AttributeError:
            # Older huggingface_hub – fallback
            return _text_generation_fallback(kwargs)
        except HfHubHTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                sleep_s = 0.7 * (2 ** attempt) + random.random() * 0.25
                time.sleep(sleep_s)
                last_err = e
                continue
            raise
        except Exception as e:
            sleep_s = 0.6 * (2 ** attempt) + random.random() * 0.2
            time.sleep(sleep_s)
            last_err = e
            continue
    if last_err:
        raise last_err


def _text_generation_fallback(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback: emulate chat via text_generation with a stitched prompt."""
    messages: List[Dict[str, str]] = kwargs.get("messages") or []
    temperature: Optional[float] = kwargs.get("temperature", 0.7)
    max_tokens: int = kwargs.get("max_tokens", 900)

    parts = []
    for m in messages:
        role = (m.get("role") or "").upper()
        content = m.get("content") or ""
        parts.append(f"{role}: {content}")
    prompt = "\n".join(parts) + "\nASSISTANT:"

    text = _client.text_generation(
        prompt,
        max_new_tokens=max_tokens,
        temperature=temperature or 0.7,
        do_sample=True,
        return_full_text=False,
        stop=["</s>", "\nUSER:", "\nSYSTEM:", "\nASSISTANT:"],
    )
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                }
            }
        ]
    }


def _flatten_content(content: Union[str, List[Any]]) -> str:
    """HF may return a string or a list of chunks; concatenate text fields safely."""
    if isinstance(content, str):
        return content
    out_parts: List[str] = []
    for chunk in content:
        if isinstance(chunk, str):
            out_parts.append(chunk)
        elif isinstance(chunk, dict):
            # common shapes: {"type":"text","text":"..."} or {"text":"..."}
            txt = chunk.get("text") or ""
            out_parts.append(str(txt))
        else:
            out_parts.append(str(chunk))
    return "".join(out_parts)


def _extract_content(resp: Any) -> str:
    """Support both object and dict response shapes, and list-of-chunks content."""
    # object style
    try:
        msg = resp.choices[0].message
        if isinstance(msg, dict):
            return _flatten_content(msg.get("content", ""))
        # huggingface objects often have .content attribute
        c = getattr(msg, "content", "")
        return _flatten_content(c)
    except Exception:
        pass

    # dict style
    try:
        msg = resp["choices"][0]["message"]
        return _flatten_content(msg.get("content", ""))
    except Exception:
        return str(resp)


def chat(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = 0.7,
    model: str = DEFAULT_MODEL,  # fixed, but kept for signature compatibility
    response_format: Optional[str] = None,  # ignored
    max_tokens: int = 900,
) -> str:
    """
    HF chat call restricted to Llama-3.1-8B-Instruct.

    Returns raw content string.
    """
    kwargs = dict(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens,
    )
    resp = _chat_completion_safe(kwargs)
    return _extract_content(resp)


def current_model_id() -> str:
    """Expose the enforced model id for /health."""
    return DEFAULT_MODEL
