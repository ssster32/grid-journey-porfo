````markdown id="railway-log-task"
# TASK: railway 系OSM地物を取得し、地上線路・地下線路の件数ログを追加する

## 背景

Django製ポートフォリオ投稿サイトの MapArea / GridCell 自動初期スコア機能を実装中です。

現在、`initial_score_mode=auto` の場合、Overpass API からOSM地物を取得し、GridCellごとの `feature_summary` を作成し、`calculate_initial_score_from_feature_summary()` によって `initial_score` を自動計算しています。

直近では以下の調整を行いました。

- `road_count` を initial_score の採点寄与から外した
- `building` の base_score 寄与を弱めた
- `water penalty` を到達不能そうな水域セルに限定した
- 到達可能そうな川沿い・水辺セルを `waterfront_context` として加点するようにした
- `score breakdown summary` に `unreachable_water_penalty_cells` / `waterfront_context_cells` を追加した

現状、採点結果は概ね良い感じになっています。

次に、線路系のOSM地物を確認したいです。

現在の `build_overpass_query()` では、主に以下を取得しています。

- `building`
- `highway`
- `water`
- `waterway`
- `forest`
- `wood`
- `park`
- `garden`
- `coastline`

しかし、`railway` 系はまだ取得対象に含まれていません。

また、`classify_osm_element()` でも、`railway` 系の分類はまだありません。

## 目的

Overpass APIで `railway` 系OSM地物を取得し、GridCellごとに以下を集計できるようにしてください。

- 地上線路っぽい地物
- 地下鉄・地下線路っぽい地物

今回の目的は、まず実データ上でどの程度取得できるかを確認することです。

そのため、今回の段階では **initial_score の採点にはまだ反映しない** でください。

## 実装方針

### 1. Overpass query に railway 系filterを追加する

`build_overpass_query()` の `target_filters` に、`railway` 系を追加してください。

まずは以下を対象にしてください。

```python
'["railway"="rail"]',
'["railway"="subway"]',
'["railway"="light_rail"]',
'["railway"="tram"]',
```

必要であれば、今後追加しやすいようにコメントを添えてください。

ただし、今回の目的は件数ログなので、対象を広げすぎないでください。

### 2. railway を classify_osm_element() で分類する

`classify_osm_element(tags)` に railway 系の分岐を追加してください。

想定:

```python
railway = tags.get("railway")

if railway in {"rail", "subway", "light_rail", "tram"}:
    return "railway"
```

優先順位は、既存の `coastline` / `waterway` / `water` / `forest` / `park` / `road` / `building` の扱いを壊さないように調整してください。

基本的には、`highway` や `building` より前に railway を判定してよいと思います。

### 3. map_feature に railway属性を保存する

`build_map_feature_from_osm_element()` で、railway系のタグ情報を `map_feature` に残してください。

想定項目:

```python
source_railway
source_tunnel
source_layer
source_bridge
```

例:

```python
railway = tags.get("railway")
if railway:
    map_feature["source_railway"] = railway

if "tunnel" in tags:
    map_feature["source_tunnel"] = tags.get("tunnel")

if "layer" in tags:
    map_feature["source_layer"] = tags.get("layer")

if "bridge" in tags:
    map_feature["source_bridge"] = tags.get("bridge")
```

目的は、後から地上線路・地下線路の判定根拠を確認しやすくすることです。

### 4. 地上線路・地下線路の分類関数を追加する

`services.py` に、railway feature が地下寄りか地上寄りかを判定する関数を追加してください。

想定名:

```python
classify_railway_feature_level(feature)
```

または、

```python
classify_railway_feature_surface_type(feature)
```

戻り値の例:

```python
"surface"
"underground"
"unknown"
```

判定の初期方針:

```python
source_railway = feature.get("source_railway")
source_tunnel = feature.get("source_tunnel")
source_layer = feature.get("source_layer")
```

地下線路扱いの条件例:

- `source_railway == "subway"`
- `source_tunnel == "yes"`
- `source_tunnel == "true"`
- `source_tunnel == "building_passage"` は必要なら地下寄り扱いにしてもよい
- `source_layer` が数値として解釈でき、0未満

