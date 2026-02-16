"""Load user links/constants for templates."""

import json
from pathlib import Path
from typing import Any


def load_links(work_dir: Path | None = None) -> dict[str, str]:
    """
    Load links from links.json in the given directory or cwd.
    Returns dict with keys: x, linkedin, github, portfolio, resume, sender_name.
    Missing keys return empty string.
    """
    dirs = [Path(work_dir)] if work_dir else []
    dirs.append(Path.cwd())

    for d in dirs:
        path = Path(d) / "links.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "x": str(data.get("x", "")),
                    "linkedin": str(data.get("linkedin", "")),
                    "github": str(data.get("github", "")),
                    "portfolio": str(data.get("portfolio", "")),
                    "resume": str(data.get("resume", "")),
                    "sender_name": str(data.get("sender_name", "")),
                }
            except (json.JSONDecodeError, TypeError):
                return _empty_links()

    return _empty_links()


def _empty_links() -> dict[str, str]:
    return {"x": "", "linkedin": "", "github": "", "portfolio": "", "resume": "", "sender_name": ""}
