# 文献調査CLI — プロジェクト規約（Claude Code / Codex 共通）

このリポジトリは、AI コーディングエージェントの subagent + MCP を用いて文献調査（先行研究調査・メソッド検討・MSL の KOL 調査）を体系化する CLI システムである。**Claude Code と Codex のどちらでも同じ手順で動く状態を保つ**。仕様の全体像は `README.md` を参照。

この文書は、両ランタイムの全 subagent・コマンド・skill が依拠する共通規約の**正本**である。Codex は `AGENTS.md` を直接読み込み、Claude Code は `CLAUDE.md` の `@AGENTS.md` 経由で読み込む。ランタイムごとの差分は末尾の「ランタイム対応」と「デュアルランタイム維持規約」にまとめる。

## 設計原則（README「設計原則」準拠）

- **プログラム最小**：実装は薄い glue に留め、思考ロジックは subagent のプロンプトに寄せる。判断を含まない整形・検証だけは `tools/` の最小スクリプトで行ってよい（現在は `tools/build_view.py` のみ。「ビュー規約」）。
- **フレームワーク不変**：構造を頻繁に変えない。
- **状態は最小**：永続状態は `seen.jsonl`（プロジェクト単位）のみが判定に使われる。`query-log.jsonl`・`runs/`・`findings/` は参照専用で判定には使わない。
- **連鎖の事前固定はしない**：subagent は定義済み順序で自動連鎖させない。
- **フェーズ移行は人間が握る**：探索→俯瞰→精査の移行は人間が判断する。
- **透明性**：subagent / orchestrator は「どう解釈し、何をするか」を実行前に必ず言語化する。

## 台帳と記録（役割を混同しない）

