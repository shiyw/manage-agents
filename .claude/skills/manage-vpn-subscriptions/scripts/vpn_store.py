#!/usr/bin/env python3
"""Read/write ~/.config/secrets/vpn.yaml for VPN account management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path.home() / ".config" / "secrets" / "vpn.yaml"
DEFAULT_PORTAL = "https://web4.52pokemon.cc"

SEED_ACCOUNTS = [
    {
        "email": "nimeholoshi39846@gmail.com",
        "password": "Rigdic-xozhab-kofmo1",
        "portal_url": DEFAULT_PORTAL,
    },
    {
        "email": "markshi1322@gmail.com",
        "password": "neFwiv-nozgeg-keqjy1",
        "portal_url": DEFAULT_PORTAL,
    },
    {
        "email": "shiy123456789@foxmail.com",
        "password": "tobnat-wEbpyb-pacje8",
        "portal_url": DEFAULT_PORTAL,
    },
    {
        "email": "1538828841@qq.com",
        "password": "j0eg-EG3w-4gwh",
        "portal_url": DEFAULT_PORTAL,
    },
    {
        "email": "shiyi8699@gmail.com",
        "password": "Ckasghgap0Vxjt",
        "portal_url": DEFAULT_PORTAL,
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def email_id(email: str) -> str:
    local = email.split("@", 1)[0].strip().lower()
    if not local:
        raise ValueError(f"invalid email: {email!r}")
    return local


def empty_account(
    email: str,
    password: str,
    portal_url: str = DEFAULT_PORTAL,
    label: str | None = None,
) -> dict[str, Any]:
    return {
        "id": email_id(email),
        "email": email.strip(),
        "password": password,
        "portal_url": portal_url.rstrip("/"),
        "label": label,
        "api_base": None,
        "subscription_url": None,
        "traffic_remaining": None,
        "traffic_remaining_bytes": None,
        "traffic_used_bytes": None,
        "traffic_total_bytes": None,
        # days_until_reset: API getSubscribe.reset_day (0 = resets today). NOT calendar DOM.
        "days_until_reset": None,
        # reset_dom: day-of-month traffic resets (1–31); for method=订单日 equals expire day.
        "reset_dom": None,
        "reset_date_note": None,
        "expires_at": None,
        "plan_name": None,
        "last_synced_at": None,
        "clash_profile_uid": None,
        "notes": None,
    }


def empty_store() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "accounts": []}


def _require_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "PyYAML is required. Install with: python3 -m pip install --user pyyaml"
        ) from e
    return yaml


def load(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    yaml = _require_yaml()
    if not path.exists():
        return empty_store()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return empty_store()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid store (not a mapping): {path}")
    data.setdefault("version", 1)
    data.setdefault("updated_at", None)
    data.setdefault("accounts", [])
    if not isinstance(data["accounts"], list):
        raise SystemExit("invalid store: accounts must be a list")
    return data


def save(data: dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    yaml = _require_yaml()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    data = deepcopy(data)
    data["updated_at"] = now_iso()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def find_account(data: dict[str, Any], key: str) -> dict[str, Any] | None:
    key_l = key.strip().lower()
    for acc in data.get("accounts", []):
        if not isinstance(acc, dict):
            continue
        if str(acc.get("id", "")).lower() == key_l:
            return acc
        if str(acc.get("email", "")).lower() == key_l:
            return acc
    return None


def require_account(data: dict[str, Any], key: str) -> dict[str, Any]:
    acc = find_account(data, key)
    if acc is None:
        raise SystemExit(f"account not found: {key}")
    return acc


def upsert_account(
    data: dict[str, Any],
    *,
    email: str,
    password: str,
    portal_url: str = DEFAULT_PORTAL,
    label: str | None = None,
) -> dict[str, Any]:
    existing = find_account(data, email)
    if existing is None:
        acc = empty_account(email, password, portal_url, label)
        data.setdefault("accounts", []).append(acc)
        return acc
    existing["email"] = email.strip()
    existing["password"] = password
    existing["portal_url"] = portal_url.rstrip("/")
    if label is not None:
        existing["label"] = label
    existing.setdefault("id", email_id(email))
    return existing


def set_live(
    acc: dict[str, Any],
    *,
    subscription_url: str | None = None,
    traffic_remaining: str | None = None,
    traffic_remaining_bytes: int | None = None,
    traffic_used_bytes: int | None = None,
    traffic_total_bytes: int | None = None,
    days_until_reset: int | None = None,
    reset_dom: int | None = None,
    reset_day: int | None = None,  # legacy alias → days_until_reset
    reset_date_note: str | None = None,
    expires_at: str | None = None,
    plan_name: str | None = None,
    api_base: str | None = None,
    clash_profile_uid: str | None = None,
    mark_synced: bool = True,
) -> None:
    if subscription_url is not None:
        acc["subscription_url"] = subscription_url
    if traffic_remaining is not None:
        acc["traffic_remaining"] = traffic_remaining
    if traffic_remaining_bytes is not None:
        acc["traffic_remaining_bytes"] = traffic_remaining_bytes
    if traffic_used_bytes is not None:
        acc["traffic_used_bytes"] = traffic_used_bytes
    if traffic_total_bytes is not None:
        acc["traffic_total_bytes"] = traffic_total_bytes
    if days_until_reset is None and reset_day is not None:
        days_until_reset = reset_day
    if days_until_reset is not None:
        acc["days_until_reset"] = days_until_reset
        # keep legacy key in sync for older notes/scripts
        acc["reset_day"] = days_until_reset
    if reset_dom is not None:
        acc["reset_dom"] = reset_dom
    if reset_date_note is not None:
        acc["reset_date_note"] = reset_date_note
    if expires_at is not None:
        acc["expires_at"] = expires_at
    if plan_name is not None:
        acc["plan_name"] = plan_name
    if api_base is not None:
        acc["api_base"] = api_base.rstrip("/")
    if clash_profile_uid is not None:
        acc["clash_profile_uid"] = clash_profile_uid
    if mark_synced:
        acc["last_synced_at"] = now_iso()


def format_bytes(n: int | None) -> str:
    if n is None:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if abs(x) < 1024 or u == units[-1]:
            if u == "B":
                return f"{int(x)} {u}"
            return f"{x:.2f} {u}"
        x /= 1024
    return f"{n} B"


def human_remaining(remaining: int, total: int | None) -> str:
    if total and total > 0:
        return f"{format_bytes(remaining)} / {format_bytes(total)}"
    return format_bytes(remaining)


def reset_dom_from_expires_at(expires_at: str | int | None) -> int | None:
    """Calendar day-of-month for traffic reset (Asia/Shanghai).

    For V2Board reset_traffic_method=1 (订单日), traffic resets on the day-of-month
    of expired_at — not on API field reset_day.
    """
    if expires_at is None or expires_at == "":
        return None
    try:
        if isinstance(expires_at, (int, float)) or (
            isinstance(expires_at, str) and expires_at.isdigit()
        ):
            dt = datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
        else:
            s = str(expires_at).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        # panel operates in CST; use +08 for "which calendar day"
        local = dt.astimezone(timezone(timedelta(hours=8)))
        return int(local.day)
    except (TypeError, ValueError, OSError):
        return None


def profile_display_name(
    reset_dom: int | None = None,
    *,
    expires_at: str | int | None = None,
    fallback_id: str | None = None,
    # legacy kwargs ignored for callers still passing API reset_day
    reset_day: int | None = None,
) -> str:
    """Clash remote display name: 宝可梦-<每月重置日> (reset_dom / expire day)."""
    dom = reset_dom
    if dom is None:
        dom = reset_dom_from_expires_at(expires_at)
    if dom is not None:
        return f"宝可梦-{int(dom)}"
    if fallback_id:
        return f"宝可梦-{fallback_id}"
    return "宝可梦"


def redact_url(url: str | None, keep: int = 24) -> str:
    if not url:
        return ""
    if "token=" in url:
        head, _, rest = url.partition("token=")
        token = rest.split("&", 1)[0]
        tail = rest[len(token) :]
        if len(token) > keep:
            token = token[:8] + "…" + token[-4:]
        return f"{head}token={token}{tail}"
    if len(url) > 60:
        return url[:40] + "…" + url[-8:]
    return url


def list_rows(data: dict[str, Any], *, show_secrets: bool = False) -> list[dict[str, Any]]:
    rows = []
    for acc in data.get("accounts", []):
        if not isinstance(acc, dict):
            continue
        row = {
            "id": acc.get("id"),
            "email": acc.get("email"),
            "plan": acc.get("plan_name"),
            "traffic_remaining": acc.get("traffic_remaining"),
            "reset_dom": acc.get("reset_dom"),
            "days_until_reset": acc.get("days_until_reset", acc.get("reset_day")),
            "expires_at": acc.get("expires_at"),
            "profile_name": profile_display_name(
                acc.get("reset_dom"),
                expires_at=acc.get("expires_at"),
                fallback_id=str(acc.get("id") or ""),
            ),
            "subscription_url": (
                acc.get("subscription_url")
                if show_secrets
                else redact_url(acc.get("subscription_url"))
            ),
            "clash_profile_uid": acc.get("clash_profile_uid"),
            "api_base": acc.get("api_base"),
            "last_synced_at": acc.get("last_synced_at"),
        }
        if show_secrets:
            row["password"] = acc.get("password")
        rows.append(row)
    return rows


def init_seed(path: Path, *, force: bool = False) -> dict[str, Any]:
    data = load(path)
    if data.get("accounts") and not force:
        # merge missing only
        for seed in SEED_ACCOUNTS:
            if find_account(data, seed["email"]) is None:
                upsert_account(
                    data,
                    email=seed["email"],
                    password=seed["password"],
                    portal_url=seed["portal_url"],
                )
        save(data, path)
        return data
    if force or not data.get("accounts"):
        data = empty_store()
        for seed in SEED_ACCOUNTS:
            upsert_account(
                data,
                email=seed["email"],
                password=seed["password"],
                portal_url=seed["portal_url"],
            )
        save(data, path)
    return data


def cmd_list(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    rows = list_rows(data, show_secrets=args.secrets)
    if args.json:
        print(json.dumps({"updated_at": data.get("updated_at"), "accounts": rows}, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("(no accounts)")
        return 0
    headers = [
        "id",
        "email",
        "plan",
        "traffic_remaining",
        "reset_dom",
        "days_until_reset",
        "profile_name",
        "clash_profile_uid",
        "last_synced_at",
    ]
    print("\t".join(headers))
    for r in rows:
        print("\t".join(str(r.get(h) if r.get(h) is not None else "") for h in headers))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    data = init_seed(Path(args.path), force=args.force)
    print(json.dumps({"path": str(args.path), "count": len(data.get("accounts", []))}, ensure_ascii=False))
    return 0


def cmd_upsert(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    acc = upsert_account(
        data,
        email=args.email,
        password=args.password,
        portal_url=args.portal_url,
        label=args.label,
    )
    save(data, path)
    print(json.dumps({"id": acc["id"], "email": acc["email"]}, ensure_ascii=False))
    return 0


def cmd_set_live(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    acc = require_account(data, args.account)
    kwargs: dict[str, Any] = {}
    for field in (
        "subscription_url",
        "traffic_remaining",
        "reset_date_note",
        "expires_at",
        "plan_name",
        "api_base",
        "clash_profile_uid",
    ):
        val = getattr(args, field, None)
        if val is not None:
            kwargs[field] = val
    for field in (
        "traffic_remaining_bytes",
        "traffic_used_bytes",
        "traffic_total_bytes",
        "days_until_reset",
        "reset_dom",
        "reset_day",
    ):
        val = getattr(args, field, None)
        if val is not None:
            kwargs[field] = val
    set_live(acc, **kwargs, mark_synced=not args.no_synced)
    save(data, path)
    print(json.dumps({"id": acc["id"], "last_synced_at": acc.get("last_synced_at")}, ensure_ascii=False))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    acc = require_account(data, args.account)
    out = deepcopy(acc)
    if not args.secrets:
        out["password"] = "***"
        out["subscription_url"] = redact_url(out.get("subscription_url"))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="VPN account store helper")
    p.add_argument("--path", default=str(DEFAULT_PATH), help="path to vpn.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="list accounts")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--secrets", action="store_true", help="include passwords / full URLs")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("init", help="seed default accounts")
    sp.add_argument("--force", action="store_true", help="replace all accounts with seed")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("upsert", help="add or update account credentials")
    sp.add_argument("--email", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--portal-url", default=DEFAULT_PORTAL)
    sp.add_argument("--label", default=None)
    sp.set_defaults(func=cmd_upsert)

    sp = sub.add_parser("get", help="get one account as JSON")
    sp.add_argument("account")
    sp.add_argument("--secrets", action="store_true")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("set-live", help="update live fields for an account")
    sp.add_argument("--account", required=True)
    sp.add_argument("--subscription-url")
    sp.add_argument("--traffic-remaining")
    sp.add_argument("--traffic-remaining-bytes", type=int)
    sp.add_argument("--traffic-used-bytes", type=int)
    sp.add_argument("--traffic-total-bytes", type=int)
    sp.add_argument(
        "--days-until-reset",
        type=int,
        help="days until next traffic reset (API getSubscribe.reset_day; 0=today)",
    )
    sp.add_argument(
        "--reset-dom",
        type=int,
        help="calendar day-of-month for monthly traffic reset (from expired_at)",
    )
    sp.add_argument(
        "--reset-day",
        type=int,
        help="legacy alias for --days-until-reset",
    )
    sp.add_argument("--reset-date-note")
    sp.add_argument("--expires-at")
    sp.add_argument("--plan-name")
    sp.add_argument("--api-base")
    sp.add_argument("--clash-profile-uid")
    sp.add_argument("--no-synced", action="store_true")
    sp.set_defaults(func=cmd_set_live)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
