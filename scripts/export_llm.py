#!/usr/bin/env python3
"""LLM 学習用エクスポート(corpus#3)。raw 層 → datasets/*.jsonl。

- 1 レコード = 1 事例。provenance(source_url/fetched_at/revision)必須。
- 汚染防止: datasets/eval_urls.txt(core が定理・教義・e2 リプレイで引用する裁決)を
  eval split に隔離。AccountingBench-JP(core#4)と共用。
- 学習方法(RAG/fine-tune/vendor 提供)は別途議論 — ここは「学習可能な形」まで。

使い方: python3 scripts/export_llm.py
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "datasets"


def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def main():
    OUT.mkdir(exist_ok=True)
    eval_urls = set((OUT / "eval_urls.txt").read_text().split())
    rev = revision()
    n = {"train": 0, "eval": 0}
    seen: set[str] = set()

    with (OUT / "rulings.jsonl").open("w", encoding="utf-8") as w:
        # 号別(新形式・No.76〜)を優先し、レガシー集約は未収載分のみ
        for p in sorted(ROOT.glob("raw/*/rulings/*.json")):
            for r in json.loads(p.read_text(encoding="utf-8")):
                if r["url"] in seen:
                    continue
                seen.add(r["url"])
                split = "eval" if r["url"] in eval_urls else "train"
                n[split] += 1
                w.write(json.dumps({
                    "id": re.sub(r".*/JP/(\d+)/(\d+)/.*", r"JP-\1-\2", r["url"]),
                    "kind": "tribunal_ruling", "tax": p.parts[-3],
                    "title": r["title"], "category": r.get("category", ""),
                    "summary": r.get("summary", ""), "date": r.get("ruling_date", ""),
                    "text": r["markdown"], "split": split,
                    "source_url": r["url"], "fetched_at": r.get("fetched_at", ""),
                    "license": "著作権法13条(権利の目的とならない)", "revision": rev,
                }, ensure_ascii=False) + "\n")
        for p in sorted(ROOT.glob("raw/*/tribunal_rulings.json")):
            for r in json.loads(p.read_text(encoding="utf-8")):
                if r["url"] in seen:
                    continue
                seen.add(r["url"])
                split = "eval" if r["url"] in eval_urls else "train"
                n[split] += 1
                w.write(json.dumps({
                    "id": re.sub(r".*/JP/(\d+)/(\d+)/.*", r"JP-\1-\2", r["url"]),
                    "kind": "tribunal_ruling", "tax": p.parts[-2],
                    "title": r["title"], "category": "", "summary": "", "date": "",
                    "text": r["markdown"], "split": split,
                    "source_url": r["url"], "fetched_at": "",
                    "license": "著作権法13条(権利の目的とならない)", "revision": rev,
                }, ensure_ascii=False) + "\n")

    with (OUT / "guidance.jsonl").open("w", encoding="utf-8") as w:
        for p in sorted(ROOT.glob("raw/guidance/*/*.json")):
            r = json.loads(p.read_text(encoding="utf-8"))
            n["train"] += 1
            w.write(json.dumps({
                "id": p.stem, "kind": "advance_ruling_reply", "tax": "consumption_tax",
                "title": r["title"], "text": r["markdown"], "split": "train",
                "source_url": r["url"], "fetched_at": r["fetched_at"],
                "license": "政府標準利用規約(CC BY 4.0 互換)", "revision": rev,
            }, ensure_ascii=False) + "\n")

    print(f"train={n['train']} eval={n['eval']} → {OUT}/rulings.jsonl, guidance.jsonl")


if __name__ == "__main__":
    main()
