---
name: ask
description: "Compound-intent entry point — decomposes a multi-phase request and dispatches to the needed subagents (scout/cartographer/network/citation/synthesizer) (Codex counterpart of Claude Code's /ask)"
---

# `$ask` — Claude Code の `/ask` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$ask` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/ask.md`
- 役割手順の正本：`.claude/agents/orchestrator.md`

このスレッドが `orchestrator` を演じ、必要な役割を `.codex/agents/` の custom agent（`scout` / `cartographer` / `network` / `citation` / `synthesizer` の 5 種のみ）として spawn する（共通作法 3・4）。orchestrator 自身はソースに触れず、ファイルも書かない。
