# 文献調査CLI — Claude Code 用エントリ

共通規約の正本は `AGENTS.md`（Claude Code / Codex 共通）。次の行で読み込む。

@AGENTS.md

## Claude Code 固有の補足

- このファイルには Claude Code 固有の事項だけを書く。共通規約・手順は `AGENTS.md` と `.claude/` 配下の正本に書く。
- `.claude/commands/*.md` と `.claude/agents/*.md` は Codex からも手順書として読まれる共通の正本である。編集・追加・改名・削除するときは `AGENTS.md`「デュアルランタイム維持規約」に従い、Codex 側のアダプタ（`.agents/skills/`・`.codex/agents/`）も同時に更新する。
