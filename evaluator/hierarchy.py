"""Pull HIERARCHY_CONFIG out of notebook/content.ipynb cell 4.

Single source of truth for the rubric is the live notebook. The evaluator
parses cell 4, evaluates the ``HIERARCHY_CONFIG`` literal, and caches the
parsed dict on disk to keep CLI runs fast.

If/when HIERARCHY_CONFIG is lifted into a standalone JSON, point
``load_hierarchy`` at that file instead — no caller change required.
"""

from __future__ import annotations

import ast
import json
from typing import Any

from .config import FRAMEWORKS, HIERARCHY_CACHE, NOTEBOOK_PATH


def _extract_hierarchy_literal() -> dict[str, Any]:
    nb = json.loads(NOTEBOOK_PATH.read_text())
    cell4 = "".join(nb["cells"][4]["source"])
    tree = ast.parse(cell4)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "HIERARCHY_CONFIG"
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("HIERARCHY_CONFIG not found in notebook cell 4")


def _load_full_hierarchy(refresh: bool = False) -> dict[str, Any]:
    if HIERARCHY_CACHE.exists() and not refresh:
        nb_mtime = NOTEBOOK_PATH.stat().st_mtime
        cache_mtime = HIERARCHY_CACHE.stat().st_mtime
        if cache_mtime >= nb_mtime:
            return json.loads(HIERARCHY_CACHE.read_text())
    hierarchy = _extract_hierarchy_literal()
    HIERARCHY_CACHE.write_text(json.dumps(hierarchy, indent=2))
    return hierarchy


def load_hierarchy(framework: str, refresh: bool = False) -> dict[str, Any]:
    if framework not in FRAMEWORKS:
        raise ValueError(f"Unknown framework {framework!r}; expected one of {FRAMEWORKS}")
    full = _load_full_hierarchy(refresh=refresh)
    if framework not in full:
        raise RuntimeError(
            f"Framework {framework!r} not present in HIERARCHY_CONFIG; "
            "cell 4 of the notebook may be out of date."
        )
    return full[framework]


def render_excerpt(framework: str, refresh: bool = False) -> str:
    """Flatten the per-framework subtree into a prompt-friendly bulleted list."""
    subtree = load_hierarchy(framework, refresh=refresh)
    lines: list[str] = []
    for l1, l2_map in subtree.items():
        lines.append(f"- L1: {l1}")
        if isinstance(l2_map, dict):
            for l2, l3s in l2_map.items():
                lines.append(f"  - L2: {l2}")
                if isinstance(l3s, list):
                    for l3 in l3s:
                        lines.append(f"    - L3: {l3}")
                elif isinstance(l3s, dict):
                    for l3, deeper in l3s.items():
                        lines.append(f"    - L3: {l3}")
                        if isinstance(deeper, list):
                            for leaf in deeper:
                                lines.append(f"      - {leaf}")
    return "\n".join(lines)
