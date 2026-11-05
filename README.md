# literature-search-cli（文献調査CLI）

AI コーディングエージェントの subagent と MCP を使って、文献調査（先行研究調査・メソッド検討・MSL の KOL 調査）を網羅的・俯瞰的・高速に行うための CLI フレームワーク。

**Claude Code と Codex のどちらでも同じ手順書で動く。** 手順書（`.claude/agents/`・`.claude/commands/`）と共通規約（`AGENTS.md`）を両ランタイムが共有し、Codex 側は正本を指すだけの薄いアダプタで動かす。

- 共通規約の正本：[`AGENTS.md`](AGENTS.md)（台帳の書き方・報告の作法・ランタイム対応表・維持規約）
- この README：目的・使い方・セットアップ・設計の考え方

---

## 1. 設計原則

- **プログラム最小**：実装は薄い glue に留め、思考ロジックは subagent のプロンプトに寄せる。専用スクリプトは作らない。
- **フレームワーク不変**：構造を頻繁に変えずに維持できること。
- **状態は最小**：判定に使う永続状態は `seen.jsonl`（プロジェクト単位）のみ。
- **連鎖の事前固定はしない**：subagent を定義済み順序で自動連鎖させない。
- **フェーズ移行は人間が握る**：「探索→俯瞰→精査」の移行は人間が判断する。機械的な停止条件で自動遷移させない。
- **透明性**：subagent / orchestrator は「どう解釈し、何をするか」を実行前に必ず言語化し、人間が軌道修正できる状態にする。

---

## 2. 全体フロー

| フェーズ | ユーザーの動き | 担当 subagent | 主ソース |
|---|---|---|---|
| ① 探索・内容確認 | どんな論文があるかざっと調べ、内容を聞く | scout | PubMed（精密）+ Semantic Scholar（開拓・未接続） |
| ② 俯瞰 | 分野全体を俯瞰し、手薄な軸・流行を判断 | cartographer / network | OpenAlex |
| ③ 精査 | 引用評価・トレンドをチェック | citation | Scite |
| 蓄積・出力 | キュレーション文献を蓄積、二次情報を出力 | synthesizer | Zotero / Obsidian（未接続） |

段階移行は人間の判断で行う（「テーマが絞れてきた」等はセマンティックな判断であり自動化しない）。

---

## 3. 使い方

### 3.1 コマンド一覧

| Claude Code | Codex | 担当 | 内容 |
|---|---|---|---|
| `/new-project <name>` | `$new-project <name>` | （直接実行） | プロジェクト作成（`seen.jsonl` / `query-log.jsonl` / `landscape.md`） |
| `/scout [project] <query>` | `$scout ...` | scout | ① PubMed で網羅探索、新規/既出判定、隣接軸提案 |
| `/map [project]` | `$map ...` | cartographer | ② seen 集合を OpenAlex で俯瞰し、`landscape.md` 更新を提案 |
| `/network [project] <author or work>` | `$network ...` | network | 著者・共著・共引用ネットワークから周辺論文を発掘 |
| `/cite [project] <DOI> \| --topic "<text>" \| --recent N` | `$cite ...` | citation | ③ Scite で supporting / contrasting / mentioning・撤回を評価（単一・群） |
| `/digest [project] [対象] [--zotero]` | `$digest ...` | synthesizer | 要約・ファクトチェック → 二次情報出力。Zotero 蓄積は明示時のみ |
| `/ask <複合クエリ>` | `$ask ...` | orchestrator | 複合意図を分解し、必要な subagent だけを呼び分ける |

- Codex では skill として `$scout` のように呼ぶ（`/skills` から選んでもよい）。`$digest` は人間が明示的に呼ぶものなので、Codex が会話から暗黙に起動しない設定にしてある。
- 先頭トークンが既存プロジェクト名ならそのプロジェクト、省略時は直近に触れたプロジェクト、プロジェクトが無ければ `_scratch/`（状態を残さない）で実行する。

### 3.2 主なオプション

- `--source <list>`：ソースを明示指定（`--source pubmed` / `--source pubmed,s2`）。省略時は scout が意図から選び、**選択理由を実行前に宣言**する。
- `--exclude-zotero`：Zotero に所持済みの論文を除き、未所持だけを報告する（scout / ask に付けられる横断フィルタ）。
- `/cite` の入力形態：単一 DOI／`--topic "<text>"`（seen 内のタイトル近似マッチ群）／`--recent N`（seen に最近追加した N 件）。複数件では群としてのトレンドも返す。
- `/digest`：Zotero への追加は**既定では行わない**。「Zoteroに登録して」等の明示要求がある時だけ追加し、`seen.jsonl` の `zot` フラグを更新する。

### 3.3 単一コマンドと `/ask` の使い分け

| 入口 | 使う場面 |
|---|---|
| `/scout` `/map` `/network` `/cite` `/digest` | 意図が単一のとき（直接・高速） |
| `/ask <複合クエリ>` | 探索 + 俯瞰 + 著者 + Zotero 照合が絡むとき |

