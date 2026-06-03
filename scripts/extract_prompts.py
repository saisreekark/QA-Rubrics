#!/usr/bin/env python3
"""Extract prompt definitions from notebook/content.ipynb cell 5 into prompts/*.md.

Each NAME_PROMPT triple-quoted block becomes a separate markdown file at
prompts/<framework>/<agent>.md with YAML frontmatter so injection is
deterministic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_PATH = ROOT / "notebook" / "content.ipynb"
PROMPTS_DIR = ROOT / "prompts"

PROMPT_BLOCK_RE = re.compile(
    r'^(?P<name>[A-Z][A-Z0-9_]*_PROMPT)\s*=\s*"""(?P<body>.*?)"""',
    re.MULTILINE | re.DOTALL,
)

FRAMEWORK_MAP = {
    "REOPEN": "reopen",
    "TTR": "ttr",
    "ESCALATION": "escalation",
    "DSAT": "dsat",
    "QUALITY": "quality",
    "WORKFLOW": "workflow",
    "HIERARCHY": "hierarchy",
}


def parse_name(prompt_name: str) -> tuple[str, str]:
    # e.g. REOPEN_AGENT_1_PROMPT -> ("reopen", "agent1")
    m = re.match(r"([A-Z]+)_AGENT_(\d+)_PROMPT$", prompt_name)
    if not m:
        raise ValueError(f"Unrecognized prompt name: {prompt_name}")
    framework_key, idx = m.group(1), m.group(2)
    return FRAMEWORK_MAP[framework_key], f"agent{idx}"


def main() -> None:
    nb = json.loads(NB_PATH.read_text())
    cell5 = "".join(nb["cells"][5]["source"])
    matches = list(PROMPT_BLOCK_RE.finditer(cell5))
    if not matches:
        raise SystemExit("No prompts found in cell 5")

    PROMPTS_DIR.mkdir(exist_ok=True)
    for m in matches:
        name = m.group("name")
        body = m.group("body")
        framework, agent = parse_name(name)
        target_dir = PROMPTS_DIR / framework
        target_dir.mkdir(exist_ok=True)
        out = target_dir / f"{agent}.md"
        frontmatter = (
            "---\n"
            f"prompt_name: {name}\n"
            f"framework: {framework}\n"
            f"agent: {agent}\n"
            "---\n"
        )
        out.write_text(frontmatter + body)
        print(f"wrote {out.relative_to(ROOT)} ({len(body)} chars)")

    print(f"\nTotal: {len(matches)} prompts")


if __name__ == "__main__":
    main()
