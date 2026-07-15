#!/usr/bin/env python3
"""PDF 変換パイプライン(corpus#12)。取得ポリシー(README)準拠。

1 URL につき 3 点セットを生成する:
  {name}.pdf(原本) + {name}.txt(抽出) + {name}.meta.json(provenance+抽出率)

変換規律(#12): 数値の正本は PDF 原本。抽出テキストは検索・参照用 advisory。
core の記載例 E2E への数値写経は原本目視+ページ番号出典(自動転記禁止)。

抽出: pdftotext -layout 第一段。テキスト層なし頁(chars < THRESHOLD)が全頁なら
tesseract(jpn)へフォールバック(未導入環境では meta に ocr_needed を記録して継続)。

使い方: python3 scripts/fetch_pdf.py <URL> <出力dir/name(拡張子なし)>
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

UA = "jp-tax-corpus-bot/1.0 (+https://github.com/chisakiShinichirouToshiyuki/jp-tax-corpus)"
WAIT = 2.0          # 1req/2s 固定
THRESHOLD = 100     # chars/page がこれ未満 → テキスト層なし頁とみなす


def check_robots(url: str):
    host = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{host.scheme}://{host.netloc}/robots.txt",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except Exception as e:
        sys.exit(f"robots.txt 取得不能のため中止(ポリシー2): {e}")
    if not rp.can_fetch(UA, url):
        sys.exit(f"robots.txt が不許可のため中止: {url}")


def download(url: str, dest: Path) -> str:
    check_robots(url)
    time.sleep(WAIT)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            dest.write_bytes(data)
            return hashlib.sha256(data).hexdigest()
        except Exception:
            time.sleep(2 ** (attempt + 2))
    sys.exit(f"取得失敗(リトライ上限): {url}")


def tool_version(cmd: str) -> str:
    try:
        r = subprocess.run([cmd, "-v"], capture_output=True, text=True)
        return (r.stderr or r.stdout).splitlines()[0].strip()
    except Exception:
        return "unavailable"


def extract(pdf: Path, txt: Path) -> dict:
    """pdftotext -layout → 頁別文字数。全頁閾値未満なら OCR フォールバック。"""
    subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
    pages = txt.read_text(encoding="utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    chars = [len(re.sub(r"\s", "", p)) for p in pages]
    low = [i + 1 for i, c in enumerate(chars) if c < THRESHOLD]
    meta = {
        "tool": f"pdftotext -layout ({tool_version('pdftotext')})",
        "pages": len(pages),
        "chars_per_page": chars,
        "low_text_pages": low,
    }
    if pages and len(low) == len(pages):  # 全頁テキスト層なし → OCR
        if shutil.which("tesseract") and shutil.which("pdftoppm"):
            tmp = txt.parent / (txt.stem + "_ppm")
            subprocess.run(["pdftoppm", "-r", "300", "-png", str(pdf), str(tmp)], check=True)
            parts = []
            for img in sorted(txt.parent.glob(txt.stem + "_ppm*.png")):
                r = subprocess.run(["tesseract", str(img), "stdout", "-l", "jpn"],
                                   capture_output=True, text=True, check=True)
                parts.append(r.stdout)
                img.unlink()
            txt.write_text("\f".join(parts), encoding="utf-8")
            meta["tool"] = f"tesseract jpn ({tool_version('tesseract')})"
            meta["ocr"] = True
        else:
            meta["ocr_needed"] = True  # 環境未整備でも中断しない(Actions で再実行)
    return meta


def main():
    url, out = sys.argv[1], Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf, txt = out.with_suffix(".pdf"), out.with_suffix(".txt")
    if url.startswith("http"):
        sha = download(url, pdf)
    else:  # ローカル PDF(self-test 用。取得は行わない)
        data = Path(url).read_bytes()
        pdf.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
    meta = {
        "source_url": url,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sha256": sha,
        "authority_note": "数値の正本はPDF原本。txtは検索・参照用advisory(corpus#12)",
        **extract(pdf, txt),
    }
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in
                      ("source_url", "sha256", "tool", "pages", "low_text_pages")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
