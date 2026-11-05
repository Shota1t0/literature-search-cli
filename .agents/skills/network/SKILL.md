---
name: network
description: "Author/co-authorship/co-citation network discovery via OpenAlex, extending from the current seen set (falls back to a PubMed-based co-authorship table while OpenAlex is not connected) (Codex counterpart of Claude Code's /network)"
---

# `$network` — Claude Code の `/network` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$network` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/network.md`
- 役割手順の正本：`.claude/agents/network.md`

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
