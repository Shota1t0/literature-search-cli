---
name: view
description: "Build the browsable view (view.html) of a project's searches, papers and question→answer records; propose question triage; restore records from past reports (Codex counterpart of Claude Code's /view)"
---

# `$view` — Claude Code の `/view` に対応する Codex アダプタ

手順はここに書かない（正本は下記。`AGENTS.md`「デュアルランタイム維持規約」）。`AGENTS.md`「Codex アダプタ共通作法」に従い、次の正本を読んでから実行する。手順中の `$ARGUMENTS` は、ユーザーが `$view` に続けて書いた入力全体と読み替える。

- コマンド正本：`.claude/commands/view.md`
- 役割手順：なし（コマンド本文そのものが手順）

subagent は起動せず、このスレッドで直接実行する（共通作法 3）。`python tools/build_view.py <project> --fetch-bib` はネットワークを使うので sandbox 外で実行する。
