#!/usr/bin/env python3
"""workspace/<project>/view.html を作る（判断はしない glue）。

入力：runs/*.json・findings/*.json・seen.jsonl・query-log.jsonl・landscape.md・
      view-config.json・bib-cache.jsonl・viewer/card-presets.json
出力：workspace/<project>/view.html（viewer/template.html にデータを埋め込んだ 1 ファイル）

ここで行うのは検証・統合（後勝ち）・埋め込みだけ。採否・カード・回答などの判断は
エージェントが runs/ と findings/ に書いたものをそのまま使う（AGENTS.md「実行記録規約」ほか）。

使い方：
  python tools/build_view.py <project>               ビルド
  python tools/build_view.py <project> --check       検証だけ（書き込まない）
  python tools/build_view.py <project> --fetch-bib   書誌・抄録の欠けをネットから補い
                                                     bib-cache.jsonl に追記してからビルド
                                                     （OpenAlex：DOI の書誌と抄録／PubMed：PMID の書誌と抄録／
                                                       ClinicalTrials.gov：NCT の題名）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "viewer" / "template.html"
PRESETS = ROOT / "viewer" / "card-presets.json"
PLACEHOLDER = "__VIEW_DATA__"

DEPTHS = ["title", "abstract", "fulltext"]
DECISIONS = {"adopt", "hold", "exclude"}
STATUSES = {"active", "answered", "parked", "merged", "dropped"}
TITLE_ONLY_REASONS = {"off_topic", "design", "duplicate", "later", "other"}
POINT_ROLES = {"original", "origin", "tutorial", "comparison", "guideline", "review", "application",
               "critique", "book", "citation_statement"}
OPEN_STATUSES = {"not_found", "not_searched"}
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}_[a-z][a-z0-9-]*$")
UA = {"User-Agent": "literature-search-cli/1.0"}


class Log:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)


# ---------------------------------------------------------------- 読み込み

def read_json(path: Path, log: Log):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        log.error(f"{path.name}: JSON として読めない（{e}）")
        return None


def read_jsonl(path: Path, log: Log) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            log.warn(f"{path.name}:{i} 行目が JSON として読めないため無視")
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def norm_doi(doi) -> str | None:
    if not doi or not isinstance(doi, str):
        return None
    d = doi.strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d or None


class Keyer:
    """論文は DOI、試験は NCT、DOI が無ければ PMID（DOI が分かっていれば DOI に寄せる）、最後に題名+年。"""

    def __init__(self) -> None:
        self.pmid2doi: dict[str, str] = {}

    def learn(self, rec: dict) -> None:
        srcs = rec.get("srcs") or {}
        pmid = rec.get("pmid") or srcs.get("pmid")
        d = norm_doi(rec.get("doi"))
        if pmid and d:
            self.pmid2doi[str(pmid)] = d

    def key(self, rec: dict) -> str | None:
        srcs = rec.get("srcs") or {}
        nct = rec.get("nct") or srcs.get("nct")
        if rec.get("type") == "trial" or (nct and not rec.get("doi")):
            return f"nct:{str(nct).upper()}" if nct else None
        d = norm_doi(rec.get("doi"))
        if d:
            return f"doi:{d}"
        pmid = rec.get("pmid") or srcs.get("pmid")
        if pmid:
            pmid = str(pmid)
            return f"doi:{self.pmid2doi[pmid]}" if pmid in self.pmid2doi else f"pmid:{pmid}"
        bib = rec.get("bib") or {}
        title = rec.get("title") or bib.get("title")
        year = rec.get("year") or bib.get("year")
        if title:
            t = re.sub(r"\W+", " ", str(title).lower()).strip()
            return f"title:{t}|{year or ''}"
        return None


def landscape_purpose(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8-sig")
    m = re.search(r"^##\s*目的\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def extras(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if isinstance(k, str) and k.startswith("x-")}


# ---------------------------------------------------------------- 研究カードの設定

def card_config(proj: Path, log: Log) -> dict:
    presets = json.loads(PRESETS.read_text(encoding="utf-8"))
    cfg_path = proj / "view-config.json"
    cfg = (read_json(cfg_path, log) or {}) if cfg_path.exists() else {}
    card = cfg.get("card") or {}
    name = card.get("preset")
    if name and name not in presets["presets"]:
        log.warn(f"view-config.json: card.preset「{name}」は card-presets.json に無い")
        name = None
    base = presets["presets"].get(name) if name else None
    slots = card.get("slots") or (base or {}).get("slots") or []
    glance = card.get("glance") or (base or {}).get("glance") or [s["id"] for s in slots[:3]]
    by_kind = dict(presets.get("by_kind_default", {}))
    by_kind.update(card.get("by_kind") or {})
    labels = {}
    for p in presets["presets"].values():
        for s in p["slots"]:
            labels.setdefault(s["id"], s["label"])
    for bk in by_kind.values():
        for s in bk.get("slots", []):
            labels.setdefault(s["id"], s["label"])
    for s in slots:
        labels[s["id"]] = s["label"]
    return {"preset": name, "preset_label": (base or {}).get("label"), "configured": bool(cfg_path.exists()),
            "slots": slots, "glance": glance, "by_kind": by_kind,
            "kinds": presets["kinds"], "labels": labels}


# ---------------------------------------------------------------- 書誌・抄録の取得（--fetch-bib）

def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def openalex_abstract(inv) -> str | None:
    if not isinstance(inv, dict) or not inv:
        return None
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    return " ".join(w for _, w in sorted(pos)) or None


def fetch_openalex(dois: list[str], mailto: str, today: str, log: Log) -> list[dict]:
    rows = []
    ok = [d for d in dois if "," not in d and "|" not in d]
    for i in range(0, len(ok), 50):
        chunk = ok[i:i + 50]
        params = {"filter": "doi:" + "|".join(chunk), "per-page": "50",
                  "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index"}
        if mailto:
            params["mailto"] = mailto
        try:
            res = json.loads(http_get("https://api.openalex.org/works?" + urllib.parse.urlencode(params)))
        except Exception as e:  # noqa: BLE001
            log.warn(f"OpenAlex 取得失敗（{len(chunk)} 件分）：{e}")
            continue
        found = set()
        for w in res.get("results", []):
            d = norm_doi(w.get("doi"))
            if not d:
                continue
            found.add(d)
            authors = [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])]
            src = ((w.get("primary_location") or {}).get("source") or {})
            abstract = openalex_abstract(w.get("abstract_inverted_index"))
            row = {"key": f"doi:{d}", "title": w.get("title"), "year": w.get("publication_year"),
                   "authors": [a for a in authors if a][:20], "journal": src.get("display_name"),
                   "oaid": (w.get("id") or "").rsplit("/", 1)[-1], "abstract_tried": True,
                   "via": "openalex", "fetched": today}
            if abstract:
                row["abstract"] = abstract
                row["abstract_src"] = "openalex"
            rows.append(row)
        for d in chunk:
            if d not in found:
                rows.append({"key": f"doi:{d}", "missing": True, "abstract_tried": True,
                             "via": "openalex", "fetched": today})
    return rows


def fetch_pubmed(pmids: list[str], keyer: Keyer, today: str, log: Log) -> list[dict]:
    rows = []
    for i in range(0, len(pmids), 150):
        chunk = pmids[i:i + 150]
        params = {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml", "tool": "literature-search-cli"}
        try:
            xml = http_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params))
            root = ET.fromstring(xml)
        except Exception as e:  # noqa: BLE001
            log.warn(f"PubMed 取得失敗（{len(chunk)} 件分）：{e}")
            continue
        got = set()
        for art in root.iter("PubmedArticle"):
            pmid = (art.findtext("MedlineCitation/PMID") or "").strip()
            if not pmid:
                continue
            got.add(pmid)
            a = art.find("MedlineCitation/Article")
            if a is None:
                continue
            title = "".join(a.find("ArticleTitle").itertext()).strip() if a.find("ArticleTitle") is not None else None
            parts = []
            for t in a.findall("Abstract/AbstractText"):
                txt = "".join(t.itertext()).strip()
                if not txt:
                    continue
                lab = t.get("Label")
                parts.append(f"{lab}: {txt}" if lab else txt)
            authors = []
            for au in a.findall("AuthorList/Author"):
                last, fore = au.findtext("LastName"), au.findtext("ForeName")
                if last:
                    authors.append(f"{fore} {last}" if fore else last)
                elif au.findtext("CollectiveName"):
                    authors.append(au.findtext("CollectiveName"))
            year = a.findtext("Journal/JournalIssue/PubDate/Year") or (a.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
            doi = None
            for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = norm_doi(aid.text)
            if doi:
                keyer.pmid2doi.setdefault(pmid, doi)
            key = f"doi:{keyer.pmid2doi[pmid]}" if pmid in keyer.pmid2doi else f"pmid:{pmid}"
            row = {"key": key, "pmid": pmid, "title": title, "year": int(year) if year[:4].isdigit() else None,
                   "authors": authors[:20], "journal": a.findtext("Journal/Title"),
                   "abstract_tried": True, "via": "pubmed", "fetched": today}
            if parts:
                row["abstract"] = "\n".join(parts)
                row["abstract_src"] = "pubmed"
            rows.append(row)
        for p in chunk:
            if p not in got:
                key = f"doi:{keyer.pmid2doi[p]}" if p in keyer.pmid2doi else f"pmid:{p}"
                rows.append({"key": key, "pmid": p, "missing": True, "abstract_tried": True,
                             "via": "pubmed", "fetched": today})
        time.sleep(0.4)
    return rows


def fetch_trials(ncts: list[str], today: str, log: Log) -> list[dict]:
    rows = []
    for i in range(0, len(ncts), 100):
        chunk = ncts[i:i + 100]
        params = {"filter.ids": ",".join(chunk), "pageSize": "100",
                  "fields": "NCTId,BriefTitle,StartDate,OverallStatus,BriefSummary"}
        try:
            res = json.loads(http_get("https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(params)))
        except Exception as e:  # noqa: BLE001
            log.warn(f"ClinicalTrials.gov 取得失敗（{len(chunk)} 件分）：{e}")
            continue
        for s in res.get("studies", []):
            ps = s.get("protocolSection", {})
            ident, status = ps.get("identificationModule", {}), ps.get("statusModule", {})
            nct = ident.get("nctId")
            if not nct:
                continue
            start = (status.get("startDateStruct") or {}).get("date") or ""
            row = {"key": f"nct:{nct.upper()}", "title": ident.get("briefTitle"),
                   "year": int(start[:4]) if start[:4].isdigit() else None,
                   "status": status.get("overallStatus"), "abstract_tried": True,
                   "via": "clinicaltrials.gov", "fetched": today}
            summary = (ps.get("descriptionModule") or {}).get("briefSummary")
            if summary:
                row["abstract"] = summary
                row["abstract_src"] = "clinicaltrials.gov"
            rows.append(row)
    return rows


def do_fetch(proj: Path, data: dict, keyer: Keyer, log: Log) -> tuple[int, int]:
    cache_path = proj / "bib-cache.jsonl"
    mailto_file = ROOT / ".openalex-mailto"
    mailto = mailto_file.read_text(encoding="utf-8").strip() if mailto_file.exists() else ""
    today = dt.date.today().isoformat()
    need_pubmed, need_openalex, need_trials = [], [], []
    for e in data["papers"]:
        k = e["key"]
        if e.get("_tried") and (e["bib"].get("title") or e.get("_missing")):
            continue
        pmid = (e.get("srcs") or {}).get("pmid")
        if k.startswith("nct:"):
            need_trials.append(k[4:])
        elif pmid:
            need_pubmed.append(str(pmid))
        elif k.startswith("pmid:"):
            need_pubmed.append(k[5:])
        elif k.startswith("doi:"):
            need_openalex.append(k[4:])
    rows = fetch_pubmed(sorted(set(need_pubmed)), keyer, today, log)
    rows += fetch_openalex(sorted(set(need_openalex)), mailto, today, log)
    rows += fetch_trials(sorted(set(need_trials)), today, log)
    if rows:
        old = cache_path.read_text(encoding="utf-8-sig") if cache_path.exists() else ""
        if old and not old.endswith("\n"):
            old += "\n"
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        cache_path.write_text(old + body, encoding="utf-8", newline="\n")
    return len(need_pubmed) + len(need_openalex) + len(need_trials), len(rows)


# ---------------------------------------------------------------- 統合

def depth_rank(d) -> int:
    return DEPTHS.index(d) if d in DEPTHS else -1


def merge_card(dst: dict, src: dict) -> dict:
    out = dict(dst or {})
    for k, v in (src or {}).items():
        if k == "slots" and isinstance(v, dict):
            out["slots"] = {**(out.get("slots") or {}), **{a: b for a, b in v.items() if b not in (None, "")}}
        elif v not in (None, ""):
            out[k] = v
    return out


def build(proj: Path, log: Log, keyer: Keyer | None = None) -> tuple[dict, Keyer]:
    name = proj.name
    keyer = keyer or Keyer()
    seen_rows = read_jsonl(proj / "seen.jsonl", log)
    qlog_rows = read_jsonl(proj / "query-log.jsonl", log)
    bib_rows = read_jsonl(proj / "bib-cache.jsonl", log)
    card_cfg = card_config(proj, log)

    # --- runs
    runs: list[dict] = []
    for path in sorted((proj / "runs").glob("*.json")):
        r = read_json(path, log)
        if not isinstance(r, dict):
            continue
        rid = r.get("run") or path.stem
        if rid != path.stem:
            log.warn(f"runs/{path.name}: run（{rid}）がファイル名と一致しない。ファイル名を正とする")
            rid = path.stem
        if not RUN_ID_RE.match(rid):
            log.warn(f"runs/{path.name}: ファイル名が <YYYY-MM-DD>_<NN>_<cmd> の形でない")
        r["run"] = rid
        r.setdefault("date", rid[:10])
        r.setdefault("cmd", rid.split("_")[2] if rid.count("_") >= 2 else "?")
        for k in ("queries", "papers", "gaps", "title_only"):
            r.setdefault(k, [])
        r["legacy"] = False
        runs.append(r)
    runs.sort(key=lambda r: (r["date"], r["run"]))

    # PMID→DOI の対応を先に集める
    for row in seen_rows:
        keyer.learn(row)
    for r in runs:
        for p in r["papers"] + r["title_only"]:
            if isinstance(p, dict):
                keyer.learn(p)
    for row in bib_rows:
        if row.get("pmid") and str(row.get("key", "")).startswith("doi:"):
            keyer.pmid2doi.setdefault(str(row["pmid"]), row["key"][4:])

    papers: dict[str, dict] = {}

    def get_paper(key: str) -> dict:
        if key not in papers:
            papers[key] = {"key": key, "bib": {}, "occ": [], "used_in": [], "qs": set(), "extra": {}, "card": None,
                           "depth": None, "decision": None, "why": None, "abstract": None,
                           "abstract_src": None, "seen": None, "zot": None, "srcs": {},
                           "in_seen": False, "title_only": False, "trial": key.startswith("nct:")}
        return papers[key]

    def q_tags(p: dict, r: dict) -> list[str]:
        """文献を読んだ目的の問い。papers[].questions が無く、実行の対象の問いが 1 つだけならそれを使う。"""
        tags = p.get("questions")
        if isinstance(tags, str):
            tags = [tags]
        if not tags:
            rq = r.get("questions") or []
            tags = rq if len(rq) == 1 else []
        return [t for t in tags if isinstance(t, str)]

    for r in runs:
        qids = {q.get("id") for q in r["queries"] if isinstance(q, dict)}
        for i, p in enumerate(r["papers"]):
            if not isinstance(p, dict):
                continue
            key = keyer.key(p)
            if not key:
                log.warn(f"runs/{r['run']}.json: papers[{i}] に doi / nct / pmid / 題名が無い")
                continue
            e = get_paper(key)
            for v in p.get("via") or []:
                if v not in qids:
                    log.warn(f"runs/{r['run']}.json: {key} の via「{v}」が queries に無い")
            if p.get("depth") not in (None, *DEPTHS):
                log.warn(f"runs/{r['run']}.json: {key} の depth「{p.get('depth')}」は未定義")
            if p.get("decision") not in (None, *DECISIONS):
                log.warn(f"runs/{r['run']}.json: {key} の decision「{p.get('decision')}」は未定義")
            card = p.get("card")
            if card is not None:
                if not isinstance(card, dict):
                    log.warn(f"runs/{r['run']}.json: {key} の card がオブジェクトでない")
                    card = None
                else:
                    if card.get("kind") and card["kind"] not in card_cfg["kinds"]:
                        log.warn(f"runs/{r['run']}.json: {key} の card.kind「{card['kind']}」は未定義")
                    if not card.get("claim"):
                        log.warn(f"runs/{r['run']}.json: {key} の card に claim が無い")
                    for sid in (card.get("slots") or {}):
                        if sid not in card_cfg["labels"]:
                            log.warn(f"runs/{r['run']}.json: {key} の card.slots「{sid}」は未定義の項目")
            elif p.get("decision") in ("adopt", "hold") and not r.get("reconstructed"):
                log.warn(f"runs/{r['run']}.json: {key} は {p['decision']} だが card が無い")
            qtags = q_tags(p, r)
            e["qs"].update(qtags)
            e["occ"].append({"run": r["run"], "date": r["date"], "via": p.get("via") or [],
                             "new": p.get("new"), "depth": p.get("depth"),
                             "decision": p.get("decision"), "why": p.get("why"), "questions": qtags})
            for k, v in (p.get("bib") or {}).items():
                if v not in (None, "", []):
                    e["bib"][k] = v
            if p.get("pmid"):
                e["srcs"].setdefault("pmid", str(p["pmid"]))
            if depth_rank(p.get("depth")) > depth_rank(e["depth"]):
                e["depth"] = p.get("depth")
            if p.get("decision"):
                e["decision"] = p["decision"]
                e["title_only"] = False
            if p.get("why"):
                e["why"] = p["why"]
            if card:
                e["card"] = merge_card(e["card"], card)
            e["extra"].update(extras(p))
        for i, p in enumerate(r["title_only"]):
            if not isinstance(p, dict):
                continue
            key = keyer.key(p)
            if not key:
                log.warn(f"runs/{r['run']}.json: title_only[{i}] に doi / pmid / 題名が無い")
                continue
            if p.get("reason") and p["reason"] not in TITLE_ONLY_REASONS:
                log.warn(f"runs/{r['run']}.json: title_only の reason「{p['reason']}」は未定義")
            e = get_paper(key)
            qtags = q_tags(p, r)
            e["qs"].update(qtags)
            e["occ"].append({"run": r["run"], "date": r["date"], "via": [p["via"]] if isinstance(p.get("via"), str) else (p.get("via") or []),
                             "new": None, "depth": "title", "decision": "title_only", "why": p.get("note"),
                             "reason": p.get("reason"), "questions": qtags})
            if p.get("title") and not e["bib"].get("title"):
                e["bib"]["title"] = p["title"]
            if p.get("pmid"):
                e["srcs"].setdefault("pmid", str(p["pmid"]))
            if e["depth"] is None:
                e["depth"] = "title"
            if e["decision"] is None:
                e["title_only"] = True

    # --- seen.jsonl（後勝ち）
    seen_last: dict[str, dict] = {}
    for row in seen_rows:
        key = keyer.key(row)
        if key:
            seen_last[key] = {**seen_last.get(key, {}), **row}
    for key, row in seen_last.items():
        e = get_paper(key)
        e["in_seen"] = True
        e["title_only"] = False  # 台帳にある論文は「題名のみの候補」として扱わない
        e["seen"] = row.get("seen")
        e["zot"] = row.get("zot")
        e["srcs"] = {**(row.get("srcs") or {}), **e["srcs"]}

    # --- 記録のない日を復元（query-log と seen だけから）
    covered = set()
    for r in runs:
        for q in r["queries"]:
            if isinstance(q, dict):
                covered.add((q.get("src"), q.get("q"), r["date"]))
    legacy: dict[str, dict] = {}

    def legacy_run(date: str) -> dict:
        if date not in legacy:
            legacy[date] = {"run": f"{date}_00_legacy", "cmd": "legacy", "date": date,
                            "legacy": True, "ask": None, "intent": None,
                            "queries": [], "papers": [], "gaps": [], "title_only": []}
        return legacy[date]

    for row in qlog_rows:
        date = row.get("ran") or "????-??-??"
        if (row.get("src"), row.get("q"), date) in covered:
            continue
        lr = legacy_run(date)
        lr["queries"].append({"id": f"L{len(lr['queries']) + 1}", "src": row.get("src"), "q": row.get("q")})
    for key, e in papers.items():
        if e["occ"] or not e["seen"]:
            continue
        lr = legacy_run(e["seen"])
        lr["papers"].append({"key": key})
        e["occ"].append({"run": lr["run"], "date": e["seen"], "via": [], "new": True,
                         "depth": None, "decision": None, "why": None})
    all_runs = sorted(runs + list(legacy.values()), key=lambda r: (r["date"], r["run"]))

    # --- 書誌・抄録キャッシュ（フィールド単位の後勝ち）
    cache: dict[str, dict] = {}
    for row in bib_rows:
        k = row.get("key")
        if not k:
            continue
        if k.startswith("pmid:") and k[5:] in keyer.pmid2doi:
            k = f"doi:{keyer.pmid2doi[k[5:]]}"
        cur = cache.setdefault(k, {})
        for f, v in row.items():
            if f == "missing":
                cur["missing"] = cur.get("missing", True) and bool(v)
            elif v not in (None, "", []):
                cur[f] = v
    for key, e in papers.items():
        c = cache.get(key)
        if not c:
            continue
        e["_tried"] = bool(c.get("abstract_tried"))
        e["_missing"] = bool(c.get("missing")) and not c.get("title")
        for k in ("title", "year", "authors", "journal", "status"):
            if c.get(k) not in (None, "", []) and not e["bib"].get(k):
                e["bib"][k] = c[k]
        if c.get("abstract"):
            e["abstract"] = c["abstract"]
            e["abstract_src"] = c.get("abstract_src")
        if c.get("oaid"):
            e["srcs"].setdefault("oaid", c["oaid"])
        if c.get("pmid"):
            e["srcs"].setdefault("pmid", c["pmid"])

    # --- 問いと答え（フィールド単位の後勝ち）
    questions: dict[str, dict] = {}
    for path in sorted((proj / "findings").glob("*.json")):
        f = read_json(path, log)
        if not isinstance(f, dict):
            continue
        rid = f.get("run") or path.stem
        date = f.get("date") or rid[:10]
        seen_q = set()
        for i, item in enumerate(f.get("findings") or []):
            if not isinstance(item, dict) or not item.get("q"):
                log.warn(f"findings/{path.name}: findings[{i}] に q（問いの ID）が無い")
                continue
            qid = item["q"]
            if qid in seen_q:
                log.warn(f"findings/{path.name}: {qid} が同じファイルに 2 回ある（後を正とする）")
            seen_q.add(qid)
            if item.get("status") and item["status"] not in STATUSES:
                log.warn(f"findings/{path.name}: {qid} の status「{item['status']}」は未定義")
            q = questions.setdefault(qid, {"q": qid, "history": [], "runs": [], "extra": {}})
            for k, v in item.items():
                if k.startswith("x-"):
                    q["extra"][k] = v
                elif k not in ("q", "runs"):
                    q[k] = v
            q["updated"] = date
            q.setdefault("created", date)
            if rid not in q["runs"]:
                q["runs"].append(rid)
            for extra_run in item.get("runs") or []:
                if extra_run not in q["runs"]:
                    q["runs"].append(extra_run)
            q["history"].append({"run": rid, "date": date, "status": item.get("status"),
                                 "headline": item.get("headline"), "answer": item.get("answer")})

    for qid, q in questions.items():
        q.setdefault("status", "active")
        q.setdefault("points", [])
        if q.get("answer") and not q.get("headline"):
            log.warn(f"問い {qid}: headline（1 行の答え）が無い")
        if q.get("parent") and q["parent"] not in questions:
            log.warn(f"問い {qid}: parent「{q['parent']}」が見つからない")
        if q.get("merged_into") and q["merged_into"] not in questions:
            log.warn(f"問い {qid}: merged_into「{q['merged_into']}」が見つからない")
        for item in q.get("open") or []:
            if isinstance(item, dict):
                if item.get("status") not in (None, *OPEN_STATUSES):
                    log.warn(f"問い {qid}: 未解決の status「{item.get('status')}」は未定義")
                if item.get("status") == "not_found" and not item.get("searched"):
                    log.warn(f"問い {qid}: not_found の未解決に searched（探した検索）が無い")
            elif not isinstance(item, str):
                log.warn(f"問い {qid}: open の項目は文字列か {{text, status, searched}} にする")
        for j, pt in enumerate(q["points"]):
            if pt.get("role") not in (None, *POINT_ROLES):
                log.warn(f"問い {qid}: 根拠の role「{pt.get('role')}」は未定義")
            keys = []
            for ref in pt.get("dois") or []:
                k = keyer.key({"nct": ref} if str(ref).upper().startswith("NCT") else {"doi": ref})
                if not k:
                    continue
                keys.append(k)
                if k not in papers:
                    log.warn(f"問い {qid}: 根拠 {ref} が台帳（runs / seen）に無い")
                    get_paper(k)
                papers[k]["used_in"].append({"q": qid, "point": j})
                papers[k]["qs"].add(qid)
            pt["keys"] = keys
        q["children"] = []
    for e in papers.values():
        for t in sorted(e["qs"]):
            if t not in questions:
                log.warn(f"{e['key']}: questions の「{t}」が findings に無い")
        e["qs"] = sorted(e["qs"], key=qsort)
    for qid, q in questions.items():
        par = q.get("parent")
        if par in questions:
            questions[par]["children"].append(qid)

    # --- 未スクリーニング集合
    resolved = set()
    for r in runs:
        for g in r.get("resolves_gaps") or []:
            resolved.add(g)
    gaps = []
    for r in runs:
        for i, g in enumerate(r["gaps"]):
            if not isinstance(g, dict):
                continue
            gid = f"{r['run']}#{g.get('query') or i + 1}"
            gaps.append({**g, "id": gid, "run": r["run"], "date": r["date"], "resolved": gid in resolved})

    plist = sorted(papers.values(), key=lambda e: e["key"])
    main = [e for e in plist if not e["title_only"]]
    return {
        "schema": "view/2",
        "project": name,
        "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "purpose": landscape_purpose(proj / "landscape.md"),
        "card": card_cfg,
        "runs": all_runs,
        "papers": plist,
        "questions": [questions[k] for k in sorted(questions, key=qsort)],
        "gaps": gaps,
        "stats": {"papers": sum(1 for e in main if not e["trial"]),
                  "trials": sum(1 for e in main if e["trial"]),
                  "title_only": sum(1 for e in plist if e["title_only"]),
                  "cards": sum(1 for e in plist if e["card"]),
                  "abstracts": sum(1 for e in plist if e["abstract"]),
                  "runs": len(runs), "legacy_runs": len(legacy),
                  "queries": sum(len(r["queries"]) for r in all_runs),
                  "missing_bib": sum(1 for e in plist if not e["bib"].get("title"))},
        "warnings": log.warnings,
    }, keyer


def qsort(qid: str):
    m = re.match(r"^Q(\d+)$", qid)
    return (0, int(m.group(1)), "") if m else (1, 0, qid)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--check", action="store_true", help="検証だけ行い、書き込まない")
    ap.add_argument("--fetch-bib", action="store_true", help="書誌・抄録の欠けをネットから補ってからビルド")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    proj = ROOT / "workspace" / args.project
    if not proj.is_dir() or args.project.startswith("_"):
        print(f"プロジェクトが無い：workspace/{args.project}", file=sys.stderr)
        return 2

    log = Log()
    data, keyer = build(proj, log)

    if args.fetch_bib and not args.check:
        fetch_log = Log()
        n_ask, n_rows = do_fetch(proj, data, keyer, fetch_log)
        print(f"書誌・抄録を取得：{n_ask} 件を照会、{n_rows} 行を bib-cache.jsonl に追記")
        log = Log()
        data, _ = build(proj, log, keyer)
        log.warnings = fetch_log.warnings + log.warnings
        data["warnings"] = log.warnings

    s = data["stats"]
    print(f"{data['project']}: 論文 {s['papers']}・試験 {s['trials']}・題名のみ {s['title_only']}"
          f"・実行記録 {s['runs']}（記録の外 {s['legacy_runs']} 日分）・クエリ {s['queries']}"
          f"・問い {len(data['questions'])}・カード {s['cards']}・抄録 {s['abstracts']}・書誌なし {s['missing_bib']}")
    if not data["card"]["configured"]:
        print("  ・view-config.json が無い（研究カードの項目はひな形の既定ラベルで表示）")
    for w in log.warnings:
        print(f"  ⚠ {w}")
    for e in log.errors:
        print(f"  ✖ {e}")
    if log.errors:
        return 1
    if args.check:
        return 0

    for e in data["papers"]:
        e.pop("_tried", None)
        e.pop("_missing", None)
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        print("viewer/template.html に埋め込み位置が無い", file=sys.stderr)
        return 1
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = proj / "view.html"
    out.write_text(tpl.replace(PLACEHOLDER, payload, 1), encoding="utf-8", newline="\n")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
