---
name: scout
description: "Phase 1 — exhaustive precise search (PubMed) + adjacent discovery, new-vs-seen detection, adjacent-axis proposals (Codex counterpart of Claude Code's /scout)"
---

# `$scout` — Claude Code の `/scout` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$scout` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/scout.md`
- 役割手順の正本：`.claude/agents/scout.md`

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