| 台帳・記録 | 中身 | 答える問い | 判定に使うか | 更新者 | 読み方 |
|---|---|---|---|---|---|
| **seen.jsonl** | 到達論文（DOI 正本）と登録試験（NCT 番号正本） | この論文・試験を見たか | する | scout（新規追加）/ synthesizer（zot 更新） | 機械が照合 |
| **query-log.jsonl** | 打ったクエリ（生文字列） | この角度で検索したか | しない（参照のみ） | scout | 「もっと他を」要求時のみ読む |
| **landscape.md** | 目的・効いた軸・手薄な軸 | どこへ向かうか | しない | cartographer / 人間 | scout/orchestrator が委譲判断の材料として読む |
| **runs/*.json** | 1 回の実行の事実（依頼・解釈・クエリと件数・論文ごとの判断・残り） | 何をしたか | しない | 記録に対応したコマンド（「実行記録規約」） | 人がビューで見返す。続きの依頼で scout が読む |
| **findings/*.json** | 問いと、その時点の答え・根拠・未解決 | 何を問い、どう答えたか | しない | 同上・/view（状態の整理） | 同上 |

役割は完全に分離している。混ぜない。runs/ は事実、findings/ は解釈（後から版を足して更新する）。どちらも新規ファイルを足すだけで、既存ファイルは書き換えない。

生成物（消しても作り直せる。判定にも記録にも使わない）：`view.html`（ビュー）、`bib-cache.jsonl`（書誌・抄録のキャッシュ。`tools/build_view.py --fetch-bib` が追記）。設定：`view-config.json`（研究カードの項目。「研究カード規約」）。

## seen.jsonl 規約

- 1 論文（または 1 登録試験）1 行の JSONL。**追記専用**（append-only）。既存行は書き換えない。
- **正本 ID は DOI**。各ソースの固有 ID は `srcs` に併記する。

```jsonc
{
  "doi": "10.1038/s41586-025-xxxxx",   // 正本。欠損時は null
  "srcs": {                             // 各ソースの固有 ID（取得できたものだけ）
    "pmid": "38xxxxxx",
    "oaid": "W27xxxxx",
    "s2":   "corpusId:xxxxx"
  },
  "seen": "2026-08-07",                 // 初回到達日
  "zot":  false                         // Zotero 所持フラグ
}
```

- **DOI 欠損時**（preprint 等）は `"doi": null` とし、タイトル+出版年で近似照合する。近似照合したものは報告時に `⚠ DOI欠損・近似照合` フラグを立てる。
- **登録試験の行**（ClinicalTrials.gov 由来。scout が追記）は `"type": "trial"` を持ち、**NCT 番号が正本**。`zot` は持たない。`type` の無い行はすべて論文として扱う（既存行との互換のため）。

  ```jsonc
  {"type": "trial", "doi": null, "srcs": {"nct": "NCT01494701"}, "seen": "2026-11-07"}
  ```

  - 照合キー：論文は DOI（欠損時はタイトル+出版年）、試験は `srcs.nct`。dedup（後勝ち）もこのキーごとに行う。
  - 試験の行は「この試験を見たか」の判定だけに使う。試験に紐付く論文は、論文として別の行に記録する（試験の行に論文 ID を書かない）。
  - **論文を対象とする処理**（DOI 一覧の作成、OpenAlex・Scite での照合、`--recent N` の件数、DOI 欠損行の別枠集計など）は、`"type": "trial"` の行を除いてから行う。
- **フラグ更新は追記で行う**：既存行を書き換えるのではなく、同じ DOI で更新後の値（例：`"zot": true`）を持つ新しい行を追記する。読み手は常に **DOI ごとに「最後の出現」を正** とみなし、そのために全行読み込み後 DOI をキーに dedup（後勝ち）してから使う。
- **更新方法**：既存行には一切触れず、末尾に新しい行を足す。Claude Code では `Read` で現在の全内容を取得 → 追記後の全文を組み立て → `Write` で書き戻す。Codex では `apply_patch` で末尾に行を追加する。どちらもシェルのリダイレクト（`>>` 等）や `Add-Content` / `Out-File` / `Set-Content` には依存しない（Windows/Bash 両対応、文字コード・BOM・改行の混入防止のため）。プロジェクトが存在しない（`_scratch/` 実行時）は何も書き込まない。
- **引用関係で出てきただけの論文は追記しない**：citation graph・被引用一覧・共引用などで名前が挙がっただけの論文は、題名か抄録を確認するまで `seen.jsonl` に入れない（入れると、読んでいない論文が「既出」として次の検索で弾かれる）。関係そのものは実行記録（runs/）に残す。

## ID 正規化ルール

- どのソースから取得した論文も、**まず DOI に正規化**してから `seen.jsonl` と照合する。
- PubMed 由来：`mcp__pubmed__convert_article_ids` や `get_article_metadata` で DOI を取得。
- DOI が取得できない場合はタイトル+出版年で近似照合し、結果に明示的にフラグを立てる。
- ClinicalTrials.gov 由来の登録試験は論文ではないので DOI に正規化せず、NCT 番号（`NCT` + 8 桁、大文字）で照合する。
- これにより、PubMed で見た論文を将来 OpenAlex 等で再発見しても既出と判定できる（ソース横断の重複回避）。

## query-log.jsonl 規約

- スキーマ：`{"src":"pubmed","q":"GENE-A pathway regulation","ran":"2026-08-07"}`
- 追記専用。**dedup 判定には絶対に使わない**（同じクエリ文字列を再実行してよい。着目点が違えば拾う論文も変わるため）。
- 読むのは、ユーザーが明示的に「もっと他を」「別の角度で」等と求めた時だけ。scout はそのプロジェクトの過去クエリを提示し、被らない新しい角度を組んで再検索する。生ヒットに混じる既出論文は依然 `seen.jsonl` が弾く。
- 論文レベルの重複回避は常に `seen.jsonl` の仕事。角度の重複回避と論文の重複回避は別レイヤ。

## 実行記録規約（runs/）

「何を検索したか後から忘れる」ことへの対策。1 回の実行で 1 ファイルを `workspace/<project>/runs/<run-id>.json` に新規作成し、作成後は書き換えない。判定には使わない。`_scratch/` 実行時は書かない。

- **記録に対応したコマンド**：scout（`/scout` と、`/ask` から呼ばれた scout）と `/view`（報告書からの復元）。cartographer / network / citation / synthesizer は未対応（対応するまで、その実行はビューに「実行記録の外」として出るか、出ない）。
- **run-id**：`<YYYY-MM-DD>_<NN>_<cmd>`（例：`2026-11-12_01_scout`）。`NN` はその日のそのプロジェクトでの通し番号（`Glob("workspace/<project>/runs/<日付>_*.json")` の件数 + 1、2 桁）。ファイル名と `run` を一致させる。
- **書き方**：Claude Code は `Write` で新規作成。Codex は `apply_patch` の Add File。JSON は UTF-8・インデント付きでよい。

```jsonc
{
  "run": "2026-11-12_01_scout",
  "cmd": "scout",
  "by": "claude-code",                     // claude-code / codex
  "date": "2026-11-12",
  "ask": "抑うつ・不安…の経過を前向き・後ろ向きコホートで",   // 依頼の要旨（ユーザーの言葉に近く）
  "intent": "自然言語。症状名×縦断研究の語で…",            // 実行前に宣言した解釈・ソース選択
  "questions": ["Q3", "Q4"],               // この実行が答えようとした問い（findings の q）
  "queries": [
    {"id": "R1", "src": "pubmed", "label": "抑うつの縦断コホート",   // 人が読む短い見出し
     "q": "…入力した式（query-log の q と同じ文字列）…",
     "actual": "…query_translation（入力とずれた時だけ）…",
     "hits": 255, "screened": {"title": 25, "abstract": 4, "fulltext": 0},
     "note": "任意の補足"}
  ],
  "papers": [
    {"doi": "10.1002/mds.22572", "pmid": "19412939", "via": ["R1"], "new": true,
     "questions": ["Q2"],                  // どの問いのために読んだか（findings の q）。実行の対象の問いが 1 つなら省略可
     "depth": "abstract",                  // title / abstract / fulltext（実際に読んだ最も深い粒度）
     "decision": "adopt",                  // adopt（採用）/ hold（保留）/ exclude（除外）
     "why": "…",                           // 任意。採否の理由がカードから読み取れない時だけ（保留・除外の理由など）
     "card": {"kind": "original",          // 研究カード（「研究カード規約」）。adopt / hold には必ず付ける
              "claim": "閾値以上の抑うつ症状の47%が6か月以内に寛解",
              "caveat": "症状閾値の寛解で、自然治癒率ではない",
              "slots": {"design": "RCT二次解析", "population": "早期未治療PD 413例", "followup": "12–18か月"}},
     "bib": {"title": "…", "year": 2009, "first_author": "Ravina", "journal": "Mov Disord"}}
    // 登録試験は {"nct": "NCT01106976", …}。DOI 欠損は {"doi": null, "pmid": "…", "bib": {…}}
  ],
  "title_only": [                          // 題名だけ見て抄録へ進めなかった候補（識別子と理由だけ）
    {"pmid": "36603690", "doi": "10.1016/j.arr.2022.101840", "title": "…", "via": "R1", "questions": ["Q2"],
     "reason": "off_topic"}                // off_topic 対象外 / design 設計が不一致 / duplicate 重複 / later 保留 / other。分からなければ省く
  ],
  "gaps": [{"query": "R1", "kind": "unscreened", "n": 230, "note": "上位25件以外は題名も未確認"}],
  "resolves_gaps": ["2026-11-07_01_scout#R2"],   // 前の実行の gaps を片付けた時だけ（<run-id>#<query>）
  "sources": {"theme": "臨床", "searched": ["PubMed", "ClinicalTrials.gov"],
              "not_run": ["preprint（OpenAlex）"], "no_access": ["医中誌", "学会抄録"]},
  "report": "search-2026-11-12-symptom-courses.md"   // 文章の報告書を書いた時だけ（プロジェクト内の相対パス）
}
```

- `papers` には、報告で一覧表示した論文・試験（抄録以上を読んだもの）を**既出も含めて全部**入れる。
- `papers[].questions`（と `title_only[].questions`）は、その文献をどの問いのために読んだか。ビューで「問いから関連文献を全部見る」「文献を問いで絞る」に使う（上位の問いで絞ると下位の問いの文献も含む）。実行が複数の問いを扱う場合は必ず書く。答えの根拠（findings の `points`）にした文献は、書かなくてもその問いに紐づく。
- `title_only` には、題名を確認したが抄録へ進めなかった候補を入れる（識別子・題名・理由の区分だけ。seen.jsonl には入れない）。取得すらしていない残りのヒットは `queries[].screened` と `gaps` に件数で残す。
- `"reconstructed": true`（報告書から復元した記録）のファイルに限り、同じ報告書から作り直す時は置き換えてよい。それ以外の runs/・findings/ は書き換えない。
- `queries[].q` は `query-log.jsonl` に書いた文字列と同じにする（ビューは一致した query-log 行を「記録済み」とみなし、「実行記録の外」として重複表示しない）。
- 任意の追加項目は `x-` で始まるキーで足してよい（ビューの詳細欄にそのまま出る）。プロジェクト固有の情報はこれで足し、共通項目の意味は変えない。

## 問いと答え規約（findings/）

見返すときの入口。分類ではなく「どんな疑問にどう答えたか」を残す。

- 答えを出した（更新した）実行ごとに `workspace/<project>/findings/<run-id>.json` を新規作成する（run-id は同じ実行の runs/ と同じ）。既存ファイルは書き換えない。
- 同じ問い（`q`）が複数のファイルにあれば、**フィールド単位で後勝ち**（run-id の順）。状態だけ変える時は `{"q": "Q3", "status": "parked"}` のように変える項目だけ書けばよい。古い版も残るので、ビューで変更履歴として見られる。

```jsonc
{
  "run": "2026-11-12_01_scout",
  "date": "2026-11-12",
  "findings": [{
    "q": "Q3",                              // プロジェクト内で一意。Q + 通し番号
    "question": "PDの抑うつは経過とともにどう変わるか",
    "parent": "Q1",                         // 上位の問い（無ければ省略）
    "purpose": "目的①：症状別の進行パターンの把握",   // landscape.md の目的のどれに対する問いか
    "status": "active",                     // active / answered / parked / merged / dropped
    "merged_into": null,                    // merged の時だけ
    "proposed": true,                       // 新しく立てて、まだ人が承認していない問い
    "pinned": false,                        // 人が固定表示を指示した問い
    "headline": "約半数は早期に閾値未満になるが、持続・新規発症も多い",   // 1 行の答え（60 字程度）。一覧に出る
    "answer": "早期に寛解する例が約半数ある一方…",
    "points": [
      {"text": "早期PDで閾値以上の抑うつの47%が6か月以内に寛解",
       "dois": ["10.1002/mds.22572"],       // 根拠。登録試験は NCT 番号を書いてよい
       "depth": "abstract"}                 // この主張を確かめた粒度
    ],
    "conflicts": ["不安：状態が安定する研究と、軽症群で改善する研究がある"],
    "open": ["尺度・閾値の違いの影響", "後ろ向き研究は未確認"]
  }]
}
```

- **問いを立てる基準**：答えによって次の行動や landscape.md の目的への答えが変わるものだけを問いにする。「〇〇の論文はあるか」程度の確認は問いにせず、runs/ に残すだけにする。目的のどれにもつながらない問いは立てない。
- **既存の問いを優先**：書く前に `findings/*.json` を読み、既存の問い（下位の問いを含む）に収まるなら新しく立てない。収まらない時だけ新しい問いを `"proposed": true` で書き、報告の末尾で「新しい問いの提案」として示す。承認・却下は人が行い、`/view` が状態の更新を書く。
- **答えは 3 段で書く**：`headline` は一覧で読む 1 行（結論だけ。数値や但し書きは入れない）、`answer` は文章、`points` は主張 1 つ＋根拠の DOI＋確かめた粒度。根拠の DOI は、同じ実行の runs/ の `papers` か `seen.jsonl` にあるものだけ（無い DOI はビルド時に警告になる）。
- **状態の意味**：`active` 進行中／`answered` 回答済み（当面これ以上追わない）／`parked` 保留（今は追わない）／`merged` 他の問いに統合（`merged_into` に統合先）／`dropped` やめた。どれも消さずに残し、ビューでは既定で隠す。

## 研究カード規約

個々の文献が「どういう研究か」を一目で分かるようにする短い記述。全文献ではなく、**抄録以上を読んで採用・保留した文献だけ**に付ける（runs/ の `papers[].card`）。題名だけ見た候補や実行記録の外にある文献には付けない（ビューは抄録の冒頭で代える）。

- **共通の 3 項目（必須）**：`kind`（`original` 原著／`review` レビュー／`guideline` ガイドライン／`method` 手法／`data` データ・資源／`protocol` プロトコル・登録／`other`）、`claim`（何を示したか。1 行・40 字程度。結論を書き、方法は書かない）、`caveat`（読むときの注意。1 行。無ければ省く）。
- **項目（`slots`、任意）**：研究の性質を短い値で。どの項目を使うかはプロジェクトの `view-config.json` で決める。値は 15 字程度の名詞句にし、文章にしない。分からない項目は書かない。
- **ひな形**：`viewer/card-presets.json` の 4 種類。テーマの種類（報告規約「情報源の状況」の表）に対応させる。

  | ひな形（`preset`） | 項目（先頭 3 つが一覧・エビデンス表の列） | テーマ |
  |---|---|---|
  | `clinical` | design デザイン／population 対象・n／followup 追跡／exposure 曝露・介入／outcome 評価項目 | 臨床 |
  | `basic` | system 系／manipulation 操作／readout 読み出し／condition 条件 | 基礎・機序 |
  | `methods` | task 課題／method 手法／data データ・評価指標／baseline 比較対象 | 方法論・学際 |
  | `simulation` | model モデル／scale スケール・パラメータ／validation 検証データ | モデル・シミュレーション |

  レビューとガイドラインは、どのひな形でも `scope`（対象範囲）だけを使う（`by_kind`）。

- **`view-config.json`**（プロジェクト直下。設定ファイルで台帳ではない）：

  ```jsonc
  {"card": {
    "preset": "clinical",
    "slots": [ … ],                 // 任意。ひな形の項目を差し替える時だけ（id は英字で固定、label は自由）
    "glance": ["design", "population", "followup"],   // 任意。一覧に出す項目
    "by_kind": {"method": {"slots": [{"id": "task", "label": "課題"}], "glance": ["task"]}}   // 任意。種類別の項目
  }}
  ```

  - 作るのは `/new-project`（目的からひな形を選ぶ）か、無い状態で最初にカードを書く scout（テーマの種類から選び、報告で知らせる）。項目を足す・名前を変えるのは `/view` が提案し、人が承認してから。
  - 項目は分類ではなく説明なので、途中で変えても過去のカードは書き直さない（無い列は空欄で表示される）。

## ビュー規約（view.html）

- `python tools/build_view.py <project>` が runs/・findings/・seen.jsonl・query-log.jsonl・landscape.md・view-config.json・bib-cache.jsonl を読み、`viewer/template.html` にデータを埋め込んで `workspace/<project>/view.html` を作る。スクリプトは検証・統合・埋め込みだけを行い、判断はしない。ブラウザでダブルクリックして開く（オフラインで動く）。
- 表示は 4 段：L0 一覧の 1 行（問いは問いの文と `headline`、文献は著者・年と `claim`、実行は依頼と件数）→ L1 行をクリックしてその場で展開（問いはエビデンス表、文献はカードの項目と注意、実行は検索の表）→ L2 右の詳細欄（節は閉じて置く）→ L3 原典へのリンク。印は普通と違う時だけ付ける。
- **runs/ を書いたコマンドは、最後にこのスクリプトを実行する**。失敗や警告があっても報告は止めず、末尾に「ビュー：<パス>（警告 n 件：…）」と書く。
- 実行記録の無い日も、query-log.jsonl と seen.jsonl から「実行記録の外にあるもの」として表示される（件数・読んだ範囲・経路は不明と明示）。
- `--fetch-bib` は書誌と抄録の欠けを PubMed（PMID）・OpenAlex（DOI）・ClinicalTrials.gov（NCT）から取って `bib-cache.jsonl` に追記する（ネットワークを使うのはこのオプションの時だけ。`/view` が使う）。抄録は原文の保存で、AI が読んだ範囲を示すものではない（読んだ範囲は runs/ の `depth`）。`--check` は検証だけ。
- テンプレートはプロジェクトごとに書き換えない。プロジェクト固有の表示は runs/・findings/ のデータ（`x-` 項目を含む）で表す。複数のプロジェクトで要る表示だけテンプレートに足す。

## landscape.md 規約

- 目的・探索済みの軸・手薄な軸・効いた/効かなかった検索軸を記録する人間可読メモ（`/new-project` で雛形生成）。
- **目的欄**は scout / orchestrator がソース選択・隣接軸提案の委任判断の材料として読む。「メソッド選定」なら手法クラスタ・被引用集中を重視、「先行研究の網羅」なら漏れ防止優先、「KOL 把握」なら著者・所属を優先、というように委任の質を上げる。
- **効いた／効かなかった軸**は人が後で見返す厳選メモ（生ログではない）。cartographer が更新の主担当だが、OpenAlex 未接続の間は人間の手動更新が中心になる。

## ソース選択の委譲規約

- デフォルトは委譲：scout / orchestrator が意図から適切なソースを選び、**選択理由を実行前に宣言**してから実行する（例：「機序寄りの精密探索なので PubMed、開拓のため S2 併用（ただし S2 は未接続のため今回は PubMed のみ）」）。
- `--source` フラグで明示指定に上書き可能（`--source pubmed` / `--source pubmed,clinicaltrials` / `--source pubmed,s2`）。

## クエリ変換規約

- 自然言語（会話的）とキーワード羅列の両方を第一級の入力として受ける。
- OpenAlex の Boolean 検索は PubMed ほど精密でないため、自然言語を丸ごと 1 クエリにせず **concept / filter に分解**して組む（OpenAlex 接続後に適用）。
- 解釈した意図は実行前に必ず言語化する（透明性原則）。

## 報告規約

- **既出も含めて全件表示**し、新規を視覚的にマークする（人は忘れるため既出も出す）。

  ```
  🆕 [新規] Author 2025  ProteinX drives PathwayY dysregulation...  (cited 34)
     [既出] Author 2023  ProteinZ gain-of-function...               (cited 89)
  ```

- **末尾に隣接軸を提案**：seen の外側へ広げられる未探索軸を提示する。新規÷総数の比率低下を「この軸の掘り尽くし度」の目安とする。
- **検索実施サマリを冒頭に置く**：結果本体の前に、実行した各クエリについて「何を検索し、何件ヒットし、そのうち何件を実際に読んだか」を 1 行ずつ列挙する。人が「やったこと／やっていないこと」を即座に判別できるようにするため。

  ```
  検索内容（PubMed）：
  - PPMI + LEDD + 非運動症状語：16 件 → 全件精読
  - LEDD + "non-motor symptoms"（タイトル/抄録、コホート不問）：155 件 → 未スクリーニング
  - ドパミン作動薬/LEDD（タイトル）+ 非運動ドメイン：29 件 → 上位 20 件を精読
  ```

  - 「読んだ」の粒度（タイトルのみ／抄録／全文）を明記する。
  - 未スクリーニング・一部のみ精読の集合は、網羅性の限界として必ず明示する（黙って省略しない）。
  - `query-log.jsonl` への記録有無とは独立（記録不要と指示された場合もこのサマリは出す）。

- **情報源の状況を検索実施サマリに添える**：テーマの種類から「扱うべき情報源」を下表で決め、各情報源を「検索済み／未実施（この環境に検索手段あり）／検索手段なし」に分けて 1 行ずつ示す。検索しなかった情報源を黙って省略しない。テーマの種類は landscape.md の目的欄とクエリの内容から判断し、判断した種類を明記する（複数該当すれば和集合）。

  | テーマの種類 | 扱うべき情報源 |
  |---|---|
  | 臨床（治療・診断・予後・疫学） | PubMed／臨床試験レジストリ／preprint（medRxiv）／非英語文献（地域データベース）／学会抄録 |
  | 基礎・機序 | PubMed／preprint（bioRxiv） |
  | 方法論・学際（CS・社会科学にまたがる） | PubMed／PubMed 外の分野 |

  各情報源の検索手段（2026-11-07 時点。接続が変わったらここを直す）：

  | 情報源 | この環境での検索手段 |
  |---|---|
  | 臨床試験レジストリ | ClinicalTrials.gov：scout（`clinicaltrials` MCP）。WHO ICTRP・jRCT 等：なし |
  | preprint | OpenAlex（cartographer / network が REST で利用）。bioRxiv/medRxiv：bio-research プラグイン `biorxiv` MCP（キーワード検索なし、日付・分野のみ。Codex は未登録） |
  | 非英語文献（地域データベース） | なし（医中誌・CNKI・LILACS 等は未接続）。OpenAlex は非英語文献も一部収載 |
  | 学会抄録 | なし（Embase 未接続） |
  | PubMed 外の分野 | OpenAlex |

  ```
  情報源（テーマ：臨床）：
  - 検索済み：PubMed
  - 未実施（手段あり）：ClinicalTrials.gov（c-trials）、preprint（OpenAlex）
  - 検索手段なし：地域データベース（医中誌等）、学会抄録（Embase）
  ```

  - 未実施・手段なしの情報源について、「文献は少ないはず」と推測で書かない。規模を示すのは実際に数えた場合だけ。

## カレントプロジェクト解決規約

1. コマンド引数（`$ARGUMENTS`）の先頭の空白区切りトークンが既存の `workspace/<name>/` ディレクトリ名と完全一致すれば、それを明示プロジェクトとして採用し、残りをクエリ本体として扱う。
2. 一致しなければ、`workspace/*/seen.jsonl` を更新日時降順で列挙し（Claude Code の `Glob("workspace/*/seen.jsonl")` はこの順で返る。Codex は「ランタイム対応表」のコマンド）、先頭のプロジェクトを「直近操作プロジェクト」として採用する。
3. プロジェクトが一つも存在しなければ `workspace/_scratch/` で状態を持たずに実行する（`seen.jsonl` / `query-log.jsonl` への書き込みは一切行わない）。

## orchestrator の意図分解規約

- 検索・俯瞰・著者・Zotero 照合のうちどれが必要かを判定し、**分解結果を実行前に宣言**してから実行する。
- 分解順序は固定しない（固定連鎖ではなく、問いごとに動的にディスパッチする）。
- orchestrator 自身は新しい判断をせず、ソースにも直接触れない。既存 subagent を呼び分けるだけの薄い層。

## 透明性の原則（全体）

解釈・選択・分解を実行前に言語化し、人間がいつでも軌道修正できる状態にする。

## MCP 接続状況（スナップショット。ドリフトしうるため都度再確認すること：Claude Code は `/mcp`、Codex は `/mcp` または `codex mcp list`）

| ソース | Claude Code | Codex | ツールプレフィックス |
|---|---|---|---|
| PubMed | 接続済み（user scope に直接登録） | 設定済み（リポジトリの `.codex/config.toml`。**Codex でこのプロジェクトを trusted にした場合のみ読み込まれる**） | `mcp__pubmed__*` |
| Scite | 接続済み（独立 remote MCP。このプロジェクトの local scope に登録） | 設定済み（リポジトリの `.codex/config.toml`。OAuth のため初回だけ `codex mcp login scite` が必要） | `mcp__scite__*` |
| Zotero | 接続済み（Scite 連携ツール同梱） | 接続済み（user `~/.codex/config.toml`。書き込み系は下記注意） | `mcp__zotero__*` |
| Semantic Scholar | 未接続（接続後 scout の開拓探索に使用） | 未接続 | — |
| OpenAlex | 接続済み（MCP ではなく直接 REST API、`Bash` の `curl`） | 同左（シェルの `curl.exe`。sandbox 外実行が必要） | —（MCP ではない） |
| Obsidian | 未接続（接続後 synthesizer の二次情報出力先） | 未接続 | — |
| ClinicalTrials.gov | 接続済み（user scope に直接登録） | 設定済み（リポジトリの `.codex/config.toml`。trusted 時のみ） | `mcp__clinicaltrials__*` |
| bioRxiv / medRxiv | bio-research プラグイン経由で利用可（どの役割の `tools:` にも未収載。報告規約「情報源の状況」で未実施として挙げるのみ） | 未登録 | `mcp__plugin_bio-research_biorxiv__*` |

- **PubMed**：精密な網羅探索に使用。Claude Code は `claude mcp add --transport http --scope user pubmed https://pubmed.mcp.claude.com/mcp` で登録（2026-10-26）。以前は `pubmed@life-sciences` プラグイン経由（`mcp__plugin_pubmed_PubMed__*`）だったが、配布元マーケットプレイスから削除され読み込まれなくなったため切り替えた。同じ URL の PubMed は `bio-research` プラグインにもあるが、直接登録した方が残る。Codex は同じ URL を `.codex/config.toml` の `[mcp_servers.pubmed]` として登録（2026-11-06。認証なしで汎用 MCP クライアントから initialize できることを確認済み）。
- **ClinicalTrials.gov**：scout が臨床テーマで登録試験を検索する（`search_trials` / `get_trial_details`）。試験に紐付く論文は PubMed の `NCT<番号>[si]` で探す。Claude Code は `claude mcp add --transport http --scope user clinicaltrials https://hcls.mcp.claude.com/clinical_trials/mcp` で登録（2026-11-07）。同じ URL のサーバーが bio-research プラグインにも `c-trials` として入っているが、Codex とツール名を揃えるため直接登録した方（`clinicaltrials`）を使う。Codex は `.codex/config.toml` の `[mcp_servers.clinicaltrials]`。認証なしで汎用 MCP クライアントから initialize できることを確認済み（2026-11-07）。
- **Scite**：citation（`/cite`）の主経路。`https://api.scite.ai/mcp`（契約済み、OAuth 認証）。`search_literature(dois=[...])` で DOI 群の supporting/contrasting/mentioning 件数と editorial notice を、`verify_papers` で撤回・反証候補を 1 回 20 件までまとめて取得できる。Claude Code はこのプロジェクトの local scope に登録している（`~/.claude.json`、コミット対象外）。Codex は `.codex/config.toml` の `[mcp_servers.scite]` に登録（2026-11-06）。未認証・未接続の間、citation は Zotero 同梱の Scite ツールに fallback する。
- **Zotero**：同梱の `scite_enrich_item` / `scite_enrich_search` / `scite_check_retractions` は、citation で独立 Scite MCP が使えない時の fallback（DOI 1 件ずつ／Zotero ライブラリ範囲のツールで、独立 Scite MCP とは別物）。どちらのランタイムもローカル API（`ZOTERO_LOCAL=true`）を使うため Zotero デスクトップの起動が前提。Claude Code は `~/.claude/zotero-mcp-run.ps1` 経由で起動し、リポジトリ直下 `.env`（gitignore）の `ZOTERO_API_KEY` 等（書き込み系に必要）を読み込む。Codex は `zotero-mcp.exe` を `ZOTERO_LOCAL=true` のみで起動しており API キーを渡していないため、書き込み系（`zotero_add_by_*` / `zotero_create_note` / `zotero_update_item` 等）は動かない可能性が高い（未検証）。`/digest` の Zotero 蓄積（opt-in）を Codex でも使うなら、Codex 側の起動コマンドを同じ起動スクリプトに揃える。
- **OpenAlex**：個人開発 MCP パッケージを信頼せず、認証不要の公開 REST API（`https://api.openalex.org/`）を薄い glue（シェルの curl）経由で叩く方式を採用（2026-08-15）。`mailto=` パラメータを付けて polite pool を利用する。cartographer（concept/group_by 俯瞰）・network（著者/共著解決）が使用。**MCP サーバーではないため `/mcp` には出ない**（ここに接続状況を明記して都度参照する）。Codex での注意は「Codex アダプタ共通作法」6。

