import os
import json
from typing import Dict, Any


def load_config(path: str) -> Dict[str, Any]:
    """Helper function to load configuration json."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
