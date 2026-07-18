#!/usr/bin/env python3
"""List / switch / add Clash Verge Rev remote profiles with dedup on add."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from vpn_store import DEFAULT_PATH as VPN_PATH
from vpn_store import find_account, load as load_vpn, profile_display_name, save as save_vpn

DEFAULT_PROFILES = (
    Path.home()
    / "Library"
    / "Application Support"
    / "io.github.clash-verge-rev.clash-verge-rev"
    / "profiles.yaml"
)


def _require_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "PyYAML is required. Install with: python3 -m pip install --user pyyaml"
        ) from e
    return yaml


def load_profiles(path: Path) -> dict[str, Any]:
    yaml = _require_yaml()
    if not path.exists():
        raise SystemExit(f"profiles.yaml not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("invalid profiles.yaml")
    data.setdefault("items", [])
    return data


def backup_profiles(path: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(f"{path.name}.bak.{ts}")
    bak.write_bytes(path.read_bytes())
    return bak


def save_profiles(data: dict[str, Any], path: Path, *, do_backup: bool = True) -> Path | None:
    yaml = _require_yaml()
    bak = backup_profiles(path) if do_backup and path.exists() else None
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    tmp.replace(path)
    return bak


def gen_uid(prefix: str = "R", n: int = 11) -> str:
    alphabet = string.ascii_letters + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(n))


def remote_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in data.get("items", []) if isinstance(i, dict) and i.get("type") == "remote"]


def extract_sub_token(url: str | None) -> str | None:
    """Extract subscribe token from a URL when present."""
    if not url or not str(url).strip():
        return None
    parsed = urlparse(str(url).strip())
    qs = parse_qs(parsed.query, keep_blank_values=True)
    for key in ("token", "sid", "uuid"):
        if key in qs and qs[key] and qs[key][0]:
            return str(qs[key][0])
    # path-style: /subscribe/<token> or trailing path segment that looks like hex
    parts = [p for p in parsed.path.split("/") if p]
    if parts and len(parts[-1]) >= 16 and all(c in "0123456789abcdefABCDEF" for c in parts[-1]):
        return parts[-1]
    return None


def normalize_sub_url(url: str | None) -> str | None:
    """Normalize subscription URL for dedup comparison.

    For v2board-style URLs with a token, compare by token only — the same
    account often rotates CDN hosts while keeping the same token.
    """
    if not url or not str(url).strip():
        return None
    u = str(url).strip()
    token = extract_sub_token(u)
    if token:
        return f"token:{token}"
    parsed = urlparse(u)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    # no token: scheme+host+path+sorted query without noise
    drop = {"t", "timestamp", "time", "cache", "_"}
    kept = []
    for k in sorted(qs.keys()):
        if k.lower() in drop:
            continue
        for v in qs[k]:
            kept.append(f"{k}={v}")
    query = "&".join(kept)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or parsed.path,
            "",
            query,
            "",
        )
    )


def find_by_uid(data: dict[str, Any], uid: str) -> dict[str, Any] | None:
    for it in data.get("items", []):
        if isinstance(it, dict) and it.get("uid") == uid:
            return it
    return None


def find_remote_by_url(data: dict[str, Any], url: str) -> dict[str, Any] | None:
    target = normalize_sub_url(url)
    if not target:
        return None
    for it in remote_items(data):
        if normalize_sub_url(it.get("url")) == target:
            return it
    return None


def pick_option_template(data: dict[str, Any], prefer_name_substr: str = "宝可梦") -> dict[str, Any]:
    remotes = remote_items(data)
    for it in remotes:
        name = str(it.get("name") or "")
        if prefer_name_substr in name and isinstance(it.get("option"), dict):
            opt = deepcopy(it["option"])
            # do not reuse merge/script/rules from another profile without cloning —
            # Clash Verge often pairs each remote with its own merge/script set.
            # Prefer copying structure flags only if we also create companion files.
            return opt
    for it in remotes:
        if isinstance(it.get("option"), dict):
            return deepcopy(it["option"])
    return {
        "update_interval": 1440,
        "allow_auto_update": True,
    }


def clone_option_for_new_remote(data: dict[str, Any]) -> dict[str, Any]:
    """Build option for a new remote.

    Clash Verge stores merge/script/rules/proxies/groups as separate profile
    items referenced by uid. Reusing another remote's uids would share
    patches — usually OK for identical provider style, but can surprise.
    Default: copy update flags only; leave merge/script unset so Clash uses
    global defaults unless user already has a dedicated template.
    """
    template = pick_option_template(data)
    return {
        "update_interval": template.get("update_interval", 1440),
        "allow_auto_update": template.get("allow_auto_update", True),
        "with_proxy": template.get("with_proxy", False),
        "self_proxy": template.get("self_proxy", False),
    }


def cmd_list(args: argparse.Namespace) -> int:
    data = load_profiles(Path(args.profiles))
    current = data.get("current")
    rows = []
    for it in remote_items(data):
        rows.append(
            {
                "uid": it.get("uid"),
                "name": it.get("name"),
                "url": it.get("url"),
                "active": it.get("uid") == current,
                "extra": it.get("extra"),
            }
        )
    if args.json:
        print(json.dumps({"current": current, "remotes": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"current\t{current}")
        for r in rows:
            mark = "*" if r["active"] else " "
            print(f"{mark}\t{r['uid']}\t{r['name']}\t{r['url']}")
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    data = load_profiles(Path(args.profiles))
    uid = data.get("current")
    it = find_by_uid(data, uid) if uid else None
    print(
        json.dumps(
            {
                "current": uid,
                "name": None if not it else it.get("name"),
                "url": None if not it else it.get("url"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def switch_to_uid(data: dict[str, Any], uid: str) -> dict[str, Any]:
    it = find_by_uid(data, uid)
    if it is None:
        raise SystemExit(f"profile uid not found: {uid}")
    if it.get("type") != "remote":
        raise SystemExit(f"profile is not remote: {uid} type={it.get('type')}")
    data["current"] = uid
    return it


def cmd_switch(args: argparse.Namespace) -> int:
    profiles_path = Path(args.profiles)
    data = load_profiles(profiles_path)
    uid = args.uid
    if args.account:
        vpn = load_vpn(Path(args.vpn))
        acc = find_account(vpn, args.account)
        if acc is None:
            raise SystemExit(f"account not found: {args.account}")
        uid = acc.get("clash_profile_uid")
        if not uid:
            raise SystemExit(
                f"account {args.account} has no clash_profile_uid; add subscription first"
            )
    if not uid:
        raise SystemExit("need --uid or --account")
    if args.dry_run:
        it = find_by_uid(data, uid)
        if it is None:
            raise SystemExit(f"profile uid not found: {uid}")
        print(json.dumps({"dry_run": True, "would_switch_to": uid, "name": it.get("name")}, ensure_ascii=False))
        return 0
    it = switch_to_uid(data, uid)
    bak = save_profiles(data, profiles_path, do_backup=not args.no_backup)
    print(
        json.dumps(
            {
                "switched_to": uid,
                "name": it.get("name"),
                "backup": str(bak) if bak else None,
                "note": "Reload Clash Verge if the UI does not pick up the change.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    profiles_path = Path(args.profiles)
    data = load_profiles(profiles_path)
    vpn_path = Path(args.vpn)
    vpn = load_vpn(vpn_path)
    acc = find_account(vpn, args.account)
    if acc is None:
        raise SystemExit(f"account not found: {args.account}")

    url = args.url or acc.get("subscription_url")
    if not url:
        raise SystemExit(
            f"account {args.account} has no subscription_url; sync from portal first or pass --url"
        )

    name = args.name or profile_display_name(
        acc.get("reset_dom"),
        expires_at=acc.get("expires_at"),
        fallback_id=str(acc.get("id") or ""),
    )

    # --- dedup checks ---
    existing = find_remote_by_url(data, url)
    dedup_reason = None
    if existing is None and acc.get("clash_profile_uid"):
        linked = find_by_uid(data, acc["clash_profile_uid"])
        if linked and linked.get("type") == "remote":
            # linked profile still exists: treat as already added
            existing = linked
            dedup_reason = "account already linked to clash_profile_uid"
    if existing is not None and dedup_reason is None:
        dedup_reason = "subscription_url already present"

    if existing is not None:
        uid = existing["uid"]
        acc["clash_profile_uid"] = uid
        # keep URL in sync if linked profile drifted
        if args.update_url and existing.get("url") != url:
            if not args.dry_run:
                existing["url"] = url
                existing["updated"] = int(time.time())
        if not args.dry_run:
            save_vpn(vpn, vpn_path)
            if args.switch:
                switch_to_uid(data, uid)
                bak = save_profiles(data, profiles_path, do_backup=not args.no_backup)
            else:
                bak = None
                if args.update_url:
                    bak = save_profiles(data, profiles_path, do_backup=not args.no_backup)
        else:
            bak = None
        print(
            json.dumps(
                {
                    "added": False,
                    "duplicate": True,
                    "reason": dedup_reason,
                    "uid": uid,
                    "name": existing.get("name"),
                    "switched": bool(args.switch) and not args.dry_run,
                    "backup": str(bak) if bak else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.dry_run:
        print(
            json.dumps(
                {
                    "added": True,
                    "duplicate": False,
                    "dry_run": True,
                    "would_name": name,
                    "would_url": url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    uid = gen_uid("R")
    # ensure unique
    while find_by_uid(data, uid) is not None:
        uid = gen_uid("R")
    file_name = f"{uid}.yaml"
    item = {
        "uid": uid,
        "type": "remote",
        "name": name,
        "file": file_name,
        "url": url,
        "selected": [],
        "extra": {},
        "updated": int(time.time()),
        "option": clone_option_for_new_remote(data),
    }
    data.setdefault("items", []).append(item)
    if args.switch:
        data["current"] = uid
    bak = save_profiles(data, profiles_path, do_backup=not args.no_backup)

    # touch empty profile file so Clash has a placeholder until it updates
    profiles_dir = profiles_path.parent / "profiles"
    if profiles_dir.is_dir():
        target = profiles_dir / file_name
        if not target.exists():
            target.write_text("", encoding="utf-8")

    acc["clash_profile_uid"] = uid
    save_vpn(vpn, vpn_path)

    print(
        json.dumps(
            {
                "added": True,
                "duplicate": False,
                "uid": uid,
                "name": name,
                "file": file_name,
                "switched": bool(args.switch),
                "backup": str(bak) if bak else None,
                "note": "Open Clash Verge and update/reload this profile to download nodes.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clash Verge remote profile helper")
    p.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    p.add_argument("--vpn", default=str(VPN_PATH))
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("current")
    sp.set_defaults(func=cmd_current)

    sp = sub.add_parser("switch")
    sp.add_argument("--uid")
    sp.add_argument("--account")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true")
    sp.set_defaults(func=cmd_switch)

    sp = sub.add_parser("add", help="add remote profile from account (dedup by URL / linked uid)")
    sp.add_argument("--account", required=True)
    sp.add_argument("--url", help="override subscription URL")
    sp.add_argument("--name", help='profile name (default 宝可梦-<id>)')
    sp.add_argument("--switch", action="store_true", help="set as current after add/dedup")
    sp.add_argument(
        "--update-url",
        action="store_true",
        help="when duplicate found, rewrite existing profile URL to account URL",
    )
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true")
    sp.set_defaults(func=cmd_add)

    return p


def main(argv: list[str] | None = None) -> int:
    # allow running as script from any cwd
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
