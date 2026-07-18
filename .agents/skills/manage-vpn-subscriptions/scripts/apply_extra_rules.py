#!/usr/bin/env python3
"""Apply managed extra rules to Clash Verge remote profiles.

Default rules file: ~/.config/clash/extra_rules.yaml (user-maintained, not in skill).

- LinkCube: shared prepend as written (Proxies / OpenAI / DIRECT / REJECT)
- 宝可梦: same list with policy_rewrite (Proxies→宝可梦, OpenAI→宝可梦)

Must run while Clash Verge GUI is quit (it overwrites profiles while running).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from clash_profiles import DEFAULT_PROFILES, load_profiles, save_profiles  # noqa: E402

DEFAULT_RULES_FILE = Path.home() / ".config" / "clash" / "extra_rules.yaml"
PROFILES_DIR = DEFAULT_PROFILES.parent / "profiles"


def _require_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "PyYAML is required. Install with: uv run --with pyyaml python ..."
        ) from e
    return yaml


def load_rules_template(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"rules file not found: {path}\n"
            "Create ~/.config/clash/extra_rules.yaml (see skill docs)."
        )
    yaml = _require_yaml()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid rules template: {path}")
    return data


def classify_remote(name: str | None) -> str | None:
    n = str(name or "")
    if "LinkCube" in n or "linkcube" in n.lower():
        return "linkcube"
    if "宝可梦" in n:
        return "pokemon"
    return None


def rewrite_rule_policy(rule: str, mapping: dict[str, str]) -> str:
    """Rewrite the policy group (segment after last comma) if mapped."""
    if not mapping or "," not in rule:
        return rule
    head, _, policy = rule.rpartition(",")
    policy = policy.strip()
    new_pol = mapping.get(policy)
    if new_pol is None:
        return rule
    return f"{head},{new_pol}"


def resolve_payload(tpl: dict[str, Any], kind: str) -> dict[str, Any]:
    """Build prepend/append/delete for a kind.

    Prefer full per-kind override if `kind.prepend` exists; else shared top-level
    list + policy_rewrite[kind].
    """
    override = tpl.get(kind)
    if isinstance(override, dict) and "prepend" in override:
        return {
            "prepend": list(override.get("prepend") or []),
            "append": list(override.get("append") or []),
            "delete": list(override.get("delete") or []),
        }

    prepend = list(tpl.get("prepend") or [])
    append = list(tpl.get("append") or [])
    delete = list(tpl.get("delete") or [])
    rewrites = tpl.get("policy_rewrite") if isinstance(tpl.get("policy_rewrite"), dict) else {}
    mapping = rewrites.get(kind) if isinstance(rewrites, dict) else None
    if isinstance(mapping, dict) and mapping:
        prepend = [rewrite_rule_policy(str(r), {str(k): str(v) for k, v in mapping.items()}) for r in prepend]
    return {"prepend": prepend, "append": append, "delete": delete}


def dump_rules_yaml(payload: dict[str, Any]) -> str:
    """Emit Clash Verge rules enhancement file (quoted rule strings)."""
    yaml = _require_yaml()

    class Q(str):
        pass

    def represent_q(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")

    yaml.add_representer(Q, represent_q)
    out = {
        "prepend": [Q(x) for x in (payload.get("prepend") or [])],
        "append": list(payload.get("append") or []),
        "delete": list(payload.get("delete") or []),
    }
    text = yaml.dump(
        out,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return "# Applied by manage-vpn-subscriptions apply_extra_rules.py\n" + text


def apply(
    *,
    profiles_path: Path,
    rules_template: Path,
    kinds: set[str] | None = None,
    dry_run: bool = False,
    no_backup: bool = False,
) -> dict[str, Any]:
    tpl = load_rules_template(rules_template)
    data = load_profiles(profiles_path)
    items_by_uid = {
        it["uid"]: it for it in data.get("items", []) if isinstance(it, dict) and it.get("uid")
    }
    results = []
    touched_files: list[str] = []

    for it in data.get("items", []):
        if not isinstance(it, dict) or it.get("type") != "remote":
            continue
        kind = classify_remote(it.get("name"))
        if kind is None:
            continue
        if kinds is not None and kind not in kinds:
            continue
        payload = resolve_payload(tpl, kind)
        rules_uid = (it.get("option") or {}).get("rules")
        if not rules_uid or rules_uid not in items_by_uid:
            results.append(
                {
                    "uid": it.get("uid"),
                    "name": it.get("name"),
                    "kind": kind,
                    "error": "missing option.rules",
                }
            )
            continue
        ref = items_by_uid[rules_uid]
        file_name = ref.get("file")
        if not file_name:
            results.append(
                {"uid": it.get("uid"), "name": it.get("name"), "error": "rules item has no file"}
            )
            continue
        path = PROFILES_DIR / file_name
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        new_text = dump_rules_yaml(payload)
        changed = old_text.strip() != new_text.strip()
        results.append(
            {
                "uid": it.get("uid"),
                "name": it.get("name"),
                "kind": kind,
                "rules_uid": rules_uid,
                "file": str(path),
                "changed": changed,
                "prepend_count": len(payload["prepend"]),
            }
        )
        if changed and not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                bak = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d-%H%M%S')}")
                bak.write_bytes(path.read_bytes())
            path.write_text(new_text, encoding="utf-8")
            touched_files.append(str(path))
            it["updated"] = int(time.time())

    bak_profiles = None
    if not dry_run and any(r.get("changed") for r in results):
        bak_profiles = save_profiles(data, profiles_path, do_backup=not no_backup)

    return {
        "dry_run": dry_run,
        "rules_file": str(rules_template),
        "profiles_backup": str(bak_profiles) if bak_profiles else None,
        "results": results,
        "touched_files": touched_files,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Apply extra rules to LinkCube / 宝可梦 profiles")
    p.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    p.add_argument(
        "--rules-file",
        default=str(DEFAULT_RULES_FILE),
        help=f"default: {DEFAULT_RULES_FILE}",
    )
    p.add_argument(
        "--kind",
        action="append",
        choices=["linkcube", "pokemon"],
        help="only these kinds (repeatable); default both",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    args = p.parse_args(argv)
    kinds = set(args.kind) if args.kind else None
    out = apply(
        profiles_path=Path(args.profiles),
        rules_template=Path(args.rules_file),
        kinds=kinds,
        dry_run=args.dry_run,
        no_backup=args.no_backup,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if any(r.get("error") for r in out["results"]):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
