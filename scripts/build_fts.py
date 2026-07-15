#!/usr/bin/env python3
"""静的 FTS 検索 DB の生成(corpus#1)。

raw/ 全域(裁決 rulings・レガシー tribunal_rulings・文書回答・手引き抽出テキスト)を
1 つの SQLite FTS5(trigram) に集約する。trigram なので日本語の分かち書き不要。
生成物 docs/search/fts.db は GitHub Pages から sql.js-httpvfs で範囲読みされる。

使い方: python3 scripts/build_fts.py
"""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "search" / "fts.db"


def rows():
    # 号別 rulings(#10 形式)
    for p in sorted(ROOT.glob("raw/*/rulings/*.json")):
        tax = p.parts[-3]
        for r in json.loads(p.read_text(encoding="utf-8")):
            yield (f"裁決 No.{r['sai_no']}", tax, r.get("category", ""),
                   r["title"], r["url"], r.get("ruling_date", ""), r["markdown"])
    # レガシー集約(No.47〜75 形式)
    for p in sorted(ROOT.glob("raw/*/tribunal_rulings.json")):
        tax = p.parts[-2]
        for r in json.loads(p.read_text(encoding="utf-8")):
            m = re.search(r"/JP/(\d+)/", r["url"])
            no = m.group(1) if m else "?"
            yield (f"裁決 No.{no}", tax, "", r["title"], r["url"], "", r["markdown"])
    # 文書回答事例(#9)
    for p in sorted(ROOT.glob("raw/guidance/*/*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        yield ("文書回答", "consumption_tax", "", r["title"], r["url"],
               r.get("fetched_at", "")[:10], r["markdown"])
    # 手引き抽出テキスト(#9/#12。頁単位で1行に)
    for p in sorted(ROOT.glob("raw/guides/**/*.txt")):
        meta = json.loads(p.with_suffix(".meta.json").read_text(encoding="utf-8"))
        pages = p.read_text(encoding="utf-8", errors="replace").split("\f")
        for i, page in enumerate(pages, 1):
            if page.strip():
                yield ("手引き", "consumption_tax", p.stem, f"{p.stem} p.{i}",
                       meta["source_url"] + f"#page={i}", meta["fetched_at"][:10], page)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    db = sqlite3.connect(OUT)
    # detail=full 必須(trigram の substring 検索は phrase クエリ = 位置情報前提。
    # detail=none は「phrase queries are not supported」で実測NG)。
    # サイズは 25MB チャンク分割で GitHub 100MB/ファイル制限を回避する。
    db.execute("""CREATE VIRTUAL TABLE docs USING fts5(
        kind, tax, category, title, url UNINDEXED, date, body,
        tokenize='trigram')""")
    n = 0
    for row in rows():
        db.execute("INSERT INTO docs VALUES(?,?,?,?,?,?,?)", row)
        n += 1
    db.commit()
    # httpvfs 向けに page_size を大きめへ(範囲リクエスト回数を削減)
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA page_size=32768")
    db.execute("VACUUM")
    db.close()
    # GitHub の 100MB/ファイル制限対策: 25MB チャンクへ分割(sql.js-httpvfs chunked モード)
    data = OUT.read_bytes()
    chunk = 25 * 1024 * 1024
    for old in OUT.parent.glob("fts.db.*"):
        old.unlink()
    n_chunks = 0
    for i in range(0, len(data), chunk):
        (OUT.parent / f"fts.db.{n_chunks:03d}").write_bytes(data[i:i + chunk])
        n_chunks += 1
    (OUT.parent / "config.json").write_text(json.dumps({
        "serverMode": "chunked", "requestChunkSize": 32768,
        "databaseLengthBytes": len(data), "serverChunkSize": chunk,
        "urlPrefix": "fts.db.", "suffixLength": 3,
    }), encoding="utf-8")
    OUT.unlink()  # 単一巨大ファイルはコミットしない
    print(f"{n} docs → fts.db.000..{n_chunks - 1:03d} ({len(data) // 1024 // 1024} MB, {n_chunks} chunks)")


if __name__ == "__main__":
    main()
