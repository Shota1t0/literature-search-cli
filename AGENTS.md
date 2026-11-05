# 文献調査CLI — プロジェクト規約（Claude Code / Codex 共通）

このリポジトリは、AI コーディングエージェントの subagent + MCP を用いて文献調査（先行研究調査・メソッド検討・MSL の KOL 調査）を体系化する CLI システムである。**Claude Code と Codex のどちらでも同じ手順で動く状態を保つ**。仕様の全体像は `README.md` を参照。

この文書は、両ランタイムの全 subagent・コマンド・skill が依拠する共通規約の**正本**である。Codex は `AGENTS.md` を直接読み込み、Claude Code は `CLAUDE.md` の `@AGENTS.md` 経由で読み込む。ランタイムごとの差分は末尾の「ランタイム対応」と「デュアルランタイム維持規約」にまとめる。

## 設計原則（README §1 準拠）

- **プログラム最小**：実装は薄い glue に留め、思考ロジックは subagent のプロンプトに寄せる。
- **フレームワーク不変**：構造を頻繁に変えない。
- **状態は最小**：永続状態は `seen.jsonl`（プロジェクト単位）のみが判定に使われる。`query-log.jsonl` は参照専用で判定には使わない。
- **連鎖の事前固定はしない**：subagent は定義済み順序で自動連鎖させない。
- **フェーズ移行は人間が握る**：探索→俯瞰→精査の移行は人間が判断する。
- **透明性**：subagent / orchestrator は「どう解釈し、何をするか」を実行前に必ず言語化する。

## 三層台帳（役割を混同しない）

| 台帳 | 中身 | 「重複」の意味 | 判定に使うか | 更新者 | 読み方 |
|---|---|---|---|---|---|
| **seen.jsonl** | 到達論文（DOI 正本） | この論文を見たか | する | scout（新規追加）/ synthesizer（zot 更新） | 機械が照合 |
| **query-log.jsonl** | 打ったクエリ（生文字列） | この角度で検索したか | しない（参照のみ） | scout | 「もっと他を」要求時のみ読む |
| **landscape.md** | 目的・効いた軸・手薄な軸 | どこへ向かうか | しない | cartographer / 人間 | scout/orchestrator が委譲判断の材料として読む |

役割は完全に分離している。混ぜない。

## seen.jsonl 規約

- 1 論文 1 行の JSONL。**追記専用**（append-only）。既存行は書き換えない。
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
- **フラグ更新は追記で行う**：既存行を書き換えるのではなく、同じ DOI で更新後の値（例：`"zot": true`）を持つ新しい行を追記する。読み手は常に **DOI ごとに「最後の出現」を正** とみなし、そのために全行読み込み後 DOI をキーに dedup（後勝ち）してから使う。
- **更新方法**：既存行には一切触れず、末尾に新しい行を足す。Claude Code では `Read` で現在の全内容を取得 → 追記後の全文を組み立て → `Write` で書き戻す。Codex では `apply_patch` で末尾に行を追加する。どちらもシェルのリダイレクト（`>>` 等）や `Add-Content` / `Out-File` / `Set-Content` には依存しない（Windows/Bash 両対応、文字コード・BOM・改行の混入防止のため）。プロジェクトが存在しない（`_scratch/` 実行時）は何も書き込まない。

## ID 正規化ルール

- どのソースから取得した論文も、**まず DOI に正規化**してから `seen.jsonl` と照合する。
- PubMed 由来：`mcp__pubmed__convert_article_ids` や `get_article_metadata` で DOI を取得。
- DOI が取得できない場合はタイトル+出版年で近似照合し、結果に明示的にフラグを立てる。
- これにより、PubMed で見た論文を将来 OpenAlex 等で再発見しても既出と判定できる（ソース横断の重複回避）。

## query-log.jsonl 規約

- スキーマ：`{"src":"pubmed","q":"GENE-A pathway regulation","ran":"2026-08-07"}`
- 追記専用。**dedup 判定には絶対に使わない**（同じクエリ文字列を再実行してよい。着目点が違えば拾う論文も変わるため）。
- 読むのは、ユーザーが明示的に「もっと他を」「別の角度で」等と求めた時だけ。scout はそのプロジェクトの過去クエリを提示し、被らない新しい角度を組んで再検索する。生ヒットに混じる既出論文は依然 `seen.jsonl` が弾く。
- 論文レベルの重複回避は常に `seen.jsonl` の仕事。角度の重複回避と論文の重複回避は別レイヤ。

## landscape.md 規約

