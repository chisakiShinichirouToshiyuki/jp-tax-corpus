# jp-tax-corpus — 日本の税務裁決・法令コーパス(raw 層・public)

国税不服審判所の**公表裁決**と法令の原文コーパス。再現性の根拠となる、**版管理された正本**。

## 法的根拠(なぜ public にできるか)

- 裁決: 著作権法13条3号(行政庁の裁決・決定で裁判に準ずる手続によるもの)により**著作権の目的とならない**
- 法令・通達: 同13条1号
- 出典サイト(kfs.go.jp / laws.e-gov.go.jp)は政府標準利用規約系(出典明記で再配布可)

**本 repo は原文(raw)のみ**。アノテーション(結論ラベル・論点分類・教義対応)は含まない(別管理)。

## 構造

```
raw/
  consumption_tax/  tribunal_index.json, tribunal_rulings.json  (公表裁決 255件)
  corporate_tax/    tribunal_rulings.json                       (367件)
  inheritance_tax/  tribunal_rulings.json                       (347件)
```

各 json は `[{ "url", "title", "markdown" }]` の配列。取得: 2025-08-12(kfs.go.jp。原文は Shift-JIS を UTF-8 化済)。
更新は差分検出つき定期取得が書き込む。

## SQL で検索する(無料の Athena 相当)

[DuckDB](https://duckdb.org)(ローカル or ブラウザ [shell.duckdb.org](https://shell.duckdb.org))で raw URL を直接クエリできる:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT title, url
FROM read_json_auto('https://raw.githubusercontent.com/chisakiShinichirouToshiyuki/jp-tax-corpus/main/raw/consumption_tax/tribunal_index.json')
WHERE markdown LIKE '%簡易課税%';
```

大きなクエリを高速化したい場合は Parquet 版を追加予定(範囲リクエストで部分読みが効く)。

## 取得ポリシー(法的クリアランスと負荷への配慮・2026-07-13 制定)

本 repo へのデータ取得(バックフィル・定期差分)は以下を**コードで強制**する:

1. **法的根拠**: 対象は政府公開情報のみ。著作権法13条(法令・裁決)+政府標準利用規約(NTA/MOF: 出典明記で複製・再配布可)。公開ページの GET のみを行い、認証回避・非公開領域へのアクセスは行わない
2. **robots.txt の遵守(コードで強制)**: 取得前に対象ホストの robots.txt を取得・パースし、**Disallow に該当するパスへはアクセスしない**(法的拘束力の有無に関わらず遵守)。robots.txt が取得できない場合は保守的に取得を中止する
3. **負荷への配慮**: リクエスト間隔 **2秒以上**(1req/2s)をコードに固定(サイト側の障害を誘発しない = 岡崎図書館事件の教訓)。再試行は指数バックオフ・並列取得禁止
4. **身元の明示**: User-Agent に repo URL を含め、問い合わせ可能にする(例: `tax-corpus-fetcher (+https://github.com/chisakiShinichirouToshiyuki/jp-tax-corpus)`)
5. **更新検知は低負荷手段を優先**: NTA = sitemap.xml の lastmod 差分 / kfs = idx 番号の単調増加(index 1ページ) / e-Gov = API v2。全文の再取得はしない
6. **provenance**: 全レコードに出典 URL・取得日を付し、取得は号/バッチ単位の1コミット(差分レビュー可能)

## 利用条件

原文の著作権は上記のとおり目的外。本 repo の編集(構造化)は CC0。出典(裁決番号・URL)の明記を推奨。