未接続 MCP に依存する subagent は、本文内でその旨を明示し、代替（fallback）動作で機能を保つ設計にする。OpenAlex は MCP 未接続のままだが、直接 REST API 経由で機能的には接続済み — cartographer / network はこの方式を一次手段として使う。

## ランタイム対応（Claude Code / Codex）

### 正本とアダプタ

手順は**正本にだけ**書く。アダプタは正本を指すだけで、手順を書き写さない。

| 種別 | 正本 | Claude Code での読み込み | Codex アダプタ |
|---|---|---|---|
| 共通規約 | `AGENTS.md`（本書） | `CLAUDE.md` が `@AGENTS.md` で import | 直接読み込み |
| コマンド | `.claude/commands/<cmd>.md` | そのまま slash command `/<cmd>` | `.agents/skills/<cmd>/SKILL.md`（`$<cmd>` で呼ぶ） |
| 役割（subagent） | `.claude/agents/<role>.md` | そのまま subagent | `.codex/agents/<role>.toml`（custom agent） |
| MCP 登録 | — | `claude mcp add`（user / local scope） | `.codex/config.toml`（公開してよいもの）／ `~/.codex/config.toml`（機密・マシン固有パスを含むもの） |

コマンドと役割の対応：

| Claude Code | Codex | コマンド正本 | 役割正本 | Codex custom agent |
|---|---|---|---|---|
| `/scout` | `$scout` | `.claude/commands/scout.md` | `.claude/agents/scout.md` | `.codex/agents/scout.toml` |
| `/map` | `$map` | `.claude/commands/map.md` | `.claude/agents/cartographer.md` | `.codex/agents/cartographer.toml` |
| `/network` | `$network` | `.claude/commands/network.md` | `.claude/agents/network.md` | `.codex/agents/network.toml` |
| `/cite` | `$cite` | `.claude/commands/cite.md` | `.claude/agents/citation.md` | `.codex/agents/citation.toml` |
| `/digest` | `$digest` | `.claude/commands/digest.md` | `.claude/agents/synthesizer.md` | `.codex/agents/synthesizer.toml` |
| `/ask` | `$ask` | `.claude/commands/ask.md` | `.claude/agents/orchestrator.md` | なし（Codex では main スレッドが orchestrator を演じる） |
| `/new-project` | `$new-project` | `.claude/commands/new-project.md` | なし（コマンド本文が手順） | なし |
| `/view` | `$view` | `.claude/commands/view.md` | なし（コマンド本文が手順） | なし |

