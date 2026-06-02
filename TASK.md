````markdown
# TASK: road を initial_score の採点寄与から外し、building の base_score 寄与を弱める

## 背景

Django製ポートフォリオ投稿サイトの MapArea / GridCell 自動初期スコア機能を実装中です。

現在、`initial_score_mode=auto` の場合、Overpass API から OSM 地物を取得し、GridCellごとの `feature_summary` を作成し、`calculate_initial_score_from_feature_summary()` によって `initial_score` を自動計算しています。

直近では、スコア内訳確認のために以下を追加しました。

- `calculate_initial_score_breakdown_from_feature_summary()`
- `Overpass auto score breakdown summary`
- `base_score_avg`
- `diversity_bonus_avg`
- `context_bonus_avg`
- `penalty_avg`
- `building_base_cells`
- `road_base_cells`
- `park_context_cells`
- `river_context_cells`
- `forest_context_cells`

実データ確認では、以下のログになっています。

```text
Overpass auto score breakdown summary:
area_id=59
user_id=1
summary_count=225
base_score_avg=1.45
base_score_max=1.50
diversity_bonus_avg=0.66
diversity_bonus_max=0.90
context_bonus_avg=0.27
context_bonus_max=0.60
penalty_avg=0.30
penalty_max=2.40
raw_score_avg=2.07
raw_score_max=3.00
clamped_score_avg=2.07
clamped_score_max=3.00
max_score_cells=1
building_base_cells=225
road_base_cells=225
park_context_cells=146
river_context_cells=117
forest_context_cells=14
coastal_context_cells=0
water_penalty_cells=28
forest_penalty_cells=0
empty_cell_penalty_cells=0
```

この結果から、現在の平均スコアが高めになる主因は `base_score` です。

特に、

```text
base_score_avg=1.45
base_score_max=1.50
building_base_cells=225
road_base_cells=225
```

となっており、建物・道路が全セルで基礎点を大きく押し上げています。

しかし、道路が多いこと自体は必ずしも「面白い場所」「特徴的な場所」とは限りません。  
住宅街や普通の市街地でも道路は多くなるため、`road_count` は initial_score の直接的な採点寄与から外したいです。

一方で、建物は人の活動・店舗・施設密度の目安にはなるため、完全には外さず、base_scoreへの寄与を弱めたいです。

## 目的

`road_count` を `initial_score` の採点寄与から外し、`building_count` による `base_score` 寄与を弱めてください。

目的は以下です。

- 道路が多いだけの住宅街・市街地が高スコアになりすぎるのを防ぐ
- 建物密度による都市部の底上げを弱める
- 水辺・公園・川沿いなど、他の特徴があるセルを相対的に目立たせる
- `road_count` の収集・ログは残し、将来の補助判定に使える余地は残す
- 今回は `road_count` の検出処理自体は削除しない

## 現在の想定スコア式

現在の `calculate_initial_score_breakdown_from_feature_summary()` では、おおよそ以下のような計算になっているはずです。

```python
building_base_bonus = min(building_count / 20, 1.0) * 0.7
road_base_bonus = min(road_count / 10, 1.0) * 0.5
base_score = 0.3 + building_base_bonus + road_base_bonus
```

また、`feature_categories` に `has_road` が含まれている場合、道路は diversity bonus にも影響しているはずです。

```python
feature_categories = [
    has_building,
    has_road,
    has_park,
    has_river,
    is_coastal,
    has_water,
    has_scored_forest,
]
```

今回、この `road` の採点寄与を外してください。

## 実装方針

### 1. base_score 関連の定数を追加する

`services.py` に、base_score関連の定数を追加してください。

想定名:

```python
BASE_INITIAL_SCORE = 0.2
BUILDING_BASE_SCORE_MAX_BONUS = 0.4
BUILDING_COUNT_FOR_MAX_BASE_SCORE = 20
ROAD_BASE_SCORE_MAX_BONUS = 0.0
ROAD_COUNT_FOR_MAX_BASE_SCORE = 10
```

または、既存命名に合わせて自然な名前にしてください。

### 2. road_base_bonus を 0.0 にする

`road_count` の収集処理は残してください。

ただし、`initial_score` の計算では、道路によるbase_score加点をなくしてください。

想定:

```python
road_base_bonus = 0.0
```

`ROAD_BASE_SCORE_MAX_BONUS = 0.0` を使う形でも構いません。

### 3. building_base_bonus を弱める

建物によるbase_score寄与を、現在より弱めてください。

想定:

```python
building_base_bonus = min(building_count / 20, 1.0) * 0.4
```

現在が `0.7` 相当なら、まずは `0.4` に下げてください。

### 4. 固定base_scoreも少し下げる

現在の固定基礎点が `0.3` の場合、以下のように弱めてください。

```python
base_score = 0.2 + building_base_bonus + road_base_bonus
```

目的は、地物が少ないセルや、道路・建物だけのセルが高くなりすぎないようにすることです。

### 5. road を diversity_bonus の feature_categories から外す

道路は多くの場所に存在しすぎるため、「特徴カテゴリの多様性」に含めないようにしてください。

現在のように `has_road` が `feature_categories` に含まれている場合は、以下のように外してください。

