---
name: normalize-reading-notes
description: Use when new Markdown notes are added under /Users/yi/obs/00_Clippings and/or /Users/yi/obs/03_Resources and need to be detected, skipped if already processed, and normalized to the Obsidian reading-note template
---

# 规范化阅读笔记

## 用途

当 `/Users/yi/obs/00_Clippings` 和/或 `/Users/yi/obs/03_Resources` 下新增 Markdown 笔记时，使用此 skill 只处理**尚未处理过的阅读笔记**，跳过已整理笔记，以及索引/个人/工具等非阅读笔记。

## 扫描路径（roots）

**仅**以下两根目录（必须同时扫描）：

```text
/Users/yi/obs/03_Resources
/Users/yi/obs/00_Clippings
```

规则：

- 使用 `rglob("*.md")`
- 跳过路径中任意以 `.` 开头的目录段（如 `.ocr_work`）
- 不要扫描 Inbox / Projects / Areas 等其它目录

## 笔记类型与是否处理

在 skill roots 内，`type` **只允许**这 6 个：

| `type` | 含义 | 本 skill |
|--------|------|----------|
| `reading_note` + `status: ai-summarized` | 已规范化阅读笔记 | **跳过** |
| `reading_note`（其它 status） | 未完成的阅读笔记 | **处理** |
| `index` | 目录 / 索引入口 | **跳过** |
| `personal_note` | 用户本人笔记 | **跳过** |
| `tool_note` | 工具备忘 / 附属 extract | **跳过** |
| `ai_chat` | AI 对话记录 | **跳过** |
| `ai_research` | AI 研究 / 调研 / 综合分析 | **跳过** |
| （无 type / 非法 type） | 待分类 | **先走分类清单**，勿直接当阅读笔记硬套 |

遗留映射：`resource_index` → `index`；`research_report` → `ai_research`。  
分类清单：`06_Metadata/笔记类型分类检查清单.md`（Obsidian wikilink + 二级 `- [ ]` 类型）。

## 执行流程

1. 读取模板：`/Users/yi/obs/06_Metadata/Templates/阅读笔记模板.md`
2. 运行 `scripts/list_pending.py` 看候选；若存在大量未分类，先 `scripts/classify.py generate`，等用户勾选后 `apply`
3. 若待处理阅读笔记为 `0`，直接报告并停止，不修改文件
4. 每篇待处理阅读笔记调用一个独立 subagent
5. 每个 subagent 只能编辑自己分配的那一篇文件
6. 全部完成后运行 `scripts/check.py`

## 脚本

目录：`skills/normalize-reading-notes/scripts/`（本仓库 `manage-agents` 根目录）

| 脚本 | 作用 |
|------|------|
| `list_pending.py` | 列出 pending 候选（双 roots） |
| `classify.py generate` | 生成/刷新分类检查清单（wikilink + 二级 checkbox） |
| `classify.py apply` | 按勾选写入 6 种 type 之一 |
| `classify.py unify` | 把遗留/非法 type 映射或剥成 pending |
| `classify.py stats` | 统计分类与 raw type |
| `check.py` | 自动质检（见下） |

示例（在 `manage-agents` 仓库根目录执行）：

```bash
python3 skills/normalize-reading-notes/scripts/classify.py unify
python3 skills/normalize-reading-notes/scripts/list_pending.py --group
python3 skills/normalize-reading-notes/scripts/classify.py generate
python3 skills/normalize-reading-notes/scripts/classify.py apply
python3 skills/normalize-reading-notes/scripts/check.py
```

### check.py 检查项

对 `type: reading_note`（默认仅 `status: ai-summarized`）检查：

- `local_path` 有值时路径是否存在
- 是否出现与 title/文件名重复的正文一级标题
- 代码块外是否有多余一级标题（仅允许结构标题）
- 是否含 git 冲突标记（`<<<<<<<` / `=======` / `>>>>>>>`）
- `# AI 总结` 是否为空或占位
- frontmatter 是否仅含模板字段、顺序是否正确、是否含禁用字段
- `source` 是否属于强制枚举
- 是否缺少 `# 我的笔记` / `# AI 总结` / `# 原文`

