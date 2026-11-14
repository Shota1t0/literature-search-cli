---
description: Build the browsable view (view.html) of a project's searches, papers and question→answer records; propose question triage; restore records from past reports
argument-hint: "[project-name] [--restore [report.md ...]] [--no-fetch]"
allowed-tools: Read, Write, Glob, Grep, Bash
---

`$ARGUMENTS` に従い、プロジェクトのビュー（`workspace/<project>/view.html`）を作り、問いの整理を提案する。このコマンドは subagent を経由せず、あなた自身がその場で行う。規約は `AGENTS.md`「実行記録規約」「問いと答え規約」「ビュー規約」に従う。

`Bash` は `python tools/build_view.py ...` の実行だけに使う。runs/・findings/ の作成は `Write`（Codex は `apply_patch` の Add File）で行い、既存ファイルは書き換えない。`seen.jsonl`・`query-log.jsonl` には書かない（このコマンドは検索しない）。

## 1. プロジェクト解決とフラグ

- プロジェクトは AGENTS.md「カレントプロジェクト解決規約」で決める。`_scratch/` しか無い場合は「ビューを作るプロジェクトが無い」と伝えて終わる。
- `--restore [ファイル ...]`：報告書から記録を復元する（手順 4）。ファイル指定が無ければ候補を一覧して確認を取る。
- `--no-fetch`：書誌の取得（ネットワーク）をしない。

## 2. ビルド

1. `python tools/build_view.py <project> --check` で現状を確認する（論文数・実行記録数・記録の外の日数・書誌なしの件数・警告）。
2. `--no-fetch` が無ければ `--fetch-bib` 付きで、あれば付けずに `python tools/build_view.py <project>` を実行する。`--fetch-bib` は書誌・抄録が欠けている文献だけを照会する（PMID を PubMed に、DOI を OpenAlex に、NCT 番号を ClinicalTrials.gov に送る。取得済み・取得不能と記録済みのものは再照会しない。Codex では sandbox 外実行）。
3. 警告があれば内容を示す。runs/・findings/ の書き方の誤りによる警告は、どのファイルの何が原因かを示し、直し方を提案する（勝手に既存ファイルを書き換えない。直す場合は新しい findings で後勝ちに上書きするか、人の指示を受けてから）。

## 3a. 研究カードの項目の確認

- `view-config.json` が無ければ、landscape.md の目的とこれまでの検索のテーマから `viewer/card-presets.json` のひな形を 1 つ選んで提案し、承認されたら作る。
- runs/ のカードを見て、ひな形の項目に収まらない記述が繰り返し出ている（例：方法論のプロジェクトに臨床研究が多く混ざる、基礎研究で「動物種」を毎回 `system` に詰めている）場合は、項目の追加・名前の変更・`by_kind` の追加を提案する。変更は人の承認後に `view-config.json` を書き換える（設定ファイルなので書き換えてよい）。過去のカードは書き直さない。

## 3. 問いの整理の提案（findings/ がある場合）

`findings/*.json` を run-id 順に読んで問いごとに後勝ちでまとめ、`runs/*.json` の run-id 一覧と照らして、次の合図に当たる問いを表にして示す。

| 合図 | 提案 |
|---|---|
| `proposed: true`（未承認の新しい問い） | 承認（`proposed: false`）／却下（`dropped`） |
| 進行中なのに、直近 3 回の実行記録（`cmd` が `view` 以外）で `questions` に挙がっていない | 保留（`parked`） |
| 進行中で `points` が 1 つも無い | 中止（`dropped`）か、問いの言い換え |
| 内容が近い問いがある | 統合（`merged`、`merged_into` に統合先） |
| 下位の問いがすべて `answered` | 上位の答えをまとめ直し、回答済み（`answered`）に |
| 根拠（`points`）がすべて題名・抄録どまり | 状態はそのまま。ビューの依頼文から /digest での本文確認を勧める |

