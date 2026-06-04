# TASK: large bounds expressway を除外した有効expresswayログを追加する

## 目的

expressway の実データ確認で、少数の巨大boundsが広範囲のGridCellにかかっている可能性が高いことが分かった。

前回ログ:

```text
expressway_cells=188
expressway_avg_overlap=0.7493
expressway_large_bounds_features=2
expressway_large_bounds_cells=141
motorway_cells=156
motorway_avg_overlap=0.8234
```

この状態で expressway を採点に入れると、エリア全体を底上げしてしまう可能性がある。

今回のTASKでは、**large bounds expressway を除外した場合に、採点候補として使えそうな有効expresswayがどれくらい残るか**をログで確認できるようにする。

今回も **採点ロジックは変更しない**。

## 実装方針

### 1. effective expressway summary を追加する

`services.py` に、large bounds expressway を除外した有効expressway用summary関数を追加する。

想定名:

```python
summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
)
```

対象:

```python
feature["kind"] == "expressway"
```

ただし、以下のlarge bounds判定に該当するfeatureは、有効expresswayから除外する。

```python
size_ratios["area_ratio"] > MAX_EXPRESSWAY_BOUNDS_AREA_RATIO_FOR_LOG
or size_ratios["height_ratio"] > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
or size_ratios["width_ratio"] > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
```

既存の `MAX_EXPRESSWAY_BOUNDS_AREA_RATIO_FOR_LOG` / `MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG` を使う。

### 2. 集計項目

以下を集計する。

```text
effective_expressway_features
effective_expressway_cells
effective_expressway_avg_overlap
effective_expressway_max_overlap

effective_motorway_features
effective_motorway_cells
effective_motorway_avg_overlap
effective_motorway_max_overlap

effective_motorway_link_features
effective_motorway_link_cells
effective_motorway_link_avg_overlap
effective_motorway_link_max_overlap

effective_trunk_features
effective_trunk_cells
effective_trunk_avg_overlap
effective_trunk_max_overlap

effective_trunk_link_features
effective_trunk_link_cells
effective_trunk_link_avg_overlap
effective_trunk_link_max_overlap

filtered_expressway_large_bounds_features
filtered_expressway_large_bounds_cells
```

可能なら `effective_unknown_expressway_*` も追加する。

### 3. overlap集計方針

- `*_features`: large boundsを除外したfeature件数
- `*_cells`: large boundsを除外したfeatureと1件以上交差したGridCell数
- `*_avg_overlap`: 交差セルごとの最大overlapの平均
- `*_max_overlap`: 最大overlap
- `filtered_expressway_large_bounds_features`: 除外対象になったlarge bounds feature数
- `filtered_expressway_large_bounds_cells`: 除外対象featureと交差したGridCell数

同じセルに複数featureが交差する場合は、セルごとの最大overlapを使う。

### 4. FeatureSummariesByPosition に接続する

`build_feature_summaries_for_map_area_from_overpass()` で接続する。

```python
feature_summaries.effective_expressway_summary = (
    summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
        grid_cell_contexts,
        map_features,
    )
)
```

既存の以下は維持する。

```python
feature_summaries.expressway_summary
feature_summaries.expressway_bounds_summary
```

### 5. views.py にログを追加する

`views.py` にログ関数を追加する。

想定名:

```python
log_overpass_effective_expressway_summary(
    area,
    user_id,
    effective_expressway_summary=None,
)
```

ログ名:

```text
Overpass auto effective expressway summary
```

出力項目例:

```text
effective_expressway_features=...
effective_expressway_cells=...
effective_expressway_avg_overlap=...
effective_expressway_max_overlap=...
effective_motorway_features=...
effective_motorway_cells=...
effective_motorway_avg_overlap=...
effective_motorway_max_overlap=...
effective_trunk_features=...
effective_trunk_cells=...
effective_trunk_avg_overlap=...
effective_trunk_max_overlap=...
filtered_expressway_large_bounds_features=...
filtered_expressway_large_bounds_cells=...
```

`MapAreaListCreateView.post()` の `initial_score_mode=auto` 成功時に既存ログと同じ流れで出力する。

## テスト観点

`test_osm_services.py` と必要に応じて `tests.py` を更新する。

確認すること:

- effective expressway summary 関数が追加されている
- expressway がない場合、各値が0になる
- large boundsでない motorway / trunk などが effective_* に集計される
- large bounds expressway は effective_* から除外される
- large bounds expressway は filtered_expressway_large_bounds_* に集計される
- `effective_*_cells` が交差セル数になる
- `effective_*_avg_overlap` / `effective_*_max_overlap` が計算される
- 今回の変更で `initial_score` は変わらない
- `Overpass auto effective expressway summary` がログに出る
- 既存の `Overpass auto expressway summary` / `Overpass auto expressway bounds summary` は維持される

## 注意

- 今回は採点ロジックを変更しない
- expressway を initial_score に反映しない
- large bounds expressway を取得対象から削除しない
- あくまで「有効候補から除外した場合のログ」を追加する
- road を採点寄与に戻さない
- station / surface railway / water / river / park / forest の既存採点は変更しない
- DB、model、migration は変更しない
- memo.md は触らない
- 確認コマンドやテストコマンドは実行しない

## 作業完了時に説明してほしいこと

- 変更したファイル
- 追加したeffective summary関数
- large bounds除外条件
- 追加したログ項目
- initial_score に影響しないこと
- 追加・更新したテスト観点
- 実データ確認時に見るべきログ項目