本项目用来帮助用户个性化修改 agents 的配置文档或开发 skills.

## 个性化修改 agents 的配置文档

你需要管理 Codex 和 CLAUDE 的配置, 不用管理其他 agents.

如果用户的需求不明确, 询问用户. 

除非用户指定工作文件夹, 修改~/.codex/AGENTS.md 和/或 ~/.claude/CLAUDE.md, 而不是项目文件夹中的.

如果用户没有指明具体的 agents, 询问用户.

检查原本的 AGENTS.md / CLAUDE.md, 寻找需要修改地方. 然后根据用户的需要, 进行修改. 在不改变原意的情况下修饰用户的需求, 使得文档简明且语言风格一致.

修改前, 让用户审阅 diff.

## 开发 skills

Skill应该放在 skills 文件夹的子文件夹下。

Skill开发需要遵从 skill 的最佳实践。
