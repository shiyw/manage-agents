---
name: codex-test-hooks
description: 当项目需要配置 Codex Hooks 在代码编辑后或 Stop 前自动运行测试时使用，尤其是用户提到 runtest.sh、run-tests.sh、PostToolUse、Stop hook 或改完文件自动测试。
---

# Codex 测试 Hooks

## 要做什么

在目标项目根目录配置 Codex hooks，让 Codex 在代码编辑后和 `Stop` 阶段运行 `./runtest.sh`。不要改业务代码，不要改测试文件。

创建下面这些文件。如果 `.agents/hooks.json` 已存在，只合并需要的 hook group，保留原有无关配置。

## `.agents/hooks/run-tests.sh`

```sh
#!/usr/bin/env bash
set -euo pipefail

[ -x ./runtest.sh ] || {
  echo "缺少可执行的 ./runtest.sh。请写入当前项目真实的测试命令。" >&2
  exit 2
}

out="$(mktemp -t codex-runtest.XXXXXX)"
set +e; ./runtest.sh >"$out" 2>&1; status=$?; set -e

if [ "$status" -eq 0 ]; then
  rm -f "$out"; printf '{}\n'
  exit 0
fi

{
  echo "测试失败。复现命令：./runtest.sh"
  sed -n '1,160p' "$out"
  echo
  echo "退出码：$status"
} >&2

rm -f "$out"; exit 2
```

然后运行：

```bash
chmod +x .agents/hooks/run-tests.sh
```

## `.agents/hooks.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch|Edit|Write",
        "hooks": [{ "type": "command", "command": "bash .agents/hooks/run-tests.sh" }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "bash .agents/hooks/run-tests.sh" }]
      }
    ]
  }
}
```

## `runtest.sh`

如果缺失，先尝试推断真实测试命令：

- 有 `package.json` 且 `scripts.test` 可用：优先写 `pnpm test`。
- 有 `Makefile` 的 `test` 目标：写 `make test`。
- 有 `pyproject.toml`、`pytest.ini`、`tests/` 或 `test/`：优先写 `uv run pytest`。

能推断时，创建：

```bash
#!/usr/bin/env bash
set -euo pipefail

<真实测试命令>
```

推断不了时，才创建 fail-fast 模板：

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "runtest.sh 还没有配置。请替换成当前项目真实的测试命令。" >&2
exit 2
```

然后运行 `chmod +x runtest.sh`。

## 验证

```bash
cat .agents/hooks.json | python3 -m json.tool
ls -la .agents/hooks/run-tests.sh
```
