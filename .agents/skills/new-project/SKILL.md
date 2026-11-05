---
name: new-project
description: "Create a new literature-search project (seen.jsonl, query-log.jsonl, landscape.md) (Codex counterpart of Claude Code's /new-project)"
---

# `$new-project` — Claude Code の `/new-project` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$new-project` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/new-project.md`
- 役割手順：なし（コマンド本文そのものが手順）

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
