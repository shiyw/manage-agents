# vpn.yaml schema

Path: `~/.config/secrets/vpn.yaml`

```yaml
version: 1
updated_at: "2026-07-15T00:00:00+00:00"
accounts:
  - id: nimeholoshi39846
    email: nimeholoshi39846@gmail.com
    password: "..."
    portal_url: https://web4.52pokemon.cc
    label: null
    api_base: https://jkun.waimaosass.icu
    subscription_url: https://.../api/v1/client/subscribe?token=...
    traffic_remaining: "1.23 GB / 60.00 GB"
    traffic_remaining_bytes: 1320702442
    traffic_used_bytes: 63103806998
    traffic_total_bytes: 64424509440
    # days until next traffic reset (raw API getSubscribe.reset_day; 0 = today)
    days_until_reset: 19
    # calendar day-of-month traffic resets (from expired_at, CST); use for names
    reset_dom: 3
    reset_date_note: "每月 3 日重置；距下次 19 天（API reset_day）"
    expires_at: "2026-08-03T09:11:41+00:00"
    plan_name: 入门精灵球
    last_synced_at: "2026-07-15T00:00:00+00:00"
    clash_profile_uid: RDBwvJgSEtVk
    notes: null
```

## Field notes

| Field | Meaning |
|-------|---------|
| `id` | Email local-part; stable key for CLI |
| `password` / `portal_url` | User maintained |
| `api_base` | Last successful API host |
| `subscription_url`, traffic* | Portal live state |
| `days_until_reset` | API `reset_day`: days until **next** traffic reset (`0` = today). Changes daily. |
| `reset_dom` | **Monthly reset calendar day** (1–31). For 订单日 method = day of `expired_at` (CST). Stable name key. |
| `reset_day` | Legacy mirror of `days_until_reset` (kept in sync) |
| `expires_at` | Plan expiry (ISO). Anchor for `reset_dom` when method=订单日 |
| `clash_profile_uid` | Linked Clash remote uid |

**Clash display name:** `宝可梦-{reset_dom}` (not `days_until_reset`).

Permissions: directory `0700`, file `0600`.