## 筛选逻辑（与 list_pending 一致）

```bash
python3 skills/normalize-reading-notes/scripts/list_pending.py
```

等价规则（实现见 `scripts/lib.py`）：

```python
roots = [
    Path("/Users/yi/obs/03_Resources"),
    Path("/Users/yi/obs/00_Clippings"),
]
# allowed: reading_note | index | personal_note | tool_note | ai_chat | ai_research
# skip if type in {index, personal_note, tool_note, ai_chat, ai_research}
# skip if type == reading_note and status == ai-summarized
# else pending (incl. untyped / invalid type)
```

## 单篇处理规则

每篇待处理**阅读笔记**必须整理为：

```yaml
---
title:
author:
type: reading_note
status: ai-summarized
source:  # 强制枚举，见下
web_url:
local_path:
getnote_note_id:
getnote_title:
created:
tags:
---
```

**`source` 强制枚举（仅允许下列之一）：**

```text
网页 | 微信公众号 | X | 小红书 | 知识星球 | 飞书 | YouTube | GitHub
| 课程 | 直播 | 公开会议 | 内容平台
| 本地文档 | 本地保存网页 | 本地音视频 | AI对话
```

禁止把路径、URL、作者名、复合描述写入 `source`。实现与校验见 `scripts/lib.py` 的 `ALLOWED_SOURCES` / `normalize_source()`；`check.py` 对非法值报 `source_invalid`。

要求：

- frontmatter 只能保留以上字段，且顺序一致。
- `source` 必须是枚举值之一（规范化时用 `normalize_source` 映射旧值）。
- 删除所有非模板字段，包括但不限于：
  `original_type`、`source_video`、`source_type`、`source_html`、`converted_at`、`cleaned_at`，
  以及 `source_path`、`imported_at`、`source_mtime`、`source_sha256` 等扩展字段
  （来源路径统一放在 `local_path`；需要时可在正文「来源信息」中说明）。
- 如果旧字段 `source_video` 或 `source_html` 里有本地路径，把路径迁移到 `local_path`，然后删除旧字段。
- 正文一级标题顺序固定为：
  `# 我的笔记`
  `# AI 总结`
  `# 简体中文翻译`（仅当原文不是简体中文时保留）
  `# 原文`
- 如果原文不是简体中文，必须生成 `# 简体中文翻译` 并放在 `# 原文` 之前；`# 原文` 保留可恢复的来源正文，不改写。
- 如果原文已是简体中文，删除 `# 简体中文翻译` 小节。
- 原正文整体放入 `# 原文`。如果原文有 1 个一级标题，删除。如果原文有多个一级标题，所有标题降级。
- 不在正文写与 `title`/文件名相同的重复一级标题。
- 如果原文里有明显「我的想法 / 我的笔记 / 个人想法」，移入 `# 我的笔记`，不要重复放在 `# 原文`。
- 如果没有实际 AI 总结，基于原文生成 100-600 字中文总结，格式为：

```markdown
# AI 总结

> [!tip] 核心观点
> 这里写总结
```

- 不联网。
- 不补充原文之外的信息。
- 不改写原文内容。
- **禁止**把 `index` / `personal_note` / `tool_note` / `ai_chat` / `ai_research` 改成阅读笔记结构。

## 最终校验

完成后必须运行 `scripts/check.py`，并确认：

- 本次待处理阅读笔记都已变成 `type: reading_note` + `status: ai-summarized`
- 已处理过的旧笔记与非 reading_note 类型没有被误改
- frontmatter 只含模板字段且顺序正确
- 不存在禁用字段
- 代码块外一级标题只允许结构标题
- `# AI 总结` 不是空占位
- 有 `local_path` 则路径存在（外置盘应已挂载）
- 无 git 冲突标记

## 最终报告

报告：

- 扫描 roots 与 Markdown 总数
- 跳过：已处理 / index / personal_note / tool_note / ai_chat / ai_research 各多少
- 处理多少篇阅读笔记
- `check.py` 是否通过
- 是否发现原文异常但未改写
