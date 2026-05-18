# 現在のタスク

GridCell 自動生成 service を実装し、service テストを追加してください。

# 目的

`MapArea` の緯度経度範囲と `grid_size_meters` をもとに、`GridCell` を自動生成できるようにします。

今回は service 実装と service テスト追加まで行います。
API view / URL 追加はまだ行いません。

# 担当役割

Backend Developer / Tester

# 作業前に確認するファイル

- `memo.md`
- `AGENTS.md`
- `README.md`
- `RULES.md`
- `TASK.md`
- `API_SPEC.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `maps/models.py`
- `maps/services.py`
- `maps/tests.py`

# 編集してよいファイル

- `maps/services.py`
- `maps/tests.py`

必要な場合のみ:

- `API_SPEC.md`
- `TASK.md`

# 変更しないファイル

指示がない限り、次は変更しないでください。

- `maps/models.py`
- `maps/migrations/`
- `maps/views.py`
- `maps/urls.py`
- `maps/serializers.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`

# 実装する service

```python
generate_grid_cells_for_area(map_area)
```

## 入力

| 項目 | 内容 |
| --- | --- |
| `map_area` | `MapArea` instance |

## 出力

生成して DB に保存した `GridCell` の一覧。

```python
[grid_cell_1, grid_cell_2, grid_cell_3]
```

# 実装方針

## 緯度経度の簡易計算

最初の学習用実装では、厳密な測地計算ではなく簡易計算にしてください。

```python
lat_step = map_area.grid_size_meters / 111000
lng_step = map_area.grid_size_meters / 111000
```

注意:

- 経度 1 度あたりの距離は本来緯度によって変わります。
- 今回は学習用の簡易実装として、緯度方向と同じ近似値を使います。
- 外部ライブラリや外部地図 API は使わないでください。

## 行数・列数

```python
row_count = ceil((map_area.north - map_area.south) / lat_step)
col_count = ceil((map_area.east - map_area.west) / lng_step)
```

`math.ceil` を使ってください。

## 端のグリッド

範囲がぴったり割り切れない場合、最後の行・列は `MapArea` の境界に合わせて小さめにしてください。

```python
cell_north = map_area.north - row_index * lat_step
cell_south = max(map_area.south, cell_north - lat_step)

cell_west = map_area.west + col_index * lng_step
cell_east = min(map_area.east, cell_west + lng_step)
```

## 生成する GridCell の値

| フィールド | 値 |
| --- | --- |
| `area` | 対象の `MapArea` |
| `row_index` | 上から何行目か。0 始まり |
| `col_index` | 左から何列目か。0 始まり |
| `north` | そのマスの北端 |
| `south` | そのマスの南端 |
| `east` | そのマスの東端 |
| `west` | そのマスの西端 |
| `initial_score` | `0` |
| `average_user_score` | `0` |
| `rating_count` | `0` |
| `calculated_score` | `0` |
| `score_updated_at` | `None` |

# 既存 GridCell がある場合

対象の `MapArea` に `GridCell` が 1 件以上ある場合は、新規生成しないでください。

方針:

```python
raise ValueError("この MapArea には既に GridCell があります。")
```

理由:

- 重複生成を防ぐため
- 既存の採点や集計値を壊さないため
- 削除して再生成する処理は影響が大きいため

# 入力チェック

`MapArea` model には制約がありますが、service 側でも念のため次をチェックしてください。

| 条件 | 方針 |
| --- | --- |
| `grid_size_meters <= 0` | `ValueError` |
| `north <= south` | `ValueError` |
| `east <= west` | `ValueError` |

# テスト追加

`maps/tests.py` に service テストを追加してください。

最低限ほしいテスト:

1. `MapArea` から `GridCell` が生成される
2. 生成された `GridCell` の `row_index` / `col_index` が 0 始まりになる
3. `initial_score`, `average_user_score`, `rating_count`, `calculated_score`, `score_updated_at` が初期値になる
4. 端のグリッドが `MapArea` の境界を超えない
5. 既に `GridCell` がある場合は `ValueError` になり、新規生成されない
6. `grid_size_meters <= 0` 相当の不正値では `ValueError`
7. `north <= south` 相当の不正値では `ValueError`
8. `east <= west` 相当の不正値では `ValueError`

不正値テストで model 制約に引っかかる場合は、DB に保存済みの `MapArea` instance の属性を一時的に変更して service に渡す形を検討してください。

# 今回やらないこと

- `models.py` の変更
- migration の作成
- API view の追加
- URL の追加
- serializer の追加
- 認証方式の変更
- 依存関係の追加
- 外部地図 API の利用
- 正確な地球測地計算
- 地形情報や観光情報からの `initial_score` 計算

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff -- maps/services.py maps/tests.py
git diff --check -- maps/services.py maps/tests.py
```

# 完了報告

短めでよいので、次を報告してください。

- 担当した役割
- 変更したファイル
- 変更内容
- 初心者向け補足
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業