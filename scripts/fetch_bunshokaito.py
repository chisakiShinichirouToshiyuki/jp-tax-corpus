#!/usr/bin/env python3
"""文書回答事例(消費税)のワンショット取得(corpus#9)。取得ポリシー(README)準拠。

索引 /law/bunshokaito/shohi/09.htm(+続葉)から事例ページを列挙し、
raw/guidance/bunshokaito_shohi/{slug}.json に本文+provenance を保存する。

使い方: python3 scripts/fetch_bunshokaito.py
"""
import html
import json
import re
import sys
import time
import urllib.robotparser
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_kfs import TextExtractor  # 本文抽出は kfs と共通の簡素 markdown 風

BASE = "https://www.nta.go.jp"
UA = "jp-tax-corpus-bot/1.0 (+https://github.com/chisakiShinichirouToshiyuki/jp-tax-corpus)"
WAIT = 2.0
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "guidance" / "bunshokaito_shohi"
INDEXES = ["/law/bunshokaito/shohi/09.htm", "/law/bunshokaito/shohi/09_1.htm"]

robots = urllib.robotparser.RobotFileParser()
_last = [0.0]


def init_robots():
    req = urllib.request.Request(f"{BASE}/robots.txt", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            robots.parse(r.read().decode("utf-8", "replace").splitlines())
    except Exception as e:
        sys.exit(f"robots.txt 取得不能のため中止(ポリシー2): {e}")


def fetch(url: str) -> str | None:
    if not robots.can_fetch(UA, url):
        print(f"robots 不許可 → skip: {url}", flush=True)
        return None
    for attempt in range(4):
        w = WAIT - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("cp932", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** (attempt + 2))
        except Exception:
            time.sleep(2 ** (attempt + 2))
    sys.exit(f"取得失敗(リトライ上限): {url}")


def slug_of(url: str) -> str:
    p = url.replace(BASE, "").strip("/")
    p = re.sub(r"\.htm[l]?$", "", p)
    return re.sub(r"[^A-Za-z0-9]+", "_", p).strip("_")


def main():
    init_robots()
    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}  # url -> 索引上のタイトル
    for idx in INDEXES:
        src = fetch(BASE + idx)
        if src is None:
            print(f"索引なし: {idx}", flush=True)
            continue
        for m in re.finditer(r'<a href="(/[^"]*bunshokaito/shohi/[^"]+\.htm)"[^>]*>(.*?)</a>',
                             src, re.S):
            url = BASE + m.group(1)
            title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
            if url not in seen and not m.group(1).endswith(("09.htm", "09_1.htm")):
                seen[url] = title
    print(f"事例リンク {len(seen)} 件", flush=True)
    n_ok = 0
    for url, idx_title in seen.items():
        page = fetch(url)
        if page is None:
            print(f"  404: {url}", flush=True)
            continue
        p = TextExtractor()
        p.feed(page)
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        title = html.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip() if tm else idx_title
        rec = {
            "url": url,
            "title": title,
            "index_title": idx_title,
            "markdown": p.text(),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_index": BASE + INDEXES[0],
        }
        (OUT / f"{slug_of(url)}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        n_ok += 1
    print(f"保存 {n_ok} 件 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
