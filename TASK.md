# 現在のタスク

GridCell 自動生成 service の仕様を設計してください。

# 目的

`MapArea` の緯度経度範囲と `grid_size_meters` をもとに、将来的に `GridCell` を自動生成できるようにするため、まず service の仕様を `API_SPEC.md` に整理します。

今回は設計だけ行います。
`models.py` 変更や migration 作成は行いません。

# 担当役割

API Designer / Backend Developer

# 進め方

このタスクでは、次を行ってください。

- `memo.md` を読んで現在の状況を確認する
- `API_SPEC.md` を読んで既存 API と未実装 API 候補を確認する
- `maps/models.py` を読んで `MapArea` と `GridCell` の現在のフィールドを確認する
- `maps/services.py` を読んで既存 service の書き方を確認する
- `API_SPEC.md` に GridCell 自動生成 service の設計を追記する
- 必要なら `TASK.md` には触れず、完了報告だけ行う

# 何を設計するか

`MapArea` から `GridCell` を自動生成する service を設計します。

想定する service 名:

```python
generate_grid_cells_for_area(map_area)
```

想定する役割:

- `MapArea.north`, `south`, `east`, `west`, `grid_size_meters` をもとにグリッドを作る
- 作成した `GridCell` を DB に保存する
- 生成した `GridCell` 一覧を返す
- 既にその `MapArea` に `GridCell` がある場合の扱いを決める

# 今回やらないこと

- `models.py` は変更しない
- migration は作らない
- `maps/services.py` にはまだ実装しない
- `maps/views.py` にはまだ実装しない
- `maps/urls.py` にはまだ URL を追加しない
- `maps/tests.py` にはまだテストを追加しない
- 外部地図 API は使わない
- 正確な地球測地計算はまだ実装しない
- 地形情報や観光情報から `initial_score` を計算しない
- 認証方式は変更しない
- 依存関係は追加しない

# 最低限決めたい仕様

## service 名

```python
generate_grid_cells_for_area(map_area)
```

## 入力

| 項目 | 内容 |
| --- | --- |
| `map_area` | `MapArea` instance |

## 出力

生成された `GridCell` の一覧。

例:

```python
[grid_cell_1, grid_cell_2, grid_cell_3]
```

## 使用する MapArea の値

| フィールド | 内容 |
| --- | --- |
| `north` | 地図範囲の北端 |
| `south` | 地図範囲の南端 |
| `east` | 地図範囲の東端 |
| `west` | 地図範囲の西端 |
| `grid_size_meters` | 1 マスの大きさ |

## 生成する GridCell の値

| フィールド | 方針 |
| --- | --- |
| `area` | 対象の `MapArea` |
| `row_index` | 上から何行目か。0 始まり |
| `col_index` | 左から何列目か。0 始まり |
| `north` | そのマスの北端 |
| `south` | そのマスの南端 |
| `east` | そのマスの東端 |
| `west` | そのマスの西端 |
| `initial_score` | まずは `0` |
| `average_user_score` | 初期値 `0` |
| `rating_count` | 初期値 `0` |
| `calculated_score` | まずは `initial_score` と同じ `0` |
| `score_updated_at` | `null` |

# 設計で決めてほしいこと

以下を `API_SPEC.md` に整理してください。

## 1. 緯度経度への変換方針

`grid_size_meters` はメートル単位ですが、`MapArea` と `GridCell` は緯度経度で保存しています。

最初の学習用実装では、厳密な測地計算ではなく、簡易計算でよいです。

候補:

```text
1 度の緯度は約 111,000m として扱う
緯度方向の 1 マス = grid_size_meters / 111000
経度方向も最初は同じ近似値を使う
```

ただし、経度は本来緯度によって距離が変わるため、これは簡易実装であることを明記してください。

## 2. 行数・列数の計算

例:

```text
lat_step = grid_size_meters / 111000
lng_step = grid_size_meters / 111000

row_count = ceil((north - south) / lat_step)
col_count = ceil((east - west) / lng_step)
```

## 3. 端のグリッドの扱い

範囲ぴったりに割り切れない場合、最後の行・列は `MapArea` の境界に合わせて小さめのグリッドにする方針にしてください。

例:

```text
cell_north = north - row_index * lat_step
cell_south = max(south, cell_north - lat_step)

cell_west = west + col_index * lng_step
cell_east = min(east, cell_west + lng_step)
```

## 4. 既存 GridCell がある場合

最初の実装では安全のため、既に対象 `MapArea` に `GridCell` が 1 件以上ある場合は新規生成しない方針にしてください。

候補:

```text
既存 GridCell がある場合はエラーにする
```

理由:
- 重複生成を防ぐため
- 既存の採点や集計値を壊さないため
- 削除して再生成する処理は影響が大きいため、別タスクで扱う

## 5. 想定するエラー

| 状況 | 方針 |
| --- | --- |
| `map_area` が存在しない | API 側で 404 にする想定 |
| 対象 `MapArea` に既に `GridCell` がある | service でエラー |
| `grid_size_meters <= 0` | model 制約上は保存できない想定だが、service 側でも念のためエラー候補 |
| `north <= south` | model 制約上は保存できない想定 |
| `east <= west` | model 制約上は保存できない想定 |

## 6. 後続 API の候補

service 設計の後に、次の API を作る想定です。

```text
POST /api/maps/areas/{area_id}/grids/
```

目的:
- 指定した `MapArea` から `GridCell` を自動生成する

今回は API 実装はしません。
`API_SPEC.md` に「後続 API 候補」として軽く書く程度でよいです。

# API_SPEC.md に書いてほしい構成

`API_SPEC.md` の適切な位置に、次のような見出しで追記してください。

```markdown
## 設計中: GridCell 自動生成 service
```

中に以下を含めてください。

- 目的
- service 名
- 入力
- 出力
- 生成する GridCell の項目
- 緯度経度の簡易計算方針
- 行数・列数の計算方針
- 端のグリッドの扱い
- 既存 GridCell がある場合の扱い
- 想定エラー
- 今回は実装しないこと
- 後続 API 候補

# 確認方法

作業後に次を実行してください。

```bash
git diff -- API_SPEC.md
git diff --check -- API_SPEC.md
```

今回は設計だけなので、Django のテスト実行は必須ではありません。
ただし、実装ファイルを変更してしまった場合は必ず次も実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
```

# 完了報告

短めでよいです。

- 変更内容
- 確認結果
- 未対応
- 次にやるとよいこと