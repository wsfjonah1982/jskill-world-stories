"""Find the my-world skill (its worldlib.py is the shared world library) and make it importable.

The skill is looked up at the env var MY_WORLD_DIR, else next to this skill (…/skill/my-world).
"""
import os
import sys
from pathlib import Path

MW = Path(os.environ.get("MY_WORLD_DIR", Path(__file__).resolve().parents[2] / "my-world"))
if not (MW / "scripts" / "worldlib.py").is_file():
    sys.exit(f"DEPENDENCY ERROR [SKILL-MY-WORLD]: Skill 'my-world' not found at {MW}. Install it there or set MY_WORLD_DIR.")
sys.path.insert(0, str(MW / "scripts"))

import pagenav  # noqa: E402,F401
import worldlib as wl  # noqa: E402,F401
