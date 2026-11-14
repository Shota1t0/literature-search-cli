---
description: Summarize/fact-check target literature in conversation. Obsidian output and Zotero accumulation each require an explicit request.
argument-hint: "[project-name] [target papers, or omit for the full current seen set] [--zotero to also accumulate into Zotero]"
context: fork
agent: synthesizer
background: false
---

蓄積・出力ステップ（要約・ファクトチェック → 会話で報告）を実行する。**Zotero への追加は既定では行わない**。`$ARGUMENTS` に「Zoteroに登録」「ライブラリに追加」等の明示的な要求が含まれる場合のみ Zotero 蓄積（追加・ノート添付・`zot` フラグ更新）も行う。Obsidian 出力も、その保存を明示的に指示された場合だけ行う。方向確定後の明示呼び出しであることを前提に、省略せず要約・チェックを行うこと。プロジェクト解決・台帳更新・調査結果の保存先の作法は `AGENTS.md` に従う。

$ARGUMENTS
