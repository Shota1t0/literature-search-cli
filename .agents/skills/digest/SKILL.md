---
name: digest
description: "Summarize/fact-check target literature, output secondary material (local fallback while Obsidian is not connected). Zotero accumulation only runs if explicitly requested. (Codex counterpart of Claude Code's /digest)"
---

# `$digest` — Claude Code の `/digest` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$digest` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/digest.md`
- 役割手順の正本：`.claude/agents/synthesizer.md`

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。