正本は経緯上 `.claude/` 配下にあるが、**両ランタイム共通の手順書**として扱う。手順書は Claude Code のツール名（`Read` / `Write` / `Glob` / `Grep` / `Bash` / `Agent`）と `$ARGUMENTS` で書かれているので、Codex では次の表で読み替える。

### ランタイム対応表（手順書の表記 → 各ランタイムの操作）

| 手順書の表記 | Claude Code | Codex（Windows / PowerShell 7） |
|---|---|---|
| `Read`（ファイルを読む） | `Read` | `Get-Content -Raw -Encoding utf8 <path>` |
| `Write`（新規作成・全文の書き戻し） | `Write` | `apply_patch`（Add File / Update File）。空ファイルは `New-Item -ItemType File <path>` でもよい |
| JSONL 台帳（`seen.jsonl` / `query-log.jsonl`）への追記 | `Read` → 追記後の全文を組み立て → `Write` | `apply_patch` で末尾に行を追加（既存行には触れない） |
| `Glob("workspace/*/seen.jsonl")`（更新日時降順） | `Glob` | `Get-ChildItem workspace\*\seen.jsonl` の結果を `Sort-Object LastWriteTime -Descending` で並べる |
| `Glob("workspace/*")` | `Glob` | `Get-ChildItem workspace -Directory` |
| `Grep` | `Grep` | `rg`（無ければ `Select-String`） |
| `Bash` の `curl`（OpenAlex REST API） | `Bash` | `curl.exe`（filter の区切り記号を含め、URL 全体を二重引用符で囲む） |
| `Bash` の `python tools/build_view.py <project>`（ビューの生成） | `Bash` | `python tools/build_view.py <project>`（sandbox 内で可。`--fetch-bib` だけはネットワークを使うので sandbox 外） |
| runs/・findings/ の新規ファイル作成 | `Write` | `apply_patch`（Add File） |
| `Agent`（subagent の呼び出し） | `Agent` ツール | subagent を spawn（`.codex/agents/` の custom agent を名前で指定） |
| `$ARGUMENTS` | slash command の引数 | skill：`$<cmd>` に続けて書かれた入力全体／custom agent：親から渡されたタスク文 |
| `mcp__pubmed__*` / `mcp__scite__*` / `mcp__clinicaltrials__*` / `mcp__zotero__*` | 同名 | 同名（両ランタイムで MCP サーバー名を `pubmed` / `scite` / `clinicaltrials` / `zotero` に揃えているため） |