orchestrator は**固定連鎖ではなく、問いごとにその場で分解してディスパッチ**する。新しい判断はせず、既存 subagent を呼び分けるだけの薄い層。

```
> Zotero内にないGENE-A関連文献を探して
orchestrator: 意図を分解しました:
  1. ZoteroのGENE-A所持リストを取得（除外セット化）
  2. PubMedでGENE-A探索
  3. Zotero集合との差分 = 未所持のみ報告
  → 🆕 [未所持] Author 2025 GENE-A pathway regulation...
```

Claude Code では各コマンドが subagent に fork して動く。Codex では単一コマンドはメインのスレッドで直接動き、`$ask` だけがメインのスレッドを orchestrator にして custom agent（`.codex/agents/`）を呼び分ける。

### 3.4 報告の形

- 冒頭に**検索実施サマリ**（クエリごとのヒット数・読んだ件数と粒度・未スクリーニング集合）。
- 結果は**既出も含めて全件表示**し、新規をマークする（人は忘れるため既出も出す）。
- 末尾に**隣接軸**を提案する。新規÷総数の低下を「その軸の掘り尽くし度」とみなす。

```
🆕 [新規] Author 2025  ProteinX drives PathwayY dysregulation...  (cited 34)
   [既出] Author 2023  ProteinZ gain-of-function...               (cited 89)

今回12件（新規2/既出10）。この軸はほぼ掘り尽くし。
未探索の隣接軸：PathwayA × CellTypeB / DrugClassC 側からの逆引き ...
```

「もっと他を」「別の角度で」と頼むと、scout はそのプロジェクトで過去に打ったクエリ（`query-log.jsonl`）を見せ、被らない角度で再検索する。

---

## 4. セットアップ

### 4.1 共通（ローカルのみ・コミットしない）

| ファイル | 中身 | 用途 |
|---|---|---|
| `.env` | `ZOTERO_API_KEY` / `ZOTERO_LIBRARY_ID` / `ZOTERO_LIBRARY_TYPE` | Zotero MCP の書き込み系 |
| `.openalex-mailto` | メールアドレス 1 行 | OpenAlex の polite pool（無ければ初回に聞かれる） |

どちらも gitignore 済み。Zotero MCP はローカル API を使うため、**Zotero デスクトップを起動しておく**。

### 4.2 Claude Code

```bash
claude mcp add --transport http --scope user pubmed https://pubmed.mcp.claude.com/mcp
claude mcp add --transport http --scope local scite https://api.scite.ai/mcp   # 初回に OAuth 認証
```

Zotero MCP（`zotero-mcp serve`）は `zotero` という名前で登録する。`CLAUDE.md` は `@AGENTS.md` を読み込むだけなので、規約の追加は `AGENTS.md` に書く。接続状況は `/mcp` で確認する。

### 4.3 Codex

1. このフォルダで Codex を起動し、**フォルダを trusted にする**（初回の確認で「信頼する」）。trusted でないと `.codex/config.toml`（PubMed / Scite）と `.codex/agents/` が読み込まれない。親フォルダの trust は引き継がれない。
2. `codex mcp login scite` で Scite に一度だけ認証する。未認証の間、`$cite` は Zotero 同梱の Scite ツールで動く。
3. Zotero MCP はマシン固有の設定なので、ユーザー設定 `~/.codex/config.toml` に `zotero` という名前で登録する。API キーを渡していない場合、書き込み系（`$digest` の Zotero 蓄積）は動かない。
4. OpenAlex（`$map` / `$network`）の `curl.exe` は、Windows の sandbox 内では TLS が通らないため、sandbox 外での実行を承認する。

接続状況は `/mcp` または `codex mcp list` で確認する。

---

## 5. 状態管理

### 5.1 三層台帳

状態は 3 層に分かれ、役割が完全に分離している。混ぜない。

| 台帳 | 中身 | 「重複」の意味 | 判定に使うか | 読み方 |
|---|---|---|---|---|
| **seen.jsonl** | 到達論文（DOI 正本） | この**論文**を見たか | する | 機械が照合 |
| **query-log.jsonl** | 打ったクエリ（生文字列） | この**角度**で検索したか | しない（参照のみ） | 「もっと他を」の時だけ読む |
| **landscape.md** | 目的・効いた軸・手薄な軸 | どこへ**向かう**か | しない | 人間可読 |

- **seen.jsonl**：1 論文 1 行・追記専用。どのソースの論文も **DOI に正規化**してから照合するので、PubMed で見た論文を OpenAlex で再発見しても既出と判定できる。DOI が無い論文はタイトル + 出版年で近似照合し、`⚠ DOI欠損・近似照合` を付ける。フラグ更新（`zot` 等）も既存行を書き換えず、新しい行を追記する（DOI ごとに最後の行が正）。
- **query-log.jsonl**：重複判定には使わない。同じキーワードでも着目点が違えば拾う論文が変わるため、クエリ文字列の一致で再実行の要否は決められない。「もっと他を」と言われた時だけ読み、既出の角度を避ける材料にする。
- **landscape.md**：目的と探索の意味づけ。目的欄は scout / orchestrator がソース選択・隣接軸提案の判断材料として読む（「メソッド選定」なら手法クラスタ・被引用集中、「先行研究の網羅」なら漏れ防止、「KOL 把握」なら著者・所属を優先）。効かなかった軸の記録は「もう試した」という人間版の重複回避になる。

