#!/usr/bin/env bash
set -euo pipefail

[ -f AGENTS.md ] || {
  echo "缺少项目说明文件 AGENTS.md" >&2
  exit 1
}

[ -d skills ] || {
  echo "缺少 skills 目录" >&2
  exit 1
}

python3 - <<'PY'
from pathlib import Path
import re
import sys

errors: list[str] = []
skills_dir = Path("skills")

for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"

    if not skill_md.is_file():
        errors.append(f"{skill_dir}: 缺少 SKILL.md")
        continue

    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if match is None:
        errors.append(f"{skill_md}: 缺少 YAML frontmatter")
    else:
        frontmatter = match.group(1)
        for key in ("name", "description"):
            if re.search(rf"^{key}:\s*\S", frontmatter, re.M) is None:
                errors.append(f"{skill_md}: frontmatter 缺少 {key}")

    if not openai_yaml.is_file():
        errors.append(f"{skill_dir}: 缺少 agents/openai.yaml")
        continue

    agent_text = openai_yaml.read_text(encoding="utf-8")
    for key in ("display_name", "short_description", "default_prompt"):
        if re.search(rf"\b{key}:\s*\S", agent_text) is None:
            errors.append(f"{openai_yaml}: 缺少 {key}")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1)
PY
