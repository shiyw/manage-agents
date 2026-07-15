# manage-vpn-subscriptions 设计

Date: 2026-07-15  
Status: approved

## Goal

管理 52pokemon（及同类 v2board）多账号 VPN：本地维护账号凭证与 live 状态；按需刷新订阅信息；在 Clash Verge Rev 中切换当前订阅或添加订阅（添加时查重）。

## Approach

Skill 文档 + 本地脚本（方案 A）。

- 数据：`~/.config/secrets/vpn.yaml`（0600）
- 刷新：优先 v2board HTTP API；失败再 cmux-browser
- Clash：读写 `profiles.yaml`（切换 `current` / 添加 remote），改前备份

## YAML schema

见 skill `references/vpn-yaml.md` 与实现中的 `vpn_store.py`。

## Reset semantics (V2Board)

- API `getSubscribe.reset_day` → `days_until_reset`（0 = 今天重置；会随日期变化）。
- `reset_dom` = 每月流量重置的公历日，取自 `expired_at` 的日（订单日 method）；用于 Clash 名 `宝可梦-{reset_dom}`。
- 改 `profiles.yaml` 前必须先退出 Clash Verge GUI。

## Clash 添加查重

添加前若已存在相同订阅身份，或账号已关联且仍存在的 `clash_profile_uid`，则**不新建**，返回已有 uid，可选 `--switch`。

身份规则：有 `token=` 时只比 token（跨 CDN 主机仍算重复）；否则规范化 host+path+query。
## Non-goals

- 不测节点（`test-clash-verge-nodes`）
- 不默认删除 profile
- 聊天输出中截断 password / 完整 subscribe token