- 表には、問いの ID・文・現在の状態・合図・提案を並べる。合図が無ければ「整理の提案なし」とだけ書く。
- **人の承認を待ってから書く**。承認された変更だけを `findings/<run-id>.json`（run-id は `<今日>_<NN>_view`）に、変える項目だけで書く（例：`{"q": "Q5", "status": "parked"}`）。上位の答えをまとめ直す場合は、下位の答えと根拠から書き、新しい主張を足さない。同じ run-id で `runs/<run-id>.json` も作る（`{"run": …, "cmd": "view", "by": …, "date": …, "ask": "問いの整理", "intent": "承認された変更の要約", "questions": [変えた問い], "queries": [], "papers": [], "gaps": []}`）。書いたらビルドし直す。

## 4. 報告書からの復元（`--restore`）

実行記録（runs/）が無い時期の調査を、既に存在する過去の報告書から復元するための互換機能。新規の調査 Markdown を作る手順ではない。AGENTS.md「調査結果の保存・出力先」に従う。**書かれていないことは補わない**（推測で件数・判断・答えを作らない）。

1. 候補を挙げる：プロジェクト直下と `notes/` の `*.md`（`search-*`・`scout-report*`・`digest-*`・`citation-report*`・`network-report*` など）と `landscape.md`。既に復元済みの報告書（runs/ の `report` に挙がっているもの）は除く。どれをどの実行として復元するかを宣言し、確認を取ってから書く。
2. 報告書 1 本を実行 1 回として `runs/<日付>_<NN>_<cmd>.json` を作り、`"reconstructed": true` を付ける。日付は報告書の記載（無ければファイル名）。`cmd` は報告書の種類から（検索報告 → `scout`、digest → `digest`、引用評価 → `cite`、ネットワーク → `network`）。同じ日に複数の報告書がある場合、`NN` は報告書の時系列（「前回の〜に続く」等の記載）の順に振る。後から同じ日の別の報告書を復元する可能性があれば、時系列の位置に合わせて番号を空けておいてよい（問いの答えは run-id 順の後勝ちなので、順序を誤ると古い答えが新しい答えを上書きする）。
   - `queries`：報告書の検索式の節から写す。同じ日付の `query-log.jsonl` に同じ検索の行があれば、その `q` の文字列をそのまま使う（ビューがその行を「記録済み」とみなすため。`Grep` で日付を絞って探す）。ヒット数・確認件数は報告書にあるものだけ。
   - `papers`：報告書で個別に挙げた文献だけ。DOI・判断（主要文献 → `adopt` 等、報告書の書き方に従う）・確認の粒度は、報告書に書かれている範囲で。採用・保留した文献には、報告書の記述から研究カード（`card`）を作る（数値・対象・期間は報告書にあるものだけ。書かれていない項目は省く）。
   - `title_only`：報告書が「題名のみ確認」「その他候補」等として一覧にした文献（識別子と題名。理由が書かれていれば区分も）。
   - `gaps`：報告書が「未スクリーニング」「未確認」と書いた集合。
   - `report`：その報告書のパス（プロジェクトからの相対）。
3. 報告書と `landscape.md` に書かれた「何を問い、どう答えたか」から `findings/<同じ run-id>.json` を作る（`"reconstructed": true` を付け、`headline` も書く）。問いはすべて `"proposed": true`（人が承認する）。`points` の根拠は報告書に DOI が書かれたものだけ。問いの立て方は AGENTS.md「問いと答え規約」の基準に従い、細かくしすぎない（目安は上位の問い数個＋下位の問い）。
4. ビルドし直し、復元した実行・問いの数と、復元できなかった部分（DOI が書かれていない文献、件数の無い検索など）を報告する。

## 5. 報告

- `ビュー：workspace/<project>/view.html`（ブラウザで開く）
- 論文・試験・実行記録・記録の外の日数・問いの数、書誌の取得結果、警告
- 問いの整理の提案（手順 3）
- 実行記録の外にある日があり、復元できそうな報告書がある場合は `/view <project> --restore` を勧める
