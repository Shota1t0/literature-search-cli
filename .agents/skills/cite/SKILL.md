---
name: cite
description: "Phase 3 — Scite-based citation evaluation for one DOI or a group (--topic/--recent N) within the current seen set (Codex counterpart of Claude Code's /cite)"
---

# `$cite` — Claude Code の `/cite` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$cite` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/cite.md`
- 役割手順の正本：`.claude/agents/citation.md`

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
