# datasets/ のライセンス(層別・corpus#3)

| ファイル | 中身 | ライセンス |
|---|---|---|
| rulings.jsonl | 裁決事例集(国税不服審判所) | **著作権法13条1・3号**(裁決は権利の目的とならない)。編集著作権を主張しない |
| guidance.jsonl | 文書回答事例(国税庁) | 政府標準利用規約 第2.0版(CC BY 4.0 互換)。出典: 各レコード source_url |
| eval_urls.txt | 汚染防止リスト(core 引用裁決) | 本 repo 由来(URL リストのみ) |

## 利用上の規律

- **split=eval のレコードを学習に使わない**こと(AccountingBench-JP = core#4 の採点対象。
  学習混入はベンチ無効化 = 汚染)。
- 数値・文言の正本は各 source_url の原本。text は抽出 advisory(corpus#12)。
- 構造化層(論点分解)・手筋層・実務ログ層は本 repo に**含まれない**(private。core#73/#74)。
