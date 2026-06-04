# Agent Trash

This is the global fallback quarantine area for Codex-managed file operations.

Default deletion semantics are move-to-trash with a 30-day retention window. Use the managed root's own `.agents/trash/` folder when the operation belongs clearly to one managed root.

Exception: `/Volumes/Passport/prompts` may be directly removed after its migration into `/Users/yi/obs/06_Metadata/Prompts/Archive/` is verified.
