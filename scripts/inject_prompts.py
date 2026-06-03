#!/usr/bin/env python3
"""Inject prompts/**/*.md back into notebook/content.ipynb cell 5.

Round-trip with extract_prompts.py: extract then inject should round-trip
the prompt text (notebook JSON whitespace may differ).
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

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load_prompts() -> dict[str, str]:
    out: dict[str, str] = {}
    for md in PROMPTS_DIR.rglob("*.md"):
        text = md.read_text()
        m = FRONTMATTER_RE.match(text)
        if not m:
            raise SystemExit(f"Missing frontmatter in {md}")
        meta = dict(
            line.split(": ", 1) for line in m.group(1).strip().splitlines()
        )
        body = text[m.end():]
        out[meta["prompt_name"]] = body
    return out


def main() -> None:
    nb = json.loads(NB_PATH.read_text())
    cell5_src = "".join(nb["cells"][5]["source"])
    prompts = load_prompts()

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in prompts:
            print(f"WARN: {name} not found in prompts/, keeping original")
            return match.group(0)
        return f'{name} = """{prompts[name]}"""'

    new_src = PROMPT_BLOCK_RE.sub(replace, cell5_src)

    # nbformat stores source as a list of lines. Preserve that by splitting on
    # \n while keeping the trailing newlines, matching jupyter's convention.
    lines = new_src.splitlines(keepends=True)
    nb["cells"][5]["source"] = lines
    NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
    print(f"Injected {len(prompts)} prompts into {NB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
