# Clash Verge Rev profiles

macOS data dir:

```text
~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/
  profiles.yaml
  profiles/<uid>.yaml
  clash-verge.yaml
```

## Remote item (simplified)

```yaml
current: RMbU3W8yOINV
items:
  - uid: Rxxxxx
    type: remote
    name: 宝可梦-foo
    file: Rxxxxx.yaml
    url: https://host/api/v1/client/subscribe?token=...
    option:
      update_interval: 1440
      allow_auto_update: true
```

## Operations

| User intent | Action |
|-------------|--------|
| 切换订阅 | Set `current` to existing remote `uid` |
| 添加订阅 | Append remote item if not duplicate; optional set `current` |

### Dedup rules for add

1. Same subscription identity already in a remote → reuse that uid  
2. Account `clash_profile_uid` still points at an existing remote → reuse  
3. Otherwise create new uid + empty `profiles/<uid>.yaml`

Identity: if URL has `token=` (v2board), match **token only** across hosts/CDNs. Else compare lowercase host + path + stable query (drop cache bust params).
### After file changes

**Required:** quit Clash Verge GUI **before** writing `profiles.yaml`, then reopen. While the GUI is running it keeps profiles in memory and will overwrite disk edits (rename/add/delete all get reverted).

```bash
osascript -e 'tell application "Clash Verge" to quit'
# wait until: pgrep -x clash-verge  → empty
# … edit profiles.yaml …
open -a "Clash Verge"
```

Backups: `profiles.yaml.bak.<YYYYMMDD-HHMMSS>` next to the original.

Display names: `宝可梦-{reset_dom}` where `reset_dom` is the day-of-month of `expired_at` (订单日 traffic reset), not API `reset_day`.

### Extra rules (prepend)

Each remote has `option.rules` → a `type: rules` file under `profiles/` with prepend/append/delete.

Source of truth: `~/.config/clash/extra_rules.yaml` (not in the skill). Apply via `scripts/apply_extra_rules.py` while GUI is quit.

- **LinkCube**: shared prepend as written (`Proxies` / `OpenAI`)
- **宝可梦-***: same list with `policy_rewrite` → `宝可梦`
- Keep `DOMAIN-SUFFIX,hf.co,DIRECT` and `hf-mirror.com` for **both** kinds