### Codex アダプタ共通作法（`.agents/skills/` と `.codex/agents/` の全ファイルが従う）

1. **正本を読んでから動く**：skill は `.claude/commands/<cmd>.md` を読み、その本文をコマンドの指示として扱う。frontmatter に `agent: <role>` があれば `.claude/agents/<role>.md` も読み、その本文の手順で実行する。custom agent は自分の役割の `.claude/agents/<role>.md` を読む。frontmatter（`context: fork` 等）は Claude Code 用のメタデータで、Codex では下記 2・3 のとおり扱う。
2. **ツール範囲を守る**：役割の frontmatter `tools:`（コマンドの場合は `allowed-tools:`）が、その役割で使ってよいツールの範囲。Codex は強制しないので自分で守る。読み取り（`Read` / `Glob` / `Grep` 相当）のためのシェル利用はどの役割でも可。`Bash` を持たない役割はシェルでネットワークアクセスしない。`Write` を持たない役割はファイルを書かない。範囲外の MCP ツール（例：citation が Zotero に書き込む）は使わない。
3. **実行場所**：単一意図の skill（`$scout` `$map` `$network` `$cite` `$digest` `$new-project` `$view`）は、このスレッドで直接手順を実行する（Claude Code の `context: fork` のような隔離はしない）。`$ask` だけは、このスレッドが `orchestrator` を演じ、必要な役割を `.codex/agents/` の custom agent（`scout` / `cartographer` / `network` / `citation` / `synthesizer` の 5 種のみ）として spawn する。Codex 組み込みの `default` / `worker` / `explorer` は使わない。orchestrator 自身はソースに触れず、ファイルも書かない（`orchestrator.md` の制約がそのまま適用される）。
4. **custom agent の報告**：spawn された custom agent は、手順書の報告形式どおりの完全な報告を最終メッセージにする。親が解決済みのプロジェクト名を渡した場合は再解決しない。親（orchestrator）はその報告を再判断せずに統合する。
5. **台帳の書き込み**：`seen.jsonl` / `query-log.jsonl` / `landscape.md` / `runs/` / `findings/` / digest ファイルの書き込みは `apply_patch` で行う（`view.html` と `bib-cache.jsonl` は `tools/build_view.py` が書く）。`>>`・`Add-Content`・`Out-File`・`Set-Content` は使わない。読む時は `-Encoding utf8` を付ける（日本語の文字化け防止）。
6. **OpenAlex と sandbox**：Codex の Windows sandbox 内では `curl.exe` の TLS 接続が失敗する（`schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`。2026-11-06 に `codex sandbox` で確認）。OpenAlex 呼び出しは最初から sandbox 外実行（承認要求）で行う。**sandbox が原因の接続失敗は、cartographer / network の「API が機能しない場合」に当たらない**。それを理由に fallback へ切り替えない。

