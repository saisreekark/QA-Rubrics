#!/usr/bin/env python3
"""Render HIERARCHY_CONFIG (notebook cell 4) into per-framework Mermaid trees.

Output: docs/hierarchy-viz.md — one collapsible <details> section per
framework, each containing a `graph TD` block. GitHub renders Mermaid
natively in markdown previews.

Regenerate after any HIERARCHY_CONFIG change:
    python3 scripts/render_hierarchy.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluator.config import FRAMEWORKS  # noqa: E402
from evaluator.hierarchy import load_hierarchy  # noqa: E402

OUT_PATH = ROOT / "docs" / "hierarchy-viz.md"
_id_counter = 0


def _node_id(prefix: str, label: str) -> str:
    global _id_counter
    _id_counter += 1
    slug = re.sub(r"\W+", "_", label).strip("_")[:30] or "x"
    return f"{prefix}_{_id_counter}_{slug}"


def _esc(label: str) -> str:
    return label.strip().replace('"', "'")[:120]


def _walk_l3(parent_id: str, l3s, lines: list[str]) -> int:
    leaves = 0
    if isinstance(l3s, list):
        for l3 in l3s:
            lid = _node_id("L3", l3)
            lines.append(f'    {lid}["{_esc(l3)}"]')
            lines.append(f"    {parent_id} --> {lid}")
            leaves += 1
    elif isinstance(l3s, dict):
        for l3, deeper in l3s.items():
            lid = _node_id("L3", l3)
            lines.append(f'    {lid}(["{_esc(l3)}"])')
            lines.append(f"    {parent_id} --> {lid}")
            if isinstance(deeper, list):
                for leaf in deeper:
                    leaf_id = _node_id("L4", leaf)
                    lines.append(f'    {leaf_id}["{_esc(leaf)}"]')
                    lines.append(f"    {lid} --> {leaf_id}")
                    leaves += 1
    return leaves


def render_framework(framework: str) -> tuple[str, int, int, int]:
    subtree = load_hierarchy(framework)
    lines = ["graph TD"]
    root_id = _node_id("FW", framework)
    lines.append(f'    {root_id}(["{framework}"])')
    n_l1 = n_l2 = n_l3 = 0
    for l1, l2_map in subtree.items():
        l1_id = _node_id("L1", l1)
        lines.append(f'    {l1_id}(["{_esc(l1)}"])')
        lines.append(f"    {root_id} --> {l1_id}")
        n_l1 += 1
        if isinstance(l2_map, dict):
            for l2, l3s in l2_map.items():
                l2_id = _node_id("L2", l2)
                lines.append(f'    {l2_id}(["{_esc(l2)}"])')
                lines.append(f"    {l1_id} --> {l2_id}")
                n_l2 += 1
                n_l3 += _walk_l3(l2_id, l3s, lines)
    return "\n".join(lines), n_l1, n_l2, n_l3


def main() -> None:
    sections: list[str] = []
    totals = [0, 0, 0]
    for fw in FRAMEWORKS:
        global _id_counter
        _id_counter = 0
        body, n_l1, n_l2, n_l3 = render_framework(fw)
        totals[0] += n_l1
        totals[1] += n_l2
        totals[2] += n_l3
        sections.append(
            f"<details>\n<summary><b>{fw}</b> — L1={n_l1} · L2={n_l2} · L3={n_l3}"
            f"</summary>\n\n```mermaid\n{body}\n```\n\n</details>\n"
        )
    header = (
        "# Hierarchy visualization\n\n"
        "Mermaid trees rendered from `HIERARCHY_CONFIG` "
        "(`notebook/content.ipynb` cell 4). Regenerate after any change "
        "with `python3 scripts/render_hierarchy.py`.\n\n"
        f"**Totals across 6 frameworks**: L1={totals[0]} · L2={totals[1]} "
        f"· L3={totals[2]}.\n\n"
        "GitHub renders Mermaid natively; collapse/expand each framework "
        "below.\n\n"
    )
    OUT_PATH.write_text(header + "\n".join(sections))
    print(f"wrote {OUT_PATH.relative_to(ROOT)} "
          f"(L1={totals[0]}, L2={totals[1]}, L3={totals[2]})")


if __name__ == "__main__":
    main()
