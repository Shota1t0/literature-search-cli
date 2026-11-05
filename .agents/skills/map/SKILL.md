---
name: map
description: "Phase 2 — field overview via OpenAlex concept/group_by over the current seen set (falls back to a local tally while OpenAlex is not connected); updates landscape.md (Codex counterpart of Claude Code's /map)"
---

# `$map` — Claude Code の `/map` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$map` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/map.md`
- 役割手順の正本：`.claude/agents/cartographer.md`

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
