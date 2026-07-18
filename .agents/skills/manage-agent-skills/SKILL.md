---
name: manage-agent-skills
description: Use when the user wants to install, configure, list, update, remove, sync, adopt, tag, search, or audit skills for multiple agents or workspaces through Skills Manager, skills-manager-cli, ~/.skills-manager, presets, global workspaces, project workspaces, or linked workspaces.
---

# Manage Agent Skills

## Core Rule

Use Skills Manager as the default control plane for skill work. Do not use `pnpx skills`, `npx skills`, manual clones, direct symlinks, or direct writes into agent skill directories unless the user explicitly asks to bypass Skills Manager.

Read configuration when useful. Do not modify agent configuration, Skills Manager settings, tool paths, sync mode, Git remote, API keys, `AGENTS.md`, `CLAUDE.md`, `.codex/config.toml`, or raw agent skill folders unless the user explicitly asks for that configuration change.

## First Checks

1. Confirm the CLI is available:

```bash
command -v skills-manager-cli
```

If missing, stop and tell the user Skills Manager CLI is not on `PATH`. Do not install tools or change config unless asked.

2. Use JSON whenever parsing command output:

```bash
skills-manager-cli --json repo status
skills-manager-cli --json tools list
skills-manager-cli --json skills list
skills-manager-cli --json presets list
```

Use `tools list` for the exact agent/tool id before passing `--tool`; do not guess ids.

## Scope Decision

Before writing, identify the target scope:

| User intent | Safe action |
| --- | --- |
| "看看/列出/检查/审计 skills" | Run read-only `repo status`, `tools list`, `skills list`, `presets list/current`. |
| "安装 skill" with no target | Ask which scope should receive it, or install library-only if the user only wants it imported. |
| "安装到某 agent / 所有 agent / 当前 preset" | Use `skills install <ref> --sync` or install then `presets add-skill` + `skills sync`. |
| "只放中央库" | Use `skills install <ref>` without sync. |
| "当前项目/某 workspace" | Prefer the Skills Manager project workspace or `--skills-root <path>` when operating on an explicit skills root. Do not invent raw `.claude/skills` or `.codex/skills` paths. |
| "改 agent 路径/同步模式/配置文件" | Ask for explicit confirmation before writing config. |

## Common Workflows

### Search

```bash
skills-manager-cli --json skills search "query" --limit 5
```

Show the best 1-3 matches with `install_ref`, source, and install count. Ask the user to choose when results are ambiguous.

### Install

```bash
# Git URL, local folder, or skills.sh ref
skills-manager-cli skills install <ref>

# Make it visible through the active preset and enabled agents
skills-manager-cli skills install <ref> --sync

# Confirm after install
skills-manager-cli --json skills list
skills-manager-cli --json skills show <ref>
```

For subdirectory skills in Git repos, use the repository URL form that includes the branch and subpath when available, such as `/tree/main/path/to/skill`.

### Presets and Sync

```bash
skills-manager-cli --json presets list
skills-manager-cli --json presets current
skills-manager-cli presets add-skill "<preset>" "<skill-ref>"
skills-manager-cli --json skills sync --dry-run
skills-manager-cli skills sync
skills-manager-cli skills sync --tool <tool-id>
```

Run `sync --dry-run` first when changing more than one target or when the target set is unclear.

### Update

```bash
skills-manager-cli --json skills check --all
skills-manager-cli skills update <skill-ref>
skills-manager-cli skills update --all
```

Use `check` before broad updates. Summarize which skills changed and which were already current.

### Remove

```bash
skills-manager-cli skills remove <skill-ref> --dry-run
skills-manager-cli skills remove <skill-ref> --yes
```

Always preview removal first. Removal deletes the central-library copy, synced targets, and DB row; ask for confirmation before `--yes` unless the user already gave clear destructive approval.

### Adopt Existing Skills

```bash
skills-manager-cli skills adopt <agent-skill-dir> --dry-run
skills-manager-cli skills adopt <agent-skill-dir>
skills-manager-cli skills adopt <agent-skill-dir>/<skill> --git-url <url-with-subpath>
```

Use `adopt` for skills that already exist outside the central library. If the original Git source is known, preserve updateability with `--git-url` and, when needed, `--git-subpath`.

### External Skills Roots

```bash
skills-manager-cli --skills-root <path> --json skills list
skills-manager-cli --skills-root <path> skills install <ref>
```

Use `--skills-root` only when the user gives an explicit external skills root or asks to manage a cloned/exported skills repo. The manager stores state under `~/.skills-manager/external/...`; do not manually create that state.

## Red Flags

- Installing with `pnpx skills` when the user did not explicitly bypass Skills Manager.
- Editing `~/.codex`, `~/.claude`, or project config files to make a skill visible.
- Syncing to all enabled agents when the user did not specify the target scope.
- Guessing a project workspace path instead of using Skills Manager or an explicit `--skills-root`.
- Removing or updating many skills without a preview/check step.
- Treating adopted local skills as Git-updatable when no source metadata was provided.
- Forgetting that the desktop app may need refresh/restart after CLI writes.
