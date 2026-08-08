---
description: Compound-intent entry point — decomposes a multi-phase request and dispatches to the needed subagents (scout/cartographer/network/citation/synthesizer)
argument-hint: <compound natural-language request>
context: fork
agent: orchestrator
background: false
---

複合意図のリクエストを分解し、必要な subagent にディスパッチする。分解結果は実行前に必ず宣言すること。`orchestrator` の定義とプロジェクト解決の作法（`CLAUDE.md`）に従う。

$ARGUMENTS
