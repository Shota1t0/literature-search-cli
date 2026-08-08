---
description: Author/co-authorship/co-citation network discovery via OpenAlex, extending from the current seen set (falls back to a PubMed-based co-authorship table while OpenAlex is not connected)
argument-hint: "[project-name] <author name or work>"
context: fork
agent: network
background: false
---

対象著者・論文について、現在の seen 集合を起点にネットワーク探索を行う。OpenAlex 未接続の間の代替動作は `network` の定義に従うこと。プロジェクト解決の作法は `CLAUDE.md` に従う。

$ARGUMENTS
