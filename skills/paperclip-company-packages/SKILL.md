---
name: paperclip-company-packages
description: Use when 需要设计、导入、导出、修复或验证 Paperclip 公司包，尤其涉及 COMPANY.md、agents/*/AGENTS.md、.paperclip.yaml、codex_local adapter、目标树或导入 dry-run。
---

# Paperclip 公司包

## 核心原则

把 Paperclip 公司包当作“可被导入器真实解析的产品包”，不要只写一套看起来合理的 Markdown。每次都用 Paperclip CLI 的 `--dry-run --json` 检查服务器实际读到了什么。

## 适用场景

- 为 Paperclip 设计一家公司、团队或 AI 员工组织。
- 从本地 Markdown 包导入公司和 Agent。
- 修复导入后公司名、品牌色、Agent 名称、汇报关系或 adapter 不正确的问题。
- 判断 Paperclip 包格式和现有文档、导出结果是否一致。
- 用户要求“不预置 Projects”“排除某个 Agent”“改公司名”“导入目标树”。

## 包结构

优先使用 Paperclip 自己导出的 v1 结构：

```text
company-package/
├── .paperclip.yaml
├── COMPANY.md
├── README.md
└── agents/
    ├── elon/AGENTS.md
    ├── jobs/AGENTS.md
    ├── linus/AGENTS.md
    └── turing/AGENTS.md
```

`COMPANY.md` 必须有 frontmatter：

```markdown
---
name: "AetherForge"
description: "Yi 的 AI 原生软件工作室，专注开发浏览器插件、SaaS 产品和网站。"
schema: "agentcompanies/v1"
slug: "aetherforge"
---
```

每个 `agents/<slug>/AGENTS.md` 至少写 `name` 和 `title`；子级 Agent 用 `reportsTo`，不是 `reportsToSlug`：

```markdown
---
name: "Jobs"
title: "产品与设计"
reportsTo: "elon"
---
```

`.paperclip.yaml` 使用普通 YAML 的 `paperclip/v1` 形态。不要用旧的 JSON `schemaVersion` 清单来期待导入器读取所有字段。

```yaml
schema: "paperclip/v1"
agents:
  elon:
    role: "ceo"
    icon: "rocket"
    capabilities: "把 Yi 的意图转化为目标关联的工作。"
    adapter:
      type: "codex_local"
  jobs:
    role: "pm"
    icon: "sparkles"
    capabilities: "把目标和用户上下文转化为产品规格。"
    adapter:
      type: "codex_local"
company:
  brandColor: "#4F7CFF"
  attachmentMaxBytes: 10485760
  requireBoardApprovalForNewAgents: true
sidebar:
  agents:
    - "elon"
    - "jobs"
  projects: []
```

## 工作流

1. 先确认 Paperclip CLI 和真实解析行为。

```bash
paperclipai --version
paperclipai company import --help
```

2. 如不确定格式，导出一个现有公司到临时目录，照 Paperclip 自己的输出写。

```bash
paperclipai company export <company-id> \
  --out /tmp/paperclip-export-check \
  --include company,agents \
  --api-base <api-base>
```

3. 设计包时明确边界。

- 用户说不预置项目，就让 `sidebar.projects` 为空，并不要创建 `projects/` 文档。
- 用户排除某人，就不要创建该 Agent；可以在元数据或说明里记录“被排除”，但验证脚本只应禁止对应 slug。
- 不要自创固定的 Agent 交接模板；默认使用 Paperclip 的任务、评论、工作产物、委派、心跳和审批机制。

4. 导入预览必须用 JSON 检查 manifest，不要只看人类可读摘要。

```bash
paperclipai company import /path/to/package \
  --target new \
  --new-company-name AetherForge \
  --include company,agents \
  --agents elon,jobs,linus,turing \
  --collision rename \
  --dry-run \
  --api-base <api-base> \
  --json
```

重点检查：

- `manifest.company.name` 是真实公司名，不是 `Imported Company`。
- `manifest.company.brandColor`、`attachmentMaxBytes`、`requireBoardApprovalForNewAgents` 已被读取。
- 选中的 Agent 是预期列表；根目录 `AGENTS.md` 可能被识别成 slug `agent`，所以不要用 `--agents all`。
- 每个目标 Agent 的 `adapterType` 是预期值，例如 `codex_local`。
- `reportsToSlug` 是否按组织结构出现。
- `projects` 为 0，除非用户明确要预置项目。

5. 真正导入时继续显式列 Agent。

```bash
paperclipai company import /path/to/package \
  --target new \
  --new-company-name AetherForge \
  --include company,agents \
  --agents elon,jobs,linus,turing \
  --collision rename \
  --yes \
  --api-base <api-base> \
  --json
```

6. 目标树通常不随公司包导入。需要目标时，用 `paperclipai goal create` 或项目脚本单独写入，并记录 root goal ID。

7. 导入后必须查服务器状态。

```bash
paperclipai company get <company-id> --api-base <api-base> --json
paperclipai agent list -C <company-id> --api-base <api-base> --json
paperclipai goal list -C <company-id> --api-base <api-base> --json
```

## 修复已导入公司

如果导入后才发现字段没进来，先不要假设可以覆盖导入。Paperclip safe import 可能拒绝 `--collision replace`。优先用命令补齐：

```bash
paperclipai company update <company-id> \
  --payload-json '{"brandColor":"#4F7CFF","requireBoardApprovalForNewAgents":true}' \
  --api-base <api-base> \
  --json

paperclipai agent update <agent-id> \
  --payload-json '{"adapterType":"codex_local","reportsTo":"<manager-agent-id>"}' \
  --api-base <api-base> \
  --json
```

只有在用户明确批准破坏性操作时，才考虑删除错误导入后重导。

## 常见错误

| 错误 | 后果 | 修正 |
| --- | --- | --- |
| 用 JSON `schemaVersion` 清单 | 导入器只按 Markdown 默认值解析 | 改成 `schema: "paperclip/v1"` YAML |
| `--agents all` | 根目录 `AGENTS.md` 被导入成额外 Agent | 显式写 `--agents elon,jobs,...` |
| 在 Markdown 里写 `reportsToSlug` | 汇报关系不生效 | 子 Agent frontmatter 用 `reportsTo` |
| 没有 adapter 配置 | 可能 fallback 到 `claude_local` 或 `process` | 在 `.paperclip.yaml` 写 `adapter.type` |
| 只看普通 dry-run | 漏掉 manifest 字段是否真实读入 | 使用 `--json` 并脚本化检查 |
| 预置示例项目 | 和用户真实项目冲突 | 不创建 `projects/`，让用户运行时创建 |
| 把目标放进公司包 | 导入后目标缺失 | 用 goal CLI 或脚本单独创建 |

## 最低验证

完成前至少运行：

```bash
./runtest.sh
paperclipai company import /path/to/package --target new --new-company-name <name> --include company,agents --agents <slugs> --collision rename --dry-run --api-base <api-base> --json
```

如果已经导入，还要验证 `company get`、`agent list`、必要时 `goal list`。不要在验证命令输出前声明导入成功。