### デュアルランタイム維持規約（構成を変える時は、どちらのランタイムで作業していても守る）

1. **手順・規約の変更は正本だけを直す**：共通規約は `AGENTS.md`、コマンドは `.claude/commands/<cmd>.md`、役割は `.claude/agents/<role>.md`。`CLAUDE.md`・`.agents/skills/*/SKILL.md`・`.codex/agents/*.toml` に手順を書き写さない。
2. **コマンド・役割の追加／改名／削除は対で行う**：コマンド `<cmd>` なら `.claude/commands/<cmd>.md` と `.agents/skills/<cmd>/SKILL.md`、役割 `<role>` なら `.claude/agents/<role>.md` と `.codex/agents/<role>.toml` を同時に作る・直す・消す。`description` は両者で揃える。上の対応表も更新する。orchestrator が呼べる役割を変えたら、`orchestrator.md` の呼び出し可能リストと本書「Codex アダプタ共通作法」3 も更新する。
3. **手順書に新しい種類の操作を書いたら**（新しいツール名・シェル操作など）、ランタイム対応表に両ランタイムでの操作を追記する。片方では実現できない場合は、正本に fallback を書き、MCP 接続状況表に明記する。
4. **MCP の追加・変更は両ランタイムに同じサーバー名で登録する**。サーバー名が揃えばツール名 `mcp__<server>__<tool>` が一致し、手順書を書き分けずに済む。MCP 接続状況表は両列とも更新する。
5. **機密・個人設定はコミットしない**：API キーは `.env`、OpenAlex 用メールは `.openalex-mailto`（ともに gitignore）。`.codex/config.toml` は公開リポジトリにコミットされるので、公開 URL など機密でない設定だけを書く。
6. **変更後の整合チェック**（出力が空なら名前の対応が一致している。orchestrator は Codex 側に custom agent を置かないので除外）：

   ```powershell
   Compare-Object (Get-ChildItem .claude/commands/*.md).BaseName (Get-ChildItem .agents/skills -Directory).Name
   Compare-Object ((Get-ChildItem .claude/agents/*.md).BaseName | Where-Object { $_ -ne 'orchestrator' }) (Get-ChildItem .codex/agents/*.toml).BaseName
   ```
