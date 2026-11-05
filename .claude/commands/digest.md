---
description: Summarize/fact-check target literature, output secondary material (local fallback while Obsidian is not connected). Zotero accumulation only runs if explicitly requested.
argument-hint: "[project-name] [target papers, or omit for the full current seen set] [--zotero to also accumulate into Zotero]"
context: fork
agent: synthesizer
background: false
---

蓄積・出力ステップ（要約・ファクトチェック → 二次情報出力）を実行する。**Zotero への追加は既定では行わない**。`$ARGUMENTS` に「Zoteroに登録」「ライブラリに追加」等の明示的な要求が含まれる場合のみ Zotero 蓄積（追加・ノート添付・`zot` フラグ更新）も行う。方向確定後の明示呼び出しであることを前提に、省略せず要約・チェックを行うこと。プロジェクト解決・台帳更新の作法は `AGENTS.md` に従う。

$ARGUMENTS