変更前のイメージ:

```python
feature_categories = [
    has_building,
    has_road,
    has_park,
    has_river,
    is_coastal,
    has_water,
    has_scored_forest,
]
```

変更後のイメージ:

```python
feature_categories = [
    has_building,
    has_park,
    has_river,
    is_coastal,
    has_water,
    has_scored_forest,
]
```

`has_road` 自体はbreakdownに残して構いません。  
ただし、スコア寄与には使わないでください。

### 6. road_count の収集・ログは残す

以下は削除しないでください。

- `road_count` のfeature_summary収集
- road bounds過検出抑制ロジック
- `road_cells` ログ
- `road_base_cells` ログ

ただし、`road_base_cells` という名称が「道路がbase_scoreに効いているセル」と誤解される場合は、ログ項目名の変更または補足項目の追加を検討してください。

安全にいくなら、既存ログ項目は残した上で、追加項目を出してください。

例:

```text
road_cells=...
road_scored_cells=0
```

ただし、既存テストへの影響が大きい場合は、`road_base_cells` を残しつつ、作業完了説明で「road_base_bonusは0になった」と説明してください。

### 7. breakdownログは維持する

`Overpass auto score breakdown summary` は引き続き出してください。

今回の変更後に確認したい項目は以下です。

```text
base_score_avg
base_score_max
building_base_cells
road_base_cells
road_scored_cells
diversity_bonus_avg
context_bonus_avg
clamped_score_avg
max_score_cells
```

`road_scored_cells` を追加した場合は、常に `0` になる想定です。

### 8. 既存のスコア式のうち、今回対象外の部分は変更しない

今回は以下を変更しないでください。

- `park` の判定
- `river` の判定
- `water` の判定
- `forest` の閾値化済み挙動
- `context_bonus`
- `penalty`
- `INITIAL_SCORE_MIN`
- `INITIAL_SCORE_MAX`

主な変更対象は以下です。

- `base_score`
- `building_base_bonus`
- `road_base_bonus`
- `feature_categories` における `has_road` の扱い

## 期待される変化

現在のログでは、

```text
base_score_avg=1.45
clamped_score_avg=2.07
```

でした。

変更後は、同じ大阪中心部 `15×15 / 200m` で、base_scoreが大きく下がる想定です。

目安:

```text
base_score_avg: 1.45 → 0.5〜0.6前後
clamped_score_avg: 2.07 → 1.2〜1.5前後
```

ただし、実データでは `park` / `river` / `water` の重なりが大きいため、実際の変化はログで確認してください。

## テスト観点

`test_osm_services.py` と必要に応じて `tests.py` を更新してください。

### services.py 側のテスト

以下を確認してください。

- `road_count > 0` でも `road_base_bonus == 0.0` になる
- `road_count > 0` でも、road単体では `base_score` が上がらない
- `road_count > 0` でも、roadは `feature_category_count` に含まれない
- `building_count > 0` の場合、`building_base_bonus` は従来より弱い係数で計算される
- buildingの最大base bonusが `0.4` 相当になる
- `base_score` の固定値が `0.2` 相当になる
- `calculate_initial_score_from_feature_summary()` の戻り値が、breakdownの `clamped_score` と一致する
- `has_road` はbreakdown上に残る
- `road_count` が不正値の場合のバリデーションは維持される
- `park` / `river` / `water` / `forest` / `coastal` の既存挙動は壊れない

### views.py / ログ側のテスト

既存の `initial_score_mode=auto` のログ確認テストを更新してください。

確認例:

- `Overpass auto score breakdown summary` が引き続き出力される
- `base_score_avg` が含まれる
- `building_base_cells` が含まれる
- `road_base_cells` が含まれる
- `road_scored_cells` を追加した場合はログに含まれる
- `road_scored_cells=0` になる
- `diversity_bonus_avg` / `context_bonus_avg` / `penalty_avg` のログが壊れていない

外部Overpass APIへの実リクエストは行わず、既存と同じようにモックで確認してください。

## 実装上の注意

- 今回はDBカラム追加ではありません
- モデルやマイグレーションは、必要がなければ変更しないでください
- `road_count` の収集処理は削除しないでください
- road bounds過検出抑制ロジックは削除しないでください
- 今回は「roadを採点寄与から外す」だけで、「roadをfeature_summaryから消す」わけではありません
- buildingは完全には外さず、弱めるだけにしてください
- `context_bonus` と `penalty` は今回変更しないでください
- `memo.md` は今回は触らないでください
- 確認コマンドやテストコマンドは実行しないでください

## 作業完了時に説明してほしいこと

作業完了後、以下を説明してください。

- 変更したファイル
- 追加・変更したbase_score関連の定数
- roadがどの採点寄与から外れたか
- `road_count` の収集・ログを残したか
- buildingのbase_score寄与をどの程度弱めたか
- diversity bonus からroadを外したか
- 追加・更新したログ項目
- 追加・更新したテスト観点
- 実データ確認時に見るべきログ項目
- 残る注意点

## 禁止事項

- 確認コマンドやテストコマンドを実行しないでください
- コマンド実行結果を捏造しないでください
- `memo.md` は明示指示がない限り変更しないでください
````
