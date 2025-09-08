# app/llm.py
import os
import time
import random
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, BadRequestError, RateLimitError, APIConnectionError, APITimeoutError

load_dotenv()

def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Brak OPENAI_API_KEY w środowisku. Uzupełnij .env lub zmienną środowiskową.")
    return OpenAI(api_key=api_key)

DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

def _safe_chat_create(kwargs: Dict[str, Any]):
    """
    Wykonuje wywołanie chat.completions z odpornością na:
    - unsupported_value dla temperature lub response_format (automatycznie usuwa i ponawia),
    - rate limit / timeout / problemy sieciowe (krótki backoff i retry).
    """
    client = get_openai_client()

    # zrobimy max 4 prób (pierwsza + do 3 retry)
    last_err: Optional[Exception] = None
    for attempt in range(4):
        try:
            return client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            msg = str(e).lower()
            # 1) temperatura nieobsługiwana przez model
            if "param" in msg and "temperature" in msg and "unsupported" in msg:
                kwargs.pop("temperature", None)
                # Spróbuj jeszcze raz bez temperature
                continue
            # 2) response_format nieobsługiwany przez model
            if "response_format" in msg and "unsupported" in msg:
                kwargs.pop("response_format", None)
                # Spróbuj jeszcze raz bez response_format
                continue
            # Inny błąd 400 — przerwij i pokaż przyczynę
            raise
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            # krótki backoff z lekkim jitterem
            sleep_s = 0.7 * (2 ** attempt) + random.random() * 0.2
            time.sleep(sleep_s)
            last_err = e
            continue
    if last_err:
        raise last_err

def chat(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = 0.7,
    model: str = DEFAULT_MODEL,
    response_format: Optional[str] = None,
) -> str:
    """
    Zwraca treść odpowiedzi (message.content) jako string.
    Bezpiecznie obsługuje niedozwolone temperature/response_format
    i retry dla błędów transient.
    """
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=messages,
    )
    # dołącz temperature tylko jeśli jest ustawione
    if temperature is not None:
        kwargs["temperature"] = temperature

    # response_format: "json_object" => {"type":"json_object"}
    if response_format == "json_object":
        kwargs["response_format"] = {"type": "json_object"}

    resp = _safe_chat_create(kwargs)
    return resp.choices[0].message.content or ""
