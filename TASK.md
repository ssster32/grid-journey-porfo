````markdown
# Codex タスク: MapAreaに対して大きすぎる waterway=river bounds による has_river 過検出を抑える

## 目的

Overpass API 由来の `waterway=river` 地物について、`bounds` が MapArea 全体に対して大きすぎる場合に、GridCell ごとの `has_river=True` 判定へそのまま使わないようにしてください。

現在、`waterway=river` の bounds が大きい場合、実際の川の線形ではなく外接矩形で判定しているため、広い範囲の GridCell が `has_river=True` になりすぎることがあります。

今回は **MapAreaに対して大きすぎる waterway=river bounds による has_river 過検出を抑えること** に限定します。

## 背景

同じ中心位置付近で、グリッド設定を変えて確認したところ、以下の差が出ました。

```text
10×10 / 100m:
waterway_river_bounds_features=0
river_cells=0
score_avg=1.82

15×15 / 200m:
waterway_river_bounds_features=15
waterway_river_bounds_intersecting_map_features=15
waterway_river_bounds_covering_map_features=0
waterway_river_bounds_large_area_features=3
waterway_river_bounds_max_area_ratio_to_map=12.3827
waterway_river_bounds_max_height_ratio_to_map=3.0680
waterway_river_bounds_max_width_ratio_to_map=4.0361
river_cells=225
score_avg=2.33
```

`covering_map_features=0` なので、MapArea全体を完全に覆うfeatureだけが原因ではありません。  
一方で、`large_area_features=3`、`max_area_ratio_to_map=12.3827` となっており、MapAreaよりかなり大きい `waterway=river` bounds が取得されています。

このような大きすぎる river bounds が GridCell 単位の `has_river` 判定に使われることで、`river_cells` が全セルに広がっている可能性が高いです。

## 対象ファイル

主に以下を対象にしてください。

- `maps/services.py`
- `maps/test_osm_services.py`

必要な場合のみ確認してください。

- `maps/views.py`
- `maps/tests.py`

## 現在の前提

現在、`maps/services.py` には以下の helper / 定数があります。

```python
calculate_bounds_size_ratios(feature_bounds, grid_cell_bounds)
calculate_bounds_overlap_ratio(feature_bounds, grid_cell_bounds)
summarize_waterway_river_bounds_for_map_area(...)
LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP = 1.0
```

また、`build_map_feature_from_osm_element()` では、OSM element の `tags["waterway"]` を `source_waterway` として保持しています。

例:

```python
{
    "kind": "river",
    "bounds": {...},
    "source": "osm",
    "source_type": "way",
    "source_id": 123,
    "source_waterway": "river",
}
```

現在の `build_feature_summary_for_grid_cell()` では、`river` は以下のような流れで `has_river` を判定しています。

```text
1. GridCell bounds と river feature bounds が交差する
2. feature bounds が GridCell に対して大きすぎるかを見る
3. 大きすぎない、または overlap_ratio が一定以上なら has_river=True
```

今回追加したいのは、これに加えて、

```text
waterway=river の feature bounds が MapArea に対して大きすぎる場合は、
GridCell ごとの has_river 判定に使わない
```

という抑制です。

## 今回やること

### 1. MapAreaに対して大きすぎる waterway=river bounds を判定する helper を追加する

`maps/services.py` に、MapArea bounds と feature を受け取り、その feature を `has_river` 判定に使ってよいか判断する小さな helper を追加してください。

候補名:

```python
should_use_river_feature_for_grid_cell(feature, map_area_bounds)
```

または、既存方針に合わせてより自然な名前にして構いません。

### 2. 判定対象

今回の抑制対象は、以下をすべて満たすものにしてください。

```text
feature["kind"] == "river"
feature["source_waterway"] == "river"
feature bounds が MapArea bounds に対して大きすぎる
```

`waterway=stream` / `waterway=canal` / `source_waterway` なしの river feature は、今回はこの MapArea比による除外対象にしないでください。

理由:

```text
- 今回のログでは waterway=river が原因として見えている
- stream / canal まで同時に変えると影響範囲が広がりすぎる
- unknown は原因が別なので今回は触らない
```

### 3. 判定基準

まずは既存のログ用定数を使い、以下の条件を満たす場合に「MapAreaに対して大きすぎる」とみなしてください。

```text
area_ratio_to_map >= LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP
```

現在の初期値は以下です。

```python
LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP = 1.0
```

つまり、MapAreaと同等以上の面積を持つ `waterway=river` bounds は、GridCell ごとの `has_river` 判定には使わない方針です。

必要であれば、判定用として別名の定数を追加しても構いません。

例:

```python
MAX_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP_FOR_GRID_CELL = 1.0
```

ただし、ログ用定数と判定用定数を分ける場合は、意図が分かる名前にしてください。

## 実装方針

### 1. MapArea bounds を feature_summary 生成時に渡す

現在の `build_feature_summary_for_grid_cell(grid_cell_bounds, map_features)` は、GridCell bounds と map_features だけで判定しています。

