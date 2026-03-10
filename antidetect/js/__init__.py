"""JavaScript stealth scripts loader.

Loads JS modules from files for cleaner code organization.
JS files are cached in memory after first load.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

JS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_js(name: str) -> str:
    """Load JavaScript file content by name.

    Args:
        name: JS file name without extension (e.g., 'utils', 'webgl')

    Returns:
        JavaScript code as string

    Raises:
        FileNotFoundError: If JS file doesn't exist
    """
    js_file = JS_DIR / f"{name}.js"
    return js_file.read_text(encoding="utf-8")


def load_all_js() -> dict[str, str]:
    """Load all JavaScript files from the js directory.

    Returns:
        Dict mapping filename (without extension) to content
    """
    return {f.stem: f.read_text(encoding="utf-8") for f in JS_DIR.glob("*.js")}


__all__ = ["JS_DIR", "load_all_js", "load_js"]
