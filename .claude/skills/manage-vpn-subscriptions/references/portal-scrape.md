# Portal refresh: API first, browser fallback

## Preferred: v2board HTTP API

52pokemon-style panels expose:

1. `POST {api_base}/api/v1/passport/auth/login`  
   Body: `{"email","password"}`  
   Response: `data.auth_data`, `data.token`
2. `GET {api_base}/api/v1/user/getSubscribe`  
   Header: `Authorization: {auth_data}`  
   Useful fields:
   - `subscribe_url` or build from `token`
   - `u`, `d`, `transfer_enable` → used / remaining
   - `reset_day` → **days until next traffic reset** (`0` = today); **not** calendar DOM
   - `expired_at` (unix) → for 订单日 method, **day-of-month of expiry = monthly reset DOM**
   - `plan.name`, `plan.reset_traffic_method` (`1` = 订单日)

Portal UI host (`https://web4.52pokemon.cc`) may not proxy `/api/v1` (405). Use API hosts such as:

- `https://jkun.waimaosass.icu`
- `https://link123.52pokemon99.cc`
- `https://link123.52pokemon66.cc`

`portal_sync.py` tries account `api_base` then this list.

```bash
python3 skills/manage-vpn-subscriptions/scripts/portal_sync.py sync
python3 skills/manage-vpn-subscriptions/scripts/portal_sync.py sync --account markshi1322
```

## Browser fallback (cmux)

Use when API hosts all fail (WAF, captcha, password change).

```bash
cmux --json browser open https://web4.52pokemon.cc/login
# surface:N from JSON
cmux browser surface:N wait --load-state complete --timeout-ms 15000
cmux browser surface:N snapshot --interactive
# fill email/password, click login
cmux browser surface:N wait --url-contains dashboard --timeout-ms 20000
cmux browser surface:N get text body
# parse 订阅链接 / 剩余流量 / 重置日 from body or snapshot
```

Then write fields:

```bash
python3 skills/manage-vpn-subscriptions/scripts/vpn_store.py set-live \
  --account <id> \
  --subscription-url 'https://...' \
  --traffic-remaining '12 GB / 60 GB' \
  --reset-day 19 \
  --reset-date-note '每月 19 日重置'
```

If `snapshot --interactive` returns `js_error`, use `get text body` / `get html body`.

## Mapping

| Live field | API / derivation | Browser hint |
|------------|------------------|--------------|
| subscription_url | `subscribe_url` | copy 订阅链接 / Clash 订阅 |
| traffic_remaining | `transfer_enable - u - d` | 剩余流量 text |
| days_until_reset | API `reset_day` | 距下次重置 X 天 / 今天重置 |
| reset_dom | day of `expired_at` (CST) when method=订单日 | 每月 N 日 |
| expires_at | `expired_at` | 到期时间 |
| plan_name | `plan.name` | 套餐名 |

Clash name uses **`reset_dom`**, never raw API `reset_day`.