地上線路扱いの条件例:

- `source_railway in {"rail", "light_rail", "tram"}`
- かつ `tunnel=yes` ではない
- かつ `layer` が負数ではない

判定できないものは `"unknown"` にしてください。

注意:

- OSMタグには揺れがあるため、最初から完璧な分類を目指さないでください
- `layer` は文字列の可能性があるので、安全に数値変換してください
- 不正な `layer` 値で例外を出すより、`unknown` または地上寄り扱いに倒す方が安全です

### 5. feature_summary に railway count を追加する

`build_feature_summary_for_grid_cell()` の `feature_summary` に以下を追加してください。

```python
"surface_railway_count": 0,
"underground_railway_count": 0,
"unknown_railway_count": 0,
```

`feature_kind == "railway"` の場合、GridCellとboundsが交差していれば、分類に応じてカウントしてください。

例:

```python
railway_type = classify_railway_feature_surface_type(feature)

if railway_type == "surface":
    feature_summary["surface_railway_count"] += 1
elif railway_type == "underground":
    feature_summary["underground_railway_count"] += 1
else:
    feature_summary["unknown_railway_count"] += 1
```

今回の段階では、railway count は **initial_score には使わない** でください。

### 6. railway summary を追加する

`FeatureSummariesByPosition` に、ログ用の railway summary を持たせてください。

既存の以下と同じような位置づけです。

- `river_summary`
- `waterway_summary`
- `waterway_river_bounds_summary`

新しく、以下のような関数を追加してください。

```python
summarize_railway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
)
```

集計したい項目:

```python
railway_features
surface_railway_features
underground_railway_features
unknown_railway_features
railway_cells
surface_railway_cells
underground_railway_cells
unknown_railway_cells
```

意味:

- `*_features`: OSM feature単位の件数
- `*_cells`: その分類のrailwayが1件以上交差したGridCell数

### 7. build_feature_summaries_for_map_area_from_overpass() に railway summary を接続する

`build_feature_summaries_for_map_area_from_overpass()` で、作成した `FeatureSummariesByPosition` に `railway_summary` を追加してください。

想定:

```python
feature_summaries.railway_summary = (
    summarize_railway_feature_matches_for_grid_cell_contexts(
        grid_cell_contexts,
        map_features,
    )
)
```

### 8. views.py に railway summary ログを追加する

`views.py` に railway summary 用のログ関数を追加してください。

想定名:

```python
log_overpass_railway_summary(area, user_id, railway_summary=None)
```

ログ名:

```text
Overpass auto railway summary
```

出力項目の例:

```text
area_id=...
user_id=...
railway_features=...
surface_railway_features=...
underground_railway_features=...
unknown_railway_features=...
railway_cells=...
surface_railway_cells=...
underground_railway_cells=...
unknown_railway_cells=...
```

`MapAreaListCreateView.post()` の `initial_score_mode=auto` 成功時に、既存ログと同じ流れで出力してください。

### 9. 既存ログは壊さない

以下の既存ログは維持してください。

- `Overpass auto initial score succeeded`
- `Overpass auto feature summary`
- `Overpass auto score breakdown summary`
- `Overpass auto river summary`
- `Overpass auto scored river summary`
- `Overpass auto scored natural coverage summary`
- `Overpass auto waterway summary`
- `Overpass auto waterway river bounds summary`

今回のログは追加ログとして出してください。

### 10. initial_score にはまだ使わない

今回のTASKでは、railwayをスコアに反映しないでください。

つまり、以下は行わないでください。

- `railway_count` による base_score 加点
- railway を diversity bonus に追加
- railway を context bonus に追加
- railway による penalty 追加

今回の目的は、まず地上線路・地下線路がOSMからどの程度取れるか、ログで確認することです。

## テスト観点

`test_osm_services.py` と必要に応じて `tests.py` を更新してください。

### services.py 側のテスト

以下を確認してください。

#### Overpass query

- `build_overpass_query()` に `nwr["railway"="rail"]` が含まれる
- `nwr["railway"="subway"]` が含まれる
- `nwr["railway"="light_rail"]` が含まれる
- `nwr["railway"="tram"]` が含まれる