今回、MapArea全体に対するriver bounds判定が必要なので、以下のように optional 引数を追加してください。

```python
build_feature_summary_for_grid_cell(
    grid_cell_bounds,
    map_features,
    map_area_bounds=None,
)
```

`map_area_bounds` が `None` の場合は、既存互換のため従来通りの動作にしてください。

### 2. 関連する呼び出し元に map_area_bounds を渡す

以下のような関数で、可能な範囲で `map_area_bounds` を渡してください。

```python
build_feature_summaries_for_grid_cell_contexts(...)
build_feature_summaries_for_map_area_from_overpass(...)
```

`build_feature_summaries_for_grid_cells(...)` については、既存テストや既存用途への影響を避けるため、無理に変更しなくても構いません。  
変更する場合も後方互換を維持してください。

### 3. river 判定で MapArea比の抑制を使う

`build_feature_summary_for_grid_cell()` の `feature_kind == "river"` の処理で、以下の条件に当てはまる feature は `has_river` 判定に使わないでください。

```text
map_area_bounds が渡されている
かつ
feature["source_waterway"] == "river"
かつ
feature bounds の area_ratio_to_map >= LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP
```

この場合、その feature は skip してください。

イメージ:

```python
elif feature_kind == "river":
    if (
        map_area_bounds is not None
        and feature.get("source_waterway") == "river"
        and is_large_waterway_river_bounds_for_map_area(feature_bounds, map_area_bounds)
    ):
        continue

    # 既存の has_river 判定を続ける
```

helper名や構造は、既存コードに合わせて調整してください。

## 重要な制約

- 今回は `has_river` の過検出抑制のみ行ってください
- `source_waterway == "river"` の大きすぎるboundsだけを対象にしてください
- `stream` / `canal` / `unknown` は今回は変更しないでください
- `road` / `park` / `water` / `forest` / `coastline` / `building` は変更しないでください
- `calculate_initial_score_from_feature_summary()` は変更しないでください
- スコア計算式は変更しないでください
- APIレスポンスに項目を追加しないでください
- DB変更やmigrationは行わないでください
- model変更は行わないでください
- serializer変更は行わないでください
- demo表示は変更しないでください
- README.md / API_SPEC.md / memo.md / TASK.md は変更しないでください
- Overpass API接続処理は変更しないでください
- Overpassクエリは変更しないでください
- 外部ライブラリは追加しないでください
- geometryベース判定は導入しないでください
- GridCellごとの詳細ログは出さないでください
- 既存の summary / river summary / waterway summary / waterway river bounds summary ログは維持してください

## テスト方針

テストは追加・更新してください。  
ただし、確認コマンドは実行しないでください。テスト実行はユーザー側で行います。

### maps/test_osm_services.py

以下を確認するテストを追加してください。

#### 1. map_area_bounds がない場合は既存通り has_river=True になる

```text
build_feature_summary_for_grid_cell(grid_cell_bounds, map_features)
に map_area_bounds を渡さない
↓
従来通り river が交差すれば has_river=True
```

#### 2. MapAreaに対して大きすぎる waterway=river は has_river 判定に使われない

```text
source_waterway == "river"
feature bounds の area_ratio_to_map >= 1.0
map_area_bounds が渡されている
↓
has_river=False のまま
```

#### 3. MapAreaに対して大きすぎない waterway=river は従来通り使われる

```text
source_waterway == "river"
feature bounds の area_ratio_to_map < 1.0
map_area_bounds が渡されている
↓
has_river=True
```

#### 4. 大きすぎる stream / canal は今回は除外されない

```text
source_waterway == "stream" または "canal"
feature bounds が MapArea に対して大きい
map_area_bounds が渡されている
↓
従来通り has_river=True になり得る
```

#### 5. build_feature_summaries_for_grid_cell_contexts からも map_area_bounds が効く

```text
build_feature_summaries_for_grid_cell_contexts(...)
で map_area_bounds を渡す
↓
大きすぎる waterway=river が各GridCellの has_river 判定から除外される
```

#### 6. build_feature_summaries_for_map_area_from_overpass で効果が出る

mockした `fetch_osm_features_from_overpass` から、MapAreaより大きい `source_waterway == "river"` feature を返す。

```text
build_feature_summaries_for_map_area_from_overpass(...)
↓
feature_summary の has_river が過剰に True にならない
```

#### 7. 既存の river summary / waterway summary / waterway river bounds summary は壊さない

今回の変更は `has_river` 判定には影響しますが、調査用 summary helper の集計自体は維持してください。

必要に応じて、既存テストの期待値を調整してください。

### maps/tests.py

必要があれば、auto作成時のログテストを更新してください。  
ただし、今回の主対象は service 層なので、Viewのログテストを大きく変更しないでください。

## 実装後の報告

報告は短くしてください。

- 変更したファイル
- 追加したhelperまたは定数
- has_river 判定の変更内容
- 追加・更新したテスト内容
- 注意点や未確認事項

※確認コマンドは実行しないでください。テスト実行はユーザー側で行います。
````
