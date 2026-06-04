# Agent Index

Codex stores rebuildable machine indexes here instead of inside Obsidian.

Allowed generated formats include SQLite, JSON, CSV, and Markdown dashboards. Generated index files must be treated as cache-like state: useful for lookup, but never the only source of truth.

Indexes should exclude absolute forbidden areas:

- `.env`
- `.env.*.local`
- `/Volumes/Passport/private`