#### OSM分類

- `classify_osm_element({"railway": "rail"}) == "railway"`
- `classify_osm_element({"railway": "subway"}) == "railway"`
- `classify_osm_element({"railway": "light_rail"}) == "railway"`
- `classify_osm_element({"railway": "tram"}) == "railway"`
- 未対応の `railway` 値は `None` または既存方針に合わせた扱いになる
- 既存の `building` / `road` / `river` / `water` / `forest` / `park` / `coastline` 分類を壊さない

#### map_feature変換

- `build_map_feature_from_osm_element()` が railway element を `kind="railway"` として返す
- `source_railway` が保存される
- `tunnel` があれば `source_tunnel` が保存される
- `layer` があれば `source_layer` が保存される
- `bridge` があれば `source_bridge` が保存される

#### railway分類関数

- `railway=subway` は `underground` 扱いになる
- `railway=rail` かつ `tunnel=yes` は `underground` 扱いになる
- `railway=rail` かつ `layer=-1` は `underground` 扱いになる
- `railway=rail` かつ tunnel/layerなしは `surface` 扱いになる
- `railway=light_rail` かつ tunnel/layerなしは `surface` 扱いになる
- `railway=tram` かつ tunnel/layerなしは `surface` 扱いになる
- 不正な `layer` 値でも例外で落ちない

#### feature_summary

- `build_feature_summary_for_grid_cell()` の空summaryに `surface_railway_count` / `underground_railway_count` / `unknown_railway_count` が含まれる
- 地上線路が交差した場合、`surface_railway_count` が増える
- 地下線路が交差した場合、`underground_railway_count` が増える
- 判定不能な線路が交差した場合、`unknown_railway_count` が増える
- railway count は `calculate_initial_score_from_feature_summary()` の結果に影響しない
- railway count は `calculate_initial_score_breakdown_from_feature_summary()` の `base_score` / `diversity_bonus` / `context_bonus` / `penalty` に影響しない

#### railway summary

- `summarize_railway_feature_matches_for_grid_cell_contexts()` が feature件数を分類別に集計する
- `surface_railway_cells` が地上線路に交差したセル数になる
- `underground_railway_cells` が地下線路に交差したセル数になる
- `unknown_railway_cells` が判定不能線路に交差したセル数になる
- railwayがない場合、すべて0になる

### views.py / ログ側のテスト

既存の `initial_score_mode=auto` のログ確認テストに、railwayログ確認を追加してください。

確認例:

- `Overpass auto railway summary` がログに含まれる
- `railway_features=` が含まれる
- `surface_railway_features=` が含まれる
- `underground_railway_features=` が含まれる
- `unknown_railway_features=` が含まれる
- `railway_cells=` が含まれる
- `surface_railway_cells=` が含まれる
- `underground_railway_cells=` が含まれる
- `unknown_railway_cells=` が含まれる

外部Overpass APIへの実リクエストは行わず、既存と同じようにモックで確認してください。

## 実装上の注意

- 今回はDBカラム追加ではありません
- モデルやマイグレーションは、必要がなければ変更しないでください
- railwayは今回、採点には使わないでください
- railwayはまずログ確認用のfeatureとして扱ってください
- roadの採点除外方針は維持してください
- water / river / park / forest の既存採点ロジックは変更しないでください
- 既存ログは削除しないでください
- `memo.md` は今回は触らないでください
- 確認コマンドやテストコマンドは実行しないでください

## 作業完了時に説明してほしいこと

作業完了後、以下を説明してください。

- 変更したファイル
- Overpass query に追加した railway filter
- `classify_osm_element()` での railway 分類
- railway feature に保存する source情報
- 地上線路・地下線路・不明線路の判定条件
- feature_summary に追加した railway count
- 追加した railway summary 関数
- 追加した railway ログ項目
- 追加・更新したテスト観点
- 実データ確認時に見るべきログ項目
- 残る注意点

## 禁止事項

- 確認コマンドやテストコマンドを実行しないでください
- コマンド実行結果を捏造しないでください
- railwayを今回のinitial_score採点に反映しないでください
- `memo.md` は明示指示がない限り変更しないでください
````
