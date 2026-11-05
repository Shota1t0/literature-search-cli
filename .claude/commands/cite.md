---
description: Phase 3 — Scite-based citation evaluation for one DOI or a group (--topic/--recent N) within the current seen set
argument-hint: "[project-name] <DOI> | --topic \"<text>\" | --recent N"
context: fork
agent: citation
background: false
---

Phase ③（精査）を実行する。単一 DOI／`--topic`／`--recent N` のどのモードかを `$ARGUMENTS` の形から判定し、`citation` の定義に従って処理する。プロジェクト解決の作法は `AGENTS.md` に従う。

$ARGUMENTS
