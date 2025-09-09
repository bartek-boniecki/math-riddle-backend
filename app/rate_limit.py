# app/rate_limit.py
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class SlidingWindowLimiter:
    """
    Bardzo lekki limiter na proces:
    - limit na minutę (okno przesuwne 60s)
    - limit dzienny (reset o północy UTC)
    Przechowuje minimalne dane: kolejkę timestampów (1m) + licznik dzienny.
    """

    def __init__(self, max_per_minute: int = 5, max_per_day: int = 50):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self._minute: Dict[str, Deque[float]] = defaultdict(deque)
        self._daily: Dict[str, Dict[str, int]] = defaultdict(lambda: {"day": "", "count": 0})

    def allow(self, key: str) -> Tuple[bool, str | None, int | None]:
        """Zwraca (czy_dozwolone, komunikat_bledu, retry_after_s)"""
        now = time.time()

        # --- okno 60s ---
        dq = self._minute[key]
        cutoff = now - 60.0
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self.max_per_minute:
            retry_after = max(1, int(dq[0] + 60 - now))
            return (
                False,
                f"Przekroczono limit {self.max_per_minute}/min dla tego adresu. Spróbuj ponownie za {retry_after} s.",
                retry_after,
            )

        # --- limit dzienny (UTC) ---
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        rec = self._daily[key]
        if rec["day"] != day:
            rec["day"] = day
            rec["count"] = 0
        if rec["count"] >= self.max_per_day:
            return (
                False,
                f"Przekroczono dzienny limit {self.max_per_day} zapytań dla tego adresu. Spróbuj jutro.",
                3600,  # hint
            )

        # --- zapis użycia ---
        dq.append(now)
        rec["count"] += 1
        return True, None, None
