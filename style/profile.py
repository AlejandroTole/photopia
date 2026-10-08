"""
PHOTOIA - Style Profile (Phase 3 Placeholder)
Personal style preferences and feedback learning.
"""
from pathlib import Path
import json
from typing import Dict, Any


DEFAULT_STYLE = {
    "look": "natural_balanced",
    "contrast_preference": 1.5,
    "warmth_preference": 0.0,
    "history": [],
}


def load_style_profile(profile_path: Path = Path("style_profile.json")) -> Dict[str, Any]:
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_STYLE.copy()
