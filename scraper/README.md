# 楽天GORA 関東エリア Par情報スクレイパー

楽天GORAの関東7都県（茨城・栃木・群馬・埼玉・千葉・東京・神奈川）のゴルフ場一覧を取得し、
各コースのPar情報をJSONファイルに保存するスクリプトです。

## 必要環境

- Python 3.10 以上

## インストール

```bash
cd scraper
pip install -r requirements.txt
```

## 実行方法

```bash
cd scraper
python rakuten_gora_par_scraper.py
```

実行が完了すると、スクリプトと同じディレクトリに `rakuten_gora_kanto_par.json` が生成されます。

### テスト実行（件数制限）

スクリプト冒頭の `MAX_COURSES` 定数を変更することで取得件数を制限できます。

```python
# scraper/rakuten_gora_par_scraper.py の先頭付近
MAX_COURSES = 10   # 10件だけ取得して動作確認
MAX_COURSES = None # None で全件取得（デフォルト）
```

## 出力フォーマット

```json
{
  "scraped_at": "2025-01-01T00:00:00+00:00",
  "area": "関東",
  "total_courses_found": 555,
  "courses_with_par": 480,
  "courses_without_par": 75,
  "data": [
    {
      "c_id": "80015",
      "name": "ゴルフ場名",
      "prefecture": "茨城県",
      "url": "https://booking.gora.golf.rakuten.co.jp/guide/course_info/disp/c_id/80015/",
      "courses": {
        "東コース": {
          "H01": 4,
          "H02": 4,
          "H03": 3,
          "H04": 5,
          "H05": 4,
          "H06": 3,
          "H07": 4,
          "H08": 5,
          "H09": 4
        }
      }
    }
  ]
}
```

### フィールド説明

| フィールド | 説明 |
|---|---|
| `scraped_at` | スクレイピング実行日時（ISO 8601 UTC） |
| `total_courses_found` | 一覧ページで発見したゴルフ場の総数 |
| `courses_with_par` | Par情報を取得できたゴルフ場数 |
| `courses_without_par` | Par情報が取得できなかったゴルフ場数 |
| `data[].c_id` | 楽天GORAのゴルフ場ID |
| `data[].courses` | コース名をキーとしたPar情報（`H01`〜`H18`形式） |

## 注意事項

- リクエスト間隔を1.2秒設けています（サーバー負荷軽減のため変更しないでください）
- 楽天GORAの利用規約・ロボット排除規約を確認のうえご利用ください
- ページ構造の変更によりスクレイピングが失敗する場合があります
