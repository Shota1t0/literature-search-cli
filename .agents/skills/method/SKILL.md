---
name: method
description: "Method appraisal (explicit invocation only) — map a method's assumptions, relation to alternatives, field standing, applicability and open points, and verify a pasted recommendation or claim with --from (Codex counterpart of Claude Code's /method)"
---

# `$method` — Claude Code の `/method` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$method` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/method.md`
- 役割手順の正本：`.claude/agents/scout.md`（「手法の採用判断モード（/method）」の節）

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。明示的に `$method` と呼ばれた時だけ使い、会話から暗黙に起動しない。
