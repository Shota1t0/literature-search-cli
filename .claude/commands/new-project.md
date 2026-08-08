---
description: Create a new literature-search project (seen.jsonl, query-log.jsonl, landscape.md)
argument-hint: <project-name>
allowed-tools: Write, Read, Glob
---

`$ARGUMENTS` はプロジェクト名。このコマンドは subagent を経由せず、あなた自身がその場で以下を行う（README §5.1 準拠、サブエージェント不要な軽い glue 処理）。

1. `$ARGUMENTS` の前後空白を除去し、プロジェクト名として扱う。ファイルシステムで安全なスラッグ（英数字・ハイフン・アンダースコア推奨）か確認し、明らかに不適切（空、パス区切りを含む等）なら実行前にユーザーに確認する。
2. `Glob("workspace/*")` で既存プロジェクト一覧を確認し、同名の `workspace/<name>/` が既に存在する場合は **上書きせず** ユーザーに確認してから進める。
3. 以下の 3 ファイルを作成する：
   - `workspace/<name>/seen.jsonl`（空ファイル）
   - `workspace/<name>/query-log.jsonl`（空ファイル）
   - `workspace/<name>/landscape.md`（下記テンプレートの `{name}` を実際のプロジェクト名に置換）

```markdown
# {name}

## 目的
（この調査が何を目指すか。1〜2行。例：PD の LEDD 進展を予測する
生存解析手法の選定と先行手法の網羅。digital biomarker としての位置づけを固める。）

## 探索済みの軸

## 手薄な軸

## 効いた検索軸

## 効かなかった／広すぎた軸
```

4. 作成した 3 ファイルのパスを提示して完了を報告する。`landscape.md` の「目的」欄は空のままでよいが、ユーザーがこの場で目的を教えてくれた場合はテンプレートのコメント行を実際の目的文に置き換えてよい。
