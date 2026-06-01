````markdown
# Codex タスク: Overpass自動判定成功時に feature_summary の集計ログを1行出す

## 目的

MapArea作成APIで `initial_score_mode=auto` の自動判定が成功したとき、`feature_summaries_by_position` の内容を集計し、サーバーログで確認できるようにしてください。

今回は **ログ追加のみ** を行います。  
スコア計算式、APIレスポンス、demo表示、DB構造は変更しないでください。

## 対象ファイル

主に以下を対象にしてください。

- `maps/views.py`
- `maps/tests.py`

必要な場合のみ確認してください。

- `maps/services.py`

## 現在の前提

現在、MapArea作成APIでは `initial_score_mode=auto` の場合に、Overpass由来の `feature_summaries_by_position` を取得し、成功時には `info` ログ、失敗時には `warning` ログを出すようになっています。

今回追加したいのは、成功時に以下のような **feature_summary集計ログ** を1行出すことです。

```text
Overpass auto feature summary: area_id=... user_id=... summary_count=... building_cells=... road_cells=... park_cells=... river_cells=... coastal_cells=... water_cells=... forest_cells=...
```

## やること

`initial_score_mode=auto` の成功時、`feature_summaries_by_position` をもとに以下を集計して `logger.info()` で出してください。

集計項目:

- `summary_count`
  - `feature_summaries_by_position` の件数
- `building_cells`
  - `building_count > 0` のセル数
- `road_cells`
  - `road_count > 0` のセル数
- `park_cells`
  - `has_park == True` のセル数
- `river_cells`
  - `has_river == True` のセル数
- `coastal_cells`
  - `is_coastal == True` のセル数
- `water_cells`
  - `water_coverage_ratio > 0` のセル数
- `forest_cells`
  - `forest_coverage_ratio > 0` のセル数

## 実装方針

- `print()` は使わず、既存の `logger` を使ってください。
- ログは1行にしてください。
- GridCellごとの詳細はログに出さないでください。
- Overpassレスポンス全文はログに出さないでください。
- Overpassクエリ全文はログに出さないでください。
- 緯度経度の詳細はログに出さないでください。
- APIレスポンスには何も追加しないでください。
- fallback仕様は変更しないでください。
- `manual` の場合はこのログを出さないでください。

## 注意点

- `feature_summaries_by_position` は `(row_index, col_index)` をkey、`feature_summary` をvalueにしたdictです。
- 集計時に個別セルの値が存在しない場合は、0またはFalse扱いで構いません。
- 既存の成功ログは残して構いません。
- 既存の成功ログに集計項目を統合しても構いませんが、ログが読みやすいようにしてください。
- 失敗時のwarningログは今のまま維持してください。

## テスト方針

`maps/tests.py` の `MapAreaCreateViewTests` にある `initial_score_mode=auto` 成功時のログ確認テストを更新してください。

確認したいこと:

- auto成功時に `Overpass auto feature summary` 相当のログが出る
- ログに `summary_count` が含まれる
- ログに `building_cells` が含まれる
- ログに `road_cells` が含まれる
- ログに `park_cells` が含まれる
- ログに `river_cells` が含まれる
- ログに `coastal_cells` が含まれる
- ログに `water_cells` が含まれる
- ログに `forest_cells` が含まれる
- APIレスポンスは従来通り `201 Created`
- `manual` の場合はOverpass helperが呼ばれない既存確認を維持する

テストでは実際のOverpass API通信を行わず、既存通り `build_feature_summaries_for_map_area_from_overpass` をmockしてください。

## 今回やらないこと

- スコア計算式変更
- feature_summaryの保存
- APIレスポンスへの集計値追加
- demo画面への表示
- README.md更新
- API_SPEC.md更新
- DB変更
- migration作成
- model変更
- serializer変更
- Overpass取得処理の変更
- fallback仕様変更
- GridCellごとの詳細ログ出力

## 確認コマンド

作業後、以下を実行してください。

```bash
source .venv/bin/activate
python manage.py check
python manage.py test maps.tests.MapAreaCreateViewTests
python manage.py test maps
git diff --check -- maps/views.py maps/tests.py
```

## 実装後の報告

報告は短くしてください。

- 追加したログ内容
- 更新したテスト
- 実行した確認コマンド
- 結果

成功時の報告は3〜5行程度で構いません。
````
