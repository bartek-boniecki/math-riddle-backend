# tests/generate_example.py
# Prosty lokalny test — teraz działa zarówno jako:
#   python -m tests.generate_example
# jak i (dla wygody) bezpośrednio:
#   python tests/generate_example.py

import os
import sys
import json

# --- Fallback dla uruchomienia plikowego: dopisz katalog projektu do sys.path ---
if __package__ is None and __name__ == "__main__":
    # katalog /tests
    _here = os.path.dirname(os.path.abspath(__file__))
    # katalog projektu = rodzic /tests
    _root = os.path.dirname(_here)
    if _root not in sys.path:
        sys.path.insert(0, _root)

from app.schemas import GenerateRequest
from app.generator import generate_batch

if __name__ == "__main__":
    req = GenerateRequest(
        branch="Combinatorics",
        school_level="high school (grades 9-12)",
        scenario="sport",
        seed=1234,
    )
    out = generate_batch(req)
    print(json.dumps([c.model_dump() for c in out], ensure_ascii=False, indent=2))