- 目的・探索済みの軸・手薄な軸・効いた/効かなかった検索軸を記録する人間可読メモ（`/new-project` で雛形生成）。
- **目的欄**は scout / orchestrator がソース選択・隣接軸提案の委任判断の材料として読む。「メソッド選定」なら手法クラスタ・被引用集中を重視、「先行研究の網羅」なら漏れ防止優先、「KOL 把握」なら著者・所属を優先、というように委任の質を上げる。
- **効いた／効かなかった軸**は人が後で見返す厳選メモ（生ログではない）。cartographer が更新の主担当だが、OpenAlex 未接続の間は人間の手動更新が中心になる。

## ソース選択の委譲規約

- デフォルトは委譲：scout / orchestrator が意図から適切なソースを選び、**選択理由を実行前に宣言**してから実行する（例：「機序寄りの精密探索なので PubMed、開拓のため S2 併用（ただし S2 は未接続のため今回は PubMed のみ）」）。
- `--source` フラグで明示指定に上書き可能（`--source pubmed` / `--source pubmed,s2`）。

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

- **PubMed**：精密な網羅探索に使用。Claude Code は `claude mcp add --transport http --scope user pubmed https://pubmed.mcp.claude.com/mcp` で登録（2026-10-26）。以前は `pubmed@life-sciences` プラグイン経由（`mcp__plugin_pubmed_PubMed__*`）だったが、配布元マーケットプレイスから削除され読み込まれなくなったため切り替えた。同じ URL の PubMed は `bio-research` プラグインにもあるが、直接登録した方が残る。Codex は同じ URL を `.codex/config.toml` の `[mcp_servers.pubmed]` として登録（2026-11-06。認証なしで汎用 MCP クライアントから initialize できることを確認済み）。
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
| `Agent`（subagent の呼び出し） | `Agent` ツール | subagent を spawn（`.codex/agents/` の custom agent を名前で指定） |
| `$ARGUMENTS` | slash command の引数 | skill：`$<cmd>` に続けて書かれた入力全体／custom agent：親から渡されたタスク文 |
| `mcp__pubmed__*` / `mcp__scite__*` / `mcp__zotero__*` | 同名 | 同名（両ランタイムで MCP サーバー名を `pubmed` / `scite` / `zotero` に揃えているため） |

### Codex アダプタ共通作法（`.agents/skills/` と `.codex/agents/` の全ファイルが従う）

1. **正本を読んでから動く**：skill は `.claude/commands/<cmd>.md` を読み、その本文をコマンドの指示として扱う。frontmatter に `agent: <role>` があれば `.claude/agents/<role>.md` も読み、その本文の手順で実行する。custom agent は自分の役割の `.claude/agents/<role>.md` を読む。frontmatter（`context: fork` 等）は Claude Code 用のメタデータで、Codex では下記 2・3 のとおり扱う。
2. **ツール範囲を守る**：役割の frontmatter `tools:`（コマンドの場合は `allowed-tools:`）が、その役割で使ってよいツールの範囲。Codex は強制しないので自分で守る。読み取り（`Read` / `Glob` / `Grep` 相当）のためのシェル利用はどの役割でも可。`Bash` を持たない役割はシェルでネットワークアクセスしない。`Write` を持たない役割はファイルを書かない。範囲外の MCP ツール（例：citation が Zotero に書き込む）は使わない。
3. **実行場所**：単一意図の skill（`$scout` `$map` `$network` `$cite` `$digest` `$new-project`）は、このスレッドで直接手順を実行する（Claude Code の `context: fork` のような隔離はしない）。`$ask` だけは、このスレッドが `orchestrator` を演じ、必要な役割を `.codex/agents/` の custom agent（`scout` / `cartographer` / `network` / `citation` / `synthesizer` の 5 種のみ）として spawn する。Codex 組み込みの `default` / `worker` / `explorer` は使わない。orchestrator 自身はソースに触れず、ファイルも書かない（`orchestrator.md` の制約がそのまま適用される）。
4. **custom agent の報告**：spawn された custom agent は、手順書の報告形式どおりの完全な報告を最終メッセージにする。親が解決済みのプロジェクト名を渡した場合は再解決しない。親（orchestrator）はその報告を再判断せずに統合する。
5. **台帳の書き込み**：`seen.jsonl` / `query-log.jsonl` / `landscape.md` / digest ファイルの書き込みは `apply_patch` で行う。`>>`・`Add-Content`・`Out-File`・`Set-Content` は使わない。読む時は `-Encoding utf8` を付ける（日本語の文字化け防止）。
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