スキーマと書き込み方法の詳細は `AGENTS.md` を参照。

### 5.2 プロジェクト

- 状態の肥大・破損を避けるため、**プロジェクト単位で管理**する（トピック横断のグローバル DB は作らない）。各プロジェクトは自己完結フォルダで、複製・破棄が容易。
- `/new-project <name>` は `workspace/<name>/` に空の `seen.jsonl`・`query-log.jsonl` と、次の雛形の `landscape.md` を置くだけ。

  ```markdown
  # {name}

  ## 目的
  （この調査が何を目指すか。1〜2行。）

  ## 探索済みの軸

  ## 手薄な軸

  ## 効いた検索軸

  ## 効かなかった／広すぎた軸
  ```

- **プロジェクトを作る＝本腰を入れる意思表示**。軽い検索は `_scratch/`（状態を残さない）で行う。
- `workspace/` の中身（調査内容）はローカル専用で、リポジトリには含めない。
- KOL 調査（MSL 用途）は、論文の重複回避と関心が異なるため**著者軸の別プロジェクト**として切り出す想定（詳細は未設計）。

---

## 6. 外部ソース

| ソース | 用途 | 接続方式 |
|---|---|---|
| **PubMed** | ① 精密な網羅探索（MeSH 語彙） | MCP（`pubmed`、認証不要） |
| **Semantic Scholar** | ① 新規開拓 | 未接続 |
| **OpenAlex** | ② 俯瞰・著者ネットワーク | MCP ではなく公開 REST API を `curl` で直接呼ぶ |
| **Scite** | ③ 引用文脈評価（supporting / contrasting / mentioning、撤回） | MCP（`scite`、契約済み・OAuth）。Zotero 同梱の Scite ツールが fallback |
| **Zotero** | 文献蓄積・所持照合（`--exclude-zotero` の照合先） | MCP（`zotero`、ローカル） |
| **Obsidian** | 二次情報の出力先 | 未接続（`workspace/<project>/digest-*.md` に代替出力） |

- MCP のサーバー名を両ランタイムで揃えているので、ツール名（`mcp__pubmed__*` 等）が一致し、手順書を書き分けずに済む。
- OpenAlex の Boolean 検索は PubMed ほど精密でないため、自然言語を丸ごと 1 クエリにせず concept / filter に分解して組む。
- 各ランタイムでの最新の接続状況は `AGENTS.md`「MCP 接続状況」を正とする。

---

## 7. ディレクトリ構造

```
literature-search-cli/
├── AGENTS.md                     # 共通規約の正本（Codex が直接読む）
├── CLAUDE.md                     # Claude Code 用エントリ（@AGENTS.md を読み込むだけ）
├── .claude/                      # 手順書の正本（両ランタイム共通）
│   ├── agents/                   #   役割の手順：scout / cartographer / network / citation / synthesizer / orchestrator
│   └── commands/                 #   コマンド：new-project / scout / map / network / cite / digest / ask
├── .agents/skills/<cmd>/SKILL.md # Codex アダプタ：$scout 等の skill（正本を指すだけ）
├── .codex/
│   ├── config.toml               # Codex プロジェクト設定（PubMed / Scite MCP。trusted 時のみ有効）
│   └── agents/<role>.toml        # Codex アダプタ：custom agent（正本を指すだけ）
└── workspace/                    # 調査プロジェクト（ローカル専用・gitignore）
    ├── _scratch/                 #   状態レスの使い捨て探索
    └── <project>/
        ├── seen.jsonl
        ├── query-log.jsonl
        └── landscape.md
```

---

## 8. 両ランタイムでの維持

構成を変える時は、どちらのランタイムで作業していても `AGENTS.md`「デュアルランタイム維持規約」に従う。要点：

- 手順・規約は正本（`AGENTS.md`・`.claude/commands/`・`.claude/agents/`）だけを直す。アダプタに手順を書き写さない。
- コマンド・役割の追加／改名／削除は、Claude Code 側と Codex 側を対で行う。
- MCP は両ランタイムに同じサーバー名で登録する。
- 機密・個人設定はコミットしない（このリポジトリは公開）。

---

## 9. 未確定・後続設計事項

- Semantic Scholar の接続（scout の開拓探索）。
- Obsidian MCP の接続と、synthesizer の出力先の切り替え（ツール名 `mcp__obsidian__*` は未確定）。
- KOL 調査プロジェクトの詳細設計（著者軸・共著関係追跡の状態設計）。
- DOI 欠損 preprint の近似照合をどこまで作り込むか。
