---
name: manage-vpn-subscriptions
description: >
  Use when the user wants to manage VPN/proxy subscription accounts, refresh
  remaining traffic or reset day, store portal credentials in
  ~/.config/secrets/vpn.yaml, list 52pokemon/v2board accounts, update
  subscription URLs, switch Clash Verge current profile, or add a Clash Verge
  remote subscription with dedup. Triggers: VPN 订阅, 宝可梦, clash verge 订阅,
  切换订阅, 添加订阅, 剩余流量, 重置日期, vpn.yaml, /manage-vpn-subscriptions.
---

# Manage VPN Subscriptions

## Overview

Manage multi-account VPN portal credentials and live subscription state in `~/.config/secrets/vpn.yaml`, refresh fields via portal API (browser fallback), and switch/add Clash Verge Rev remote profiles. **Adding a subscription must dedup** — never create a second remote for the same URL or already-linked account.

Do not lecture about password storage. Credentials live at the path the user chose.

Node latency/speed tests belong to `test-clash-verge-nodes`, not this skill.

## Paths

| Item | Path |
|------|------|
| Account store | `~/.config/secrets/vpn.yaml` (mode `0600`, dir `0700`) |
| Extra rules | `~/.config/clash/extra_rules.yaml` (user-maintained) |
| Scripts | `skills/manage-vpn-subscriptions/scripts/` |
| Clash profiles | `~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/profiles.yaml` |

## Scripts

Run from repo root. Use `uv run --with pyyaml` (system Python is PEP 668 managed):

```bash
SCRIPTS=skills/manage-vpn-subscriptions/scripts
RUN="uv run --with pyyaml python"

$RUN "$SCRIPTS/vpn_store.py" list --json
$RUN "$SCRIPTS/vpn_store.py" init          # seed missing accounts
$RUN "$SCRIPTS/portal_sync.py" sync        # all accounts
$RUN "$SCRIPTS/portal_sync.py" sync --account nimeholoshi39846
$RUN "$SCRIPTS/clash_profiles.py" list --json
$RUN "$SCRIPTS/clash_profiles.py" current
$RUN "$SCRIPTS/clash_profiles.py" switch --account <id>
$RUN "$SCRIPTS/clash_profiles.py" switch --uid <uid>
$RUN "$SCRIPTS/clash_profiles.py" add --account <id> [--switch] [--dry-run]

# Extra rules (LinkCube / 宝可梦) — quit Clash GUI first
$RUN "$SCRIPTS/apply_extra_rules.py" --dry-run
$RUN "$SCRIPTS/apply_extra_rules.py"
$RUN "$SCRIPTS/apply_extra_rules.py" --kind pokemon
```

Also acceptable: `python3 ...` if PyYAML is already importable.

### Extra rules

**User file (source of truth):** `~/.config/clash/extra_rules.yaml` — not stored in the skill.

| Profile name match | How rules are applied |
|--------------------|------------------------|
| `LinkCube` | shared `prepend` as written (`Proxies` / `OpenAI` / `DIRECT` / `REJECT`) |
| `宝可梦*` | same list + `policy_rewrite.pokemon` (`Proxies`→`宝可梦`, `OpenAI`→`宝可梦`) |

Include `hf.co` / `hf-mirror.com → DIRECT` in the shared list for both kinds. Edit the user YAML when rules change, quit Clash Verge, then re-run `apply_extra_rules.py`. After adding a new 宝可梦/LinkCube remote, run apply again.

### `vpn_store.py`

- `list` / `get` / `upsert` / `set-live` / `init`
- Primary key: `id` (email local-part) or full `email`

### `portal_sync.py`

- `sync` logs into v2board API (`/api/v1/passport/auth/login` + `/api/v1/user/getSubscribe`)
- Writes: `subscription_url`, traffic fields, `days_until_reset` (API reset_day), `reset_dom` (expire day), `expires_at`, `plan_name`, `api_base`, `last_synced_at`
- Tries `api_base` then known 52pokemon backends (see `references/portal-scrape.md`)

### `clash_profiles.py`

| Command | Meaning |
|---------|---------|
| `switch` | Set `profiles.yaml` `current` to an existing remote uid |
| `add` | Create a new remote profile from account `subscription_url` |

**Add dedup (required):**

1. If a remote already matches the same subscription identity → **do not create**; return existing uid; update `clash_profile_uid` on the account.  
   Identity: prefer `token=` (or path token) only — **same token on different CDN hosts still counts as duplicate**. Without token, fall back to normalized host+path+query.
2. Else if account `clash_profile_uid` still exists as remote → **do not create**; same return.
3. Only then append a new remote (`name` default `宝可梦-{reset_dom}` from expire day), optional `--switch`, write empty `profiles/<uid>.yaml` placeholder, backfill `clash_profile_uid`.

**Clash Verge overwrites `profiles.yaml` while running.** Any direct edit (rename / add / switch via scripts) must follow:

1. Quit GUI: `osascript -e 'tell application "Clash Verge" to quit'` then `pkill -x clash-verge` if needed  
2. Edit `profiles.yaml` (scripts OK)  
3. `open -a "Clash Verge"`  
4. Re-read disk and confirm names still match  

Do **not** rely on delete+re-add while the app is open — the running process restores its in-memory list and undoes disk changes.

**Reset fields:** API `reset_day` = `days_until_reset` (0=today). **`reset_dom`** = monthly calendar day from `expired_at` (订单日). Clash name: `宝可梦-{reset_dom}`.Always backup `profiles.yaml` to `profiles.yaml.bak.<timestamp>` before write (unless `--no-backup`). After switch/add, tell the user to reload/update the profile in Clash Verge if the UI does not pick it up.

## Workflows

### List / status

1. `vpn_store.py list --json` and optionally `clash_profiles.py current`
2. Summarize: email, plan, remaining traffic, reset day, linked Clash uid, whether it is current
3. In chat, **redact** passwords and full subscribe tokens (scripts already redact URLs unless `--secrets`)

### Refresh live fields

1. Prefer `portal_sync.py sync` (all or `--account`)
2. If API fails for an account: follow `references/portal-scrape.md` with **cmux-browser** (or other browser automation), then `vpn_store.py set-live ...`
3. Report per-account ok/fail; do not wipe previous live fields on failure (sync only writes on success)

### Switch subscription

1. Resolve target by `--account` (needs `clash_profile_uid`) or `--uid`
2. `clash_profiles.py switch ...` (use `--dry-run` if user only wants a preview)
3. Confirm new `current`

### Add subscription

1. Ensure account has `subscription_url` (sync first if missing)
2. `clash_profiles.py add --account <id> [--switch] [--dry-run]`
3. Respect dedup output: `duplicate: true` means no new profile was created
4. Prompt user to **update** the profile in Clash Verge so nodes download

### Edit credentials

- `vpn_store.py upsert --email ... --password ...`
- Or edit `vpn.yaml` carefully; keep permissions `0600`

## Red flags

- Creating a second Clash remote without checking URL / linked uid
- Printing full passwords or full `token=` URLs in the final user-facing summary
- Mutating `test-clash-verge-nodes` concerns (delay tests) instead of profiles
- Deleting Clash profiles unless the user explicitly asked
- Skipping backup before writing `profiles.yaml`

## References

- [references/vpn-yaml.md](references/vpn-yaml.md) — store schema
- [references/portal-scrape.md](references/portal-scrape.md) — API + browser fallback
- [references/clash-verge.md](references/clash-verge.md) — profiles layout
- `~/.config/clash/extra_rules.yaml` — LinkCube / 宝可梦 prepend rules (user-maintained)