#!/usr/bin/env python3
"""kfs(国税不服審判所)裁決事例集の取得(corpus#10 バックフィル / #8 定期差分の共用部品)。

取得ポリシー(README)のコード強制:
  1. robots.txt を fetch 前に照合。取得不能時は保守的に中止。
  2. 1req/2s 固定(並列禁止)。失敗時は指数バックオフ。
  3. UA に repo URL を明示。
  4. provenance(source_url / fetched_at)を各レコードに記録。
  5. 号単位で raw/{tax}/rulings/{号}.json に書き、号単位で git commit。

使い方: python3 scripts/fetch_kfs.py 76 141
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.robotparser
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.kfs.go.jp"
UA = "jp-tax-corpus-bot/1.0 (+https://github.com/chisakiShinichirouToshiyuki/jp-tax-corpus)"
WAIT = 2.0  # 1req/2s 固定
ROOT = Path(__file__).resolve().parent.parent

SECTION_TO_TAX = {
    "消費税法": "consumption_tax",
    "法人税法": "corporate_tax",
    "相続税法": "inheritance_tax",
}

robots = urllib.robotparser.RobotFileParser()


def init_robots():
    req = urllib.request.Request(f"{BASE}/robots.txt", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            robots.parse(r.read().decode("utf-8", "replace").splitlines())
    except Exception as e:  # 取得不能 → 保守的に全面中止
        sys.exit(f"robots.txt 取得不能のため中止(ポリシー2): {e}")


_last_fetch = [0.0]


def fetch(url: str) -> str | None:
    """robots 照合 + レート制限 + 指数バックオフ付き GET。404 は None。"""
    if not robots.can_fetch(UA, url):
        sys.exit(f"robots.txt が不許可のため中止: {url}")
    for attempt in range(4):
        wait = WAIT - (time.time() - _last_fetch[0])
        if wait > 0:
            time.sleep(wait)
        _last_fetch[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("cp932", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** (attempt + 2))  # 4,8,16,32s
        except Exception:
            time.sleep(2 ** (attempt + 2))
    sys.exit(f"取得失敗(リトライ上限): {url}")


class TextExtractor(HTMLParser):
    """本文をmarkdown風テキストへ(既存 tribunal_rulings.json の体裁に合わせ簡素に)。"""

    SKIP = {"script", "style", "header", "footer", "nav"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0
        self._h: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self._h = "#" * int(tag[1])
            self.parts.append(f"\n\n{self._h} ")
        elif tag in ("p", "div", "li", "tr", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n")
            self._h = None

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        t = "".join(self.parts)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def extract_text(html_src: str) -> tuple[str, str]:
    """(h1タイトル, 本文テキスト)"""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_src, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    p = TextExtractor()
    p.feed(html_src)
    return title, p.text()


def parse_idx(no: int, src: str):
    """号 idx から (section税法, category, 裁決URL, summary, ruling_date) を列挙。"""
    entries = []
    # h2 セクションで分割
    chunks = re.split(r"<h2[^>]*>", src)[1:]
    for chunk in chunks:
        sec = html.unescape(re.sub(r"<[^>]+>", " ", chunk.split("</h2>")[0])).strip()
        for art in re.split(r'<div class="article"', chunk)[1:]:
            m = re.search(rf'href="[^"]*?/{no}/(\d+)/index\.html"', art)
            if not m:
                continue
            url = f"{BASE}/service/JP/{no}/{m.group(1)}/index.html"
            cat = ""
            cm = re.findall(r"<h3[^>]*>(.*?)</h3>", chunk[: chunk.find(art)] or "", re.S)
            if cm:
                cat = html.unescape(re.sub(r"<[^>]+>", "", cm[-1])).strip()
            sm = re.search(r"<p>(?:&emsp;|\s)*(.*?)</p>", art, re.S)
            summary = html.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip() if sm else ""
            dm = re.search(r'article_date">([^<]*)</p>', art)
            entries.append({
                "section": sec,
                "category": cat,
                "url": url,
                "summary": summary,
                "ruling_date": html.unescape(dm.group(1)).strip() if dm else "",
            })
    return entries


def tax_of(section: str) -> str:
    for key, tax in SECTION_TO_TAX.items():
        if key in section:
            return tax
    return "other"


def run_no(no: int) -> bool:
    idx_url = f"{BASE}/service/JP/idx/{no}.html"
    src = fetch(idx_url)
    if src is None:
        print(f"No.{no}: idx 404 → skip", flush=True)
        return False
    per_tax: dict[str, list] = {}
    entries = parse_idx(no, src)
    for e in entries:
        page = fetch(e["url"])
        if page is None:
            print(f"  404: {e['url']}", flush=True)
            continue
        title, body = extract_text(page)
        rec = {
            "url": e["url"],
            "title": title,
            "markdown": body,
            "sai_no": no,
            "section": e["section"],
            "category": e["category"],
            "summary": e["summary"],
            "ruling_date": e["ruling_date"],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_index": idx_url,
        }
        per_tax.setdefault(tax_of(e["section"]), []).append(rec)
    for tax, recs in per_tax.items():
        out = ROOT / "raw" / tax / "rulings" / f"{no}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = ", ".join(f"{t}:{len(r)}" for t, r in sorted(per_tax.items()))
    print(f"No.{no}: {len(entries)}件 ({counts})", flush=True)
    # 号単位コミット(ポリシー5)
    subprocess.run(["git", "add", "raw"], cwd=ROOT, check=True)
    r = subprocess.run(
        ["git", "commit", "-q", "-m",
         f"裁決事例集 No.{no} 取得({len(entries)}件: {counts}) — corpus#10\n\n"
         f"出典: {idx_url}(1req/2s・robots照合済)\n\n"
         "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
        cwd=ROOT)
    return r.returncode == 0


def main():
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    init_robots()
    total = 0
    for no in range(lo, hi + 1):
        if run_no(no):
            total += 1
    print(f"完了: {total} 号をコミット", flush=True)


if __name__ == "__main__":
    main()
