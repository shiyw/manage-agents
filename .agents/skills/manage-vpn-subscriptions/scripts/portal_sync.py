#!/usr/bin/env python3
"""Sync live fields from v2board-style portal APIs into vpn.yaml."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vpn_store import (
    DEFAULT_PATH,
    human_remaining,
    load,
    require_account,
    reset_dom_from_expires_at,
    save,
    set_live,
)

# Hosts observed for 52pokemon / related backends. Order matters.
DEFAULT_API_BASES = [
    "https://jkun.waimaosass.icu",
    "https://link123.52pokemon99.cc",
    "https://link123.52pokemon66.cc",
    "https://web4.52pokemon.cc",
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) manage-vpn-subscriptions/1.0"


def http_json(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, Any]:
    data = None
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        raw = e.read()
        code = e.code
    except urllib.error.URLError as e:
        raise RuntimeError(f"request failed: {url}: {e}") from e
    text = raw.decode("utf-8", errors="replace") if raw else ""
    if not text:
        return code, None
    try:
        return code, json.loads(text)
    except json.JSONDecodeError:
        return code, text


def login(api_base: str, email: str, password: str) -> dict[str, str]:
    base = api_base.rstrip("/")
    code, payload = http_json(
        "POST",
        f"{base}/api/v1/passport/auth/login",
        body={"email": email, "password": password},
    )
    if code != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"login HTTP {code} at {base}: {payload!r}"[:300])
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise RuntimeError(f"login unexpected payload at {base}: {payload!r}"[:300])
    auth = data.get("auth_data") or data.get("token")
    token = data.get("token")
    if not auth:
        # some panels put message on failure with 200
        msg = payload.get("message") or payload
        raise RuntimeError(f"login failed at {base}: {msg!r}"[:300])
    return {
        "api_base": base,
        "auth_data": str(auth),
        "token": str(token) if token else "",
    }


def get_subscribe(api_base: str, auth_data: str) -> dict[str, Any]:
    base = api_base.rstrip("/")
    code, payload = http_json(
        "GET",
        f"{base}/api/v1/user/getSubscribe",
        headers={"Authorization": auth_data},
    )
    if code != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"getSubscribe HTTP {code}: {payload!r}"[:300])
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"getSubscribe missing data: {payload!r}"[:300])
    return data


def candidate_bases(acc: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    seen: list[str] = []
    for b in [
        acc.get("api_base"),
        *(extra or []),
        *DEFAULT_API_BASES,
        acc.get("portal_url"),
    ]:
        if not b:
            continue
        b = str(b).rstrip("/")
        if b not in seen:
            seen.append(b)
    return seen


def parse_live(sub: dict[str, Any], api_base: str) -> dict[str, Any]:
    u = int(sub.get("u") or 0)
    d = int(sub.get("d") or 0)
    total = int(sub.get("transfer_enable") or 0)
    used = u + d
    remaining = max(total - used, 0) if total else None
    # API reset_day = days until next traffic reset (0 = today). NOT calendar DOM.
    days_until_reset = sub.get("reset_day")
    if days_until_reset is not None:
        try:
            days_until_reset = int(days_until_reset)
        except (TypeError, ValueError):
            days_until_reset = None
    plan = sub.get("plan") if isinstance(sub.get("plan"), dict) else {}
    plan_name = plan.get("name")
    reset_method = plan.get("reset_traffic_method")
    subscribe_url = sub.get("subscribe_url")
    if not subscribe_url and sub.get("token"):
        subscribe_url = f"{api_base.rstrip('/')}/api/v1/client/subscribe?token={sub['token']}"
    expires_at = None
    exp = sub.get("expired_at")
    if exp:
        try:
            expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            expires_at = str(exp)
    # For method 1 (订单日): monthly reset DOM = day of expired_at (CST).
    # Official: 到期日为每月 N 日则每月 N 日重置流量.
    reset_dom = reset_dom_from_expires_at(exp if exp else expires_at)
    if days_until_reset == 0 and reset_dom is not None:
        reset_note = f"今天重置；每月 {reset_dom} 日重置（订单日/到期日）"
    elif reset_dom is not None and days_until_reset is not None:
        reset_note = f"每月 {reset_dom} 日重置；距下次 {days_until_reset} 天（API reset_day）"
    elif reset_dom is not None:
        reset_note = f"每月 {reset_dom} 日重置"
    elif days_until_reset is not None:
        reset_note = f"距下次重置 {days_until_reset} 天"
    else:
        reset_note = None
    traffic_remaining = None
    if remaining is not None:
        traffic_remaining = human_remaining(remaining, total if total else None)
    return {
        "api_base": api_base.rstrip("/"),
        "subscription_url": subscribe_url,
        "traffic_used_bytes": used,
        "traffic_total_bytes": total if total else None,
        "traffic_remaining_bytes": remaining,
        "traffic_remaining": traffic_remaining,
        "days_until_reset": days_until_reset,
        "reset_dom": reset_dom,
        "reset_date_note": reset_note,
        "expires_at": expires_at,
        "plan_name": plan_name,
        "reset_traffic_method": reset_method,
        "token": sub.get("token"),
        "raw_email": sub.get("email"),
    }


def sync_account(acc: dict[str, Any], *, bases: list[str] | None = None) -> dict[str, Any]:
    email = acc.get("email")
    password = acc.get("password")
    if not email or not password:
        raise RuntimeError("account missing email/password")
    errors: list[str] = []
    for base in candidate_bases(acc, bases):
        try:
            sess = login(base, email, password)
            sub = get_subscribe(sess["api_base"], sess["auth_data"])
            live = parse_live(sub, sess["api_base"])
            set_live(
                acc,
                subscription_url=live["subscription_url"],
                traffic_remaining=live["traffic_remaining"],
                traffic_remaining_bytes=live["traffic_remaining_bytes"],
                traffic_used_bytes=live["traffic_used_bytes"],
                traffic_total_bytes=live["traffic_total_bytes"],
                days_until_reset=live["days_until_reset"],
                reset_dom=live["reset_dom"],
                reset_date_note=live["reset_date_note"],
                expires_at=live["expires_at"],
                plan_name=live["plan_name"],
                api_base=live["api_base"],
                mark_synced=True,
            )
            return {"ok": True, "id": acc.get("id"), "live": live, "tried": base}
        except Exception as e:  # noqa: BLE001 - collect per-base failures
            errors.append(f"{base}: {e}")
    return {"ok": False, "id": acc.get("id"), "errors": errors}


def cmd_sync(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    if args.account:
        targets = [require_account(data, args.account)]
    else:
        targets = [a for a in data.get("accounts", []) if isinstance(a, dict)]
    if not targets:
        print(json.dumps({"error": "no accounts"}, ensure_ascii=False))
        return 1
    results = []
    for acc in targets:
        r = sync_account(acc, bases=args.api_base)
        results.append(
            {
                "ok": r["ok"],
                "id": r.get("id"),
                "email": acc.get("email"),
                "traffic_remaining": acc.get("traffic_remaining") if r["ok"] else None,
                "reset_dom": acc.get("reset_dom") if r["ok"] else None,
                "days_until_reset": acc.get("days_until_reset") if r["ok"] else None,
                "expires_at": acc.get("expires_at") if r["ok"] else None,
                "subscription_url": acc.get("subscription_url") if r["ok"] and args.secrets else None,
                "plan_name": acc.get("plan_name") if r["ok"] else None,
                "api_base": acc.get("api_base") if r["ok"] else None,
                "errors": r.get("errors"),
            }
        )
    save(data, path)
    ok_n = sum(1 for r in results if r["ok"])
    print(json.dumps({"synced": ok_n, "total": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0 if ok_n == len(results) else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sync VPN accounts from portal API")
    p.add_argument("--path", default=str(DEFAULT_PATH))
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sync", help="login + getSubscribe + write live fields")
    sp.add_argument("--account", help="id or email; default all")
    sp.add_argument(
        "--api-base",
        action="append",
        default=None,
        help="prefer this API base (repeatable)",
    )
    sp.add_argument("--secrets", action="store_true", help="include full subscription_url in output")
    sp.set_defaults(func=cmd_sync)
    return p


def main(argv: list[str] | None = None) -> int:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
