# 引き継ぎメモ

更新日: 2026-06-25

## 概要

- Django REST Framework を使った地図採点 API。
- `MapArea` を作成すると、中心座標・行数・列数・セルサイズから地図範囲を計算する。
- `initial_score_mode=manual` では作成リクエスト内で `GridCell` を即時生成する。
- `initial_score_mode=auto` では作成リクエスト内で `GridCell` を生成せず、`grid_generation_status=pending` で返す。生成待ちの MapArea は `process_pending_grid_areas` management command で後から処理する。
- demo 画面では、メモグリッド一覧、Map Preview、選択中セルの採点、共有相手管理を確認できる。
- Score Map は削除済み。現在のセル確認・選択・範囲選択は Map Preview に一本化している。
- `initial_score_mode=auto` では、Overpass / OSM 由来の地物情報を使って初期スコアを計算し、`GridCell.auto_score_breakdown` に自動採点理由を保存する。

## 作業前に読むファイル

- `AGENTS.md`
- `RULES.md`
- `TASK.md`
- `README.md`
- `API_SPEC.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/views.py`
- `maps/tests.py`
- `maps/test_osm_services.py`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`

## 現在の Git 状態

このメモ作成前に確認した時点では、作業ツリーはクリーンだった。

```bash
git status --short
git diff --name-only
git diff --stat
```

上記はいずれも出力なし。

この `memo.md` 更新後は、`memo.md` だけが未コミット差分になる想定。

## 直近の demo UI 状態

### Score Map

- demo 画面から Score Map セクションを削除済み。
- 削除したもの:
  - `Score Map` 見出し
  - 表示モード `全体表示` / `詳細表示`
  - Score Map 専用のグリッド描画
  - Score Map 上のクリック選択
  - Score Map 上のドラッグ範囲選択
  - Score Map 専用 CSS
- JS からも `scoreMap`, `renderScoreMap`, `highlightSelectedScoreCells` などの参照を削除済み。

### Map Preview

- GridCell の表示・選択は Map Preview に一本化。
- Map Preview 上の GridCell はクリックで選択できる。
- Shift + ドラッグで範囲内の GridCell をまとめて選択できる。
- Shift を押さないドラッグは、Leaflet の通常の地図移動として動く。
- Score Map 削除後も、Map Preview のスコア色分け・境界表示・選択ハイライトは維持している。

### 上部ヘッダー

- 以前 `GridCell` 見出しがあった場所には、選択中メモグリッドの Name を表示する。
- 未選択時は `メモグリッドを選択してください` と表示する。
- メモグリッド選択時は、`selectArea(areaId, areaName)` の `areaName` を `#selected-area-name` に表示する。
- 右側の再取得ボタン文言は `セルの再取得`。
- 追加した Name 表示は少し大きめに調整済み。
- 下の `共有相手管理` との間隔は、`#message:empty` の余白を小さくして詰めている。

### 選択中のマス

- `選択中のマス` パネルは維持。
- 自動採点理由は、直近クリックしたセルだけ折りたたみ表示できる。
- 「再採点すると点数が更新されます。」の右側に小さく表示するレイアウトへ調整済み。
- 主な理由は横並び、それ以外の数値項目は縦並び。

## 自動採点まわりの主な状態

### initial_score_mode

- `manual`:
  - Overpass helper は呼ばない。
  - `region_feature_level` を `initial_score` / `calculated_score` に入れる。
- `auto`:
  - MapArea 作成時点では GridCell を即時生成しない。
  - API レスポンス時点では `grid_generation_status=pending`、`grid_generation_attempt_count=0`。
  - 後続の `process_pending_grid_areas` management command が `run_grid_generation_for_area(area)` を呼び、Overpass / OSM feature summary から GridCell ごとの初期スコアを計算する。
  - OSM 取得や feature summary 作成が失敗した場合は、MapArea 自体は残し、コマンド処理時に fallback 生成を試す。
  - fallback では従来どおり `region_feature_level` を使い、成功時は `grid_generation_status=fallback_completed` にする。

### score breakdown

- `calculate_initial_score_breakdown_from_feature_summary()` の主要項目を GridCell に保存できる。
- `GridCell.auto_score_breakdown` を API レスポンスに含める。
- demo 画面では、直近選択セルの自動採点理由として表示する。
- 保存・表示する代表項目:
  - `base_score`
  - `diversity_bonus`
  - `context_bonus`
  - `penalty`
  - `raw_score`
  - `clamped_score`
  - 主な加点フラグ

## OSM / scoring の主な加点方針

細かい数値は `maps/services.py` を正とすること。

- station:
  - surface station / subway station / public transport station を別々の context bonus として扱う。
  - station density は単純 count ではなく、距離ベースの station cluster 判定に置き換え済み。
  - bus station / unknown station は採点対象外。
- expressway:
  - motorway / motorway_link と trunk / trunk_link は別々の context bonus。
  - large bounds expressway は採点対象外。
  - unknown expressway は採点対象外。
- landmark:
  - tourism / historic 系を取得・分類する。
  - landmark は context_bonus にだけ反映する。
  - landmark_context_bonus の上限は 1.0。
  - historic_castle は landmark 加点が強め。
- castle proximity:
  - historic_castle 周辺セルに near / mid / far の proximity bonus を加える。
  - castle 本体セルには proximity bonus を加えない。
- station proximity / park + waterfront / high-context:
  - context candidate summary の結果をもとに、弱い context bonus として反映済み。
  - station proximity 対象から subway_station は除外済み。
- water / forest:
  - coverage ratio は bounds overlap ratio ベース。
- base_score / diversity_bonus / penalty に入れない方針の要素が多いので、変更時は必ず `context_bonus` だけかどうか確認する。

## ログ

`maps/views.py` で Overpass auto 系ログを出している。

主に確認するログ:

- `Overpass auto feature summary`
- `Overpass auto score breakdown summary`
- `Overpass auto station summary`
- `Overpass auto station cluster summary`
- `Overpass auto expressway summary`
- `Overpass auto effective expressway summary`
- `Overpass auto landmark summary`
- `Overpass auto castle proximity summary`
- `Overpass auto context candidate summary`

注意:

- Overpass クエリ全文やレスポンス全文はログに出さない方針。
- 緯度経度の詳細範囲や GridCell ごとの詳細 summary も原則ログに出さない。

## 自動設定の負荷対策メモ（2026-06 追記）

自動設定作成時の負荷を調べるため、`[auto_grid_create]` 系ログを追加した。

主に次を分けて確認できる。

- Overpass 取得時間と取得件数。
- OSM element から map feature への分類件数。
- `feature_counts` の building / road / park / river / water / forest / railway / station / expressway / landmark / coastline 件数。
- GridCell ごとの feature_summary 作成時間と平均 ms。
- 自動スコア計算の `avg` / `min` / `max`。
- GridCell bulk create と全体の `total_sec`。
- building 集計の `building_count_total` / `building_cells` / `building_skipped_missing_position` / `building_center_fallback_count`。

目的は、どの処理が重いかを見える化し、今後の制限緩和や非同期化を検討しやすくすること。

### road 取得除外

通常 road は現在の自動初期スコアに寄与しないため、Overpass クエリから広い `nwr["highway"]` 取得を除外した。

一方で、expressway は景観・文脈要素として使っているため、以下は取得対象として残している。

- `motorway`
- `motorway_link`
- `trunk`
- `trunk_link`

検証時の一例:

```text
road除外前:
features=7500
road=4437
feature_summary=0.983秒
total=18.978秒

road除外後:
features=約3200
road=0
feature_summary=約0.4秒
total=約9〜17秒程度
```

Overpass 取得時間は外部 API の混雑でも変わるため、常に短縮されるとは限らない。

### building 取得と軽量化

road 除外後は building が最も多い地物になった。
building を完全除外すると取得件数は減るが、スコア傾向が大きく崩れたため、通常運用では採用しない方針。

検証時の一例:

```text
buildingあり:
auto_score avg=約1.73
max=3.00

buildingなし:
auto_score avg=約0.33
max=約1.14
```

そのため、building は取得しつつ、扱い方を `geometry` / `center` で比較できるようにした。

- `geometry`: 従来に近く、bounds / geometry 由来の範囲で GridCell との関係を見る。
- `center`: building の中心点を使って `building_count` に反映する。

実装上、building の自動スコア寄与は主に `building_count` ベースで行われている。
現在のデフォルトは `center` mode。
検証時には、center mode でもスコア傾向はかなり維持できた。

検証時の一例:

```text
geometry:
feature_summary=約0.43秒
auto_score avg=約1.73
max=3.00

center:
feature_summary=約0.32秒
auto_score avg=約1.68
max=3.00
```

`AUTO_SCORE_SKIP_BUILDINGS_WHEN_LARGE` は比較用フラグとして残しているが、デフォルトでは無効。
building 完全除外や広範囲除外を通常運用にする予定は、現時点ではない。

### 不完全 building feature の安全化

OSM / Overpass 由来の building には、bounds や center が欠けるケースがある。
以前は不完全な building feature が混ざると、feature_summary 作成中に `bounds は辞書で指定してください。` で失敗し、自動設定全体が fallback に落ちることがあった。

現在は building に限り、次のように扱う。

- bounds があれば bounds 判定に使う。
- bounds がなく center があれば center 判定に使う。
- bounds も center もなければ、その building feature だけスキップする。

building 以外の park / water / river / forest などは範囲や重なりが重要なため、不正 bounds の扱いは従来どおりエラー寄りにしている。

### Overpass 分割取得の検証

初回処理そのものの安定化を調べるため、Overpass 取得を 2×2 に分割する試験実装を追加した。

実装上の整理:

- `AUTO_SCORE_SPLIT_OVERPASS_FETCH` で通常取得 / 分割取得を切り替える。
- デフォルトは `False` で、通常運用では従来どおり MapArea 全体を 1 回で取得する。
- 分割取得時は MapArea 全体の bounds を 2×2 に分け、それぞれ Overpass に問い合わせる。
- 境界付近や大きな地物は重複する可能性があるため、`source_type + source_id` で重複除去する。
- 1 区画でも失敗した場合は、欠落した地物で自動採点しないように全体失敗扱いにし、既存の fallback に流す。

実測では、分割取得 ON 時に Overpass API から `429` が返り、fallback に落ちるケースがあった。

```text
split_enabled=False:
features=3073
overpass_fetch=約6.9秒
total=約7.4秒

split_enabled=True:
status_code=429
overpass_fetch_failed=約31.8秒
fallback
```

このため、現時点では Overpass 分割取得は本採用しない。
`AUTO_SCORE_SPLIT_OVERPASS_FETCH=False` のまま、比較用機能として残す。

次の候補は、リクエスト回数を増やす方向ではなく、Overpass の出力形式や取得対象をさらに見直すこと。
ただし、road 除外を戻す、expressway 取得を削る、building mode やスコア重みを変える、といった変更は別タスクとして慎重に扱う。

### Overpass 軽量出力の検証

リクエスト回数を増やさずに 1 回の Overpass レスポンスを軽くできるかを調べるため、出力形式の軽量化を試験実装した。

実装上の整理:

- `AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT` を追加した。
- デフォルトは `False` で、通常運用では既存に近い出力形式を使う。
- 軽量出力 ON 時は、`station` / `landmark` を `out body center;` 側へ分離する。
- `park` / `water` / `river` / `forest` / `coastline` は coverage や重なりがスコアに影響するため `geom` を維持する。
- `railway` / `expressway` は線形地物で center 化するとセルとの関係が不自然になる可能性があるため、今回は `geom` を維持する。
- building は既存の `AUTO_SCORE_BUILDING_MODE_CENTER` を維持する。

実測では、軽量出力 ON / OFF で feature_counts は一致し、auto_score avg もほぼ同じだった。
一方で、処理時間は Overpass 側の混雑や応答時間のブレが大きく、安定した高速化とは判断しない。

検証時の一例:

```text
lightweight=True
t1: total_sec=16.256 / overpass_fetch=15.795 / auto_score avg=2.09
t2: total_sec=8.770 / overpass_fetch=8.309 / auto_score avg=2.09

lightweight=False
f1: total_sec=11.537 / overpass_fetch=11.083 / auto_score avg=2.10
f2: total_sec=10.011 / overpass_fetch=9.555 / auto_score avg=2.10
```

平均すると、`lightweight=True` の total_sec は約 12.51 秒、`lightweight=False` の total_sec は約 10.77 秒だった。
今回の追加計測では、軽量出力 ON の方が安定して速いとは言えない。
ただし、feature_counts とスコア傾向は維持できている。

このため、現時点では Overpass 軽量出力は本採用しない。
`AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT=False` のまま、比較用機能として残す。

分割取得は 429 に当たりやすいためデフォルト無効、軽量出力は速度改善が安定して確認できていないためデフォルト無効、という扱いで分けて考える。
次の候補は、非同期化設計、または取得対象・出力形式のさらなる調査。

### 自動設定作成の非同期化試験実装

目的:

- `initial_score_mode=auto` の作成時に、Overpass 取得と feature summary 作成でリクエストが長時間待たされる問題を分離する。
- MapArea 作成自体は早く返し、GridCell 生成の進行状況を API と画面で扱えるようにする。
- いきなり Celery / RQ / Redis を導入せず、初心者が追いやすい段階に分ける。

現在の作成フロー:

- `/maps/new/` の画面 JS は `POST /api/maps/areas/` を呼び、成功後に `/maps/<area_id>/` へ移動する。
- `MapAreaSerializer.validate()` が中心座標、行数、列数、1マスの大きさから `north/south/east/west` と `center_grid_options` を作る。
- 作成入力の `rows` / `cols` は、MapArea の `map_grid_rows` / `map_grid_cols` に保存する。
- 以前は GridCell をすぐ生成していたため、`rows` / `cols` が serializer の `write_only` 入力でも問題が見えにくかった。
- auto pending 化後は、後続の `process_pending_grid_areas` で作成時の行数・列数が必要になるため、MapArea 側に保存する。
- `initial_score_mode=manual` の場合:
  - `MapAreaListCreateView.post()` が MapArea を保存する。
  - 同じリクエスト内で `run_grid_generation_for_area(area)` を呼ぶ。
  - `run_grid_generation_for_area()` は `running` に更新してから GridCell を生成する。
  - 成功時は `grid_generation_status=completed`、`grid_generation_attempt_count=1` になってから `201 Created` を返す。
  - レスポンス後すぐに `GET /api/maps/areas/<area_id>/grids/` で GridCell を取得できる。
- `initial_score_mode=auto` の場合:
  - `MapAreaListCreateView.post()` が MapArea を保存する。
  - 作成リクエスト内では GridCell を生成しない。
  - `grid_generation_status=pending`、開始/完了時刻は `null`、error message は空文字、attempt count は `0` で `201 Created` を返す。
  - auto 作成直後は GridCell が存在しないため、GridCell 一覧 API は空になる場合がある。
  - 後から `python manage.py process_pending_grid_areas` を実行し、pending の MapArea を生成処理する。
  - コマンド処理では `run_grid_generation_for_area(area)` が呼ばれ、成功時は `completed`、Overpass 失敗から fallback 生成できた場合は `fallback_completed`、GridCell 生成自体が失敗した場合は `failed` になる。

状態管理:

- field 名は `auto_score_status` ではなく `grid_generation_status` を採用済み。
- 理由は、待っている対象が「自動採点」だけでなく、詳細画面表示に必要な GridCell 作成全体だから。
- 手動設定でも GridCell 作成は必要なので、共通状態として扱う。

MapArea の状態管理 field:

- `map_grid_rows`
- `map_grid_cols`
- `grid_generation_status`
- `grid_generation_started_at`
- `grid_generation_finished_at`
- `grid_generation_error_message`
- `grid_generation_attempt_count`

補足:

- `map_grid_rows` / `map_grid_cols` は作成時に指定された行数・列数。GridCell 生成前でも API レスポンスに返す。
- `rows` / `cols` は作成入力専用で、API レスポンスでは `map_grid_rows` / `map_grid_cols` を使う。
- `grid_generation_status` は API レスポンスにも read-only で返す。
- `grid_generation_started_at` / `grid_generation_finished_at` は生成開始・完了時刻。
- `grid_generation_error_message` は fallback / failed 時の短い内部エラー。ユーザーに長い外部 API レスポンス全文を見せる用途ではない。
- `grid_generation_attempt_count` は生成処理の試行回数。

status 値:

- `pending`: MapArea は保存済みだが、GridCell 生成はまだ始まっていない。
- `running`: GridCell 生成中。auto では Overpass 取得や feature summary 作成もここに含む。
- `completed`: 期待どおり GridCell 生成が完了した。
- `fallback_completed`: auto 作成は失敗したが、手動設定相当の fallback で GridCell 生成は完了した。
- `failed`: fallback も含めて GridCell を作れなかった。詳細画面で採点できない状態。

`not_required` は初期実装では使わない方がよい。
このアプリでは MapArea の通常利用に GridCell が必要なので、「GridCell 生成が不要」という状態が今の仕様にほぼ存在しないため。
既存データや手動設定は `completed` に寄せる方が、画面側の分岐が少ない。

既存データへの移行方針:

- migration の default は `completed` が安全。
- 既存 MapArea の多くは、現在の同期処理で GridCell 作成済みの前提だから。
- GridCell が 0 件の既存 MapArea を厳密に洗い出す処理は、別タスクの data migration または管理コマンドで検討する。

API レスポンスの設計:

- `MapAreaSerializer` / `MapAreaListSerializer` / detail API に `grid_generation_status` を read-only で含める。
- `map_grid_rows` / `map_grid_cols` も read-only で返し、pending 中でも作成時の行数・列数を確認できるようにする。
- 現在の `GET /api/maps/areas/<area_id>/grids/` は、MapArea に GridCell がまだ無い場合も `200 OK` で `grids: []` を返す。
- pending / running の状態自体は MapArea 一覧 API / 詳細 API で確認する。
- `grid_generation_error_message` はユーザーに見せてもよい短い文にし、Overpass の詳細レスポンスや内部例外全文はログ側に残す。

画面設計:

- 一覧画面:
  - GridCell 生成状態バッジを表示する。
  - `map_grid_rows` / `map_grid_cols` を使い、pending 中でもマス数を表示する。
  - `pending` / `running` / `completed` / `fallback_completed` / `failed` を区別する。
  - `pending` / `running` / `fallback_completed` / `failed` は短い補足文も表示する。
- 詳細画面:
  - `pending` / `running` / `failed` では基本情報と状態メッセージ、再読み込みリンクを表示する。
  - `pending` / `running` / `failed` では GridCell 地図、採点フォーム、一括採点 UI、共有/削除 UI、詳細画面 JS を表示しない。
  - `fallback_completed` では地図と採点を使えるようにしつつ、自動設定ではなく fallback で作られたことを表示する。
  - `completed` は通常表示する。

management command:

```bash
python manage.py process_pending_grid_areas
python manage.py process_pending_grid_areas --dry-run
python manage.py process_pending_grid_areas --limit 1
```

- これは HTTP API ではなく、Django の運用・開発用 management command。
- `pending` の MapArea を `created_at`, `id` 順に取得する。
- 対象ごとに `run_grid_generation_for_area(area)` を呼ぶ。
- GridCell 生成時は MapArea に保存済みの `map_grid_rows` / `map_grid_cols` を使う。
- 1件失敗しても残りの pending MapArea 処理を続行する。
- `--dry-run` は対象表示のみで生成処理は行わない。
- `--limit` は処理件数を制限する。
- 現状は手動実行、または将来のスケジューラ実行を想定している。

process_pending_grid_areas の運用方針:

- 現段階の基本方針:
  - 完全な非同期ジョブキューではなく、management command を使った「試験的な遅延実行」として扱う。
  - auto 作成 API は `pending` の MapArea を返し、GridCell 生成は `process_pending_grid_areas` に分離する。
  - Python コード、model、migration、serializer、view、画面 JS はこの方針整理では変更しない。
- ローカル開発:
  - `.venv` の Python で実行する。
  - まず `--dry-run` で対象件数を確認する。
  - 実処理は `--limit 1` から始め、Overpass への負荷と失敗時の挙動を確認する。
  - コマンド例:

```bash
.venv/bin/python manage.py process_pending_grid_areas --dry-run
.venv/bin/python manage.py process_pending_grid_areas --limit 1
```

- Render での短期運用:
  - まずは手動実行を基本にする。
  - デモ前や検証前に `pending` が残っていないか確認し、必要な分だけ処理する。
  - 手動実行できる環境がある場合も、最初は `--dry-run` と `--limit 1` を使う。
  - この方法では、ユーザーが auto 作成した直後に自動で完了するわけではない点に注意する。
- Render Cron Job を使う案:
  - Render 側で Cron Job が利用できる場合、低頻度で `python manage.py process_pending_grid_areas --limit 1` を実行する案がある。
  - Cron は「決めた間隔でコマンドを実行する仕組み」。Celery / RQ / Redis を入れずに、疑似的な非同期処理にできる。
  - 間隔が長すぎると `pending` の待ち時間が長くなり、短すぎると Overpass やDBへの負荷が増える。
  - まずは低頻度、少件数から始める。件数を増やす場合も `--limit 3` 程度までを検討し、実測してから判断する。
  - Render のプラン、料金、Cron Job の利用可否は別途確認が必要。このメモでは設定を追加しない。
- 外部 cron + HTTP endpoint 案:
  - 現在の `process_pending_grid_areas` は HTTP API ではないため、外部 cron から直接は呼べない。
  - 外部 cron で実行するには、認証付きの管理用 endpoint を新しく作る必要がある。
  - 管理用 endpoint は不正実行や連打への対策が必要になるため、現段階では採用しない。
- background thread 案:
  - Web リクエスト内で background thread を起動して処理する案は、本番運用では避ける。
  - 理由は、デプロイや再起動で処理が失われやすく、複数プロセス時の重複実行やエラー追跡が難しいため。
- Celery / RQ / Redis 案:
  - 将来、利用量が増えたら検討する本格案。
  - Celery / RQ は「重い処理を別 worker に渡すジョブキュー」、Redis はその待ち行列や状態管理に使うことが多い。
  - 利点は、MapArea 作成直後にジョブ登録できること、再試行や失敗状態を扱いやすいこと。
  - 欠点は、追加サービス、Render 側の運用設定、料金、学習コストが増えること。
- 推奨:
  - 現段階は management command 方式を継続する。
  - ローカルとデモでは手動実行を使う。
  - Render では、まず手動実行で確認し、Cron Job が利用できるなら低頻度かつ `--limit 1` で試す。
  - 本格運用やユーザー数増加が見えてから、Celery / RQ / Redis を再検討する。

## process_pending_grid_areas のRender Cron Job運用方針

目的:

- 公開アプリでは、auto 作成後の `pending` MapArea を手動実行だけに依存すると、GridCell 生成が進まない。
- ただし、Web リクエスト内で Overpass 取得を戻すとタイムアウトしやすくなる。
- そのため、短期運用では Render Cron Job で management command を定期実行する案を第一候補にする。

推奨する初期コマンド:

```bash
python manage.py process_pending_grid_areas --limit 1
```

- `--limit 1` は1回の実行で処理する MapArea を1件に制限する。
- pending が0件なら、対象なしとして終了する。
- limitなしの実行は、Overpass API への連続アクセスが増えるため現段階では使わない。

実行頻度候補:

| 頻度 | 利点 | 注意点 | 初期判断 |
| --- | --- | --- | --- |
| 5分ごと | 待ち時間が短い | Overpass へのアクセス頻度が増える | 最初は少し攻めた設定 |
| 10分ごと | 待ち時間と負荷のバランスがよい | 利用が増えると pending が溜まる可能性 | 初期候補 |
| 15分ごと | Overpass 負荷を抑えやすい | 完了まで少し待つ | 初期候補 |
| 30分ごと | かなり安全寄り | ユーザーの待ち時間が長い | 低頻度デモ向け |

推奨:

- 初期運用は 10〜15分に1回、`--limit 1`。
- ポートフォリオ用途で利用頻度が低いうちは、まずこの設定で様子を見る。
- pending が溜まるようになってから、頻度や `--limit` を見直す。

limit 値候補:

| limit | 利点 | 注意点 | 初期判断 |
| --- | --- | --- | --- |
| `--limit 1` | 最も安全。連続した Overpass 取得を避けやすい | pending 解消は遅い | 推奨 |
| `--limit 2`〜`--limit 3` | pending を少し早く消化できる | Overpass 失敗率や負荷が上がる可能性 | 様子を見てから |
| limitなし | pending を一気に処理できる | Overpass への負荷が大きい | 非推奨 |

Render 設定時に確認すること:

- Cron Job は既存 Web Service とは別の定期実行サービスとして作る想定。
- command は `python manage.py process_pending_grid_areas --limit 1` を候補にする。
- 既存 Web Service と同じ本番 DB を参照できるように、`DATABASE_URL` など必要な環境変数をそろえる。
- `DJANGO_SECRET_KEY`、`DJANGO_DEBUG`、`DJANGO_ALLOWED_HOSTS` など、Django 起動に必要な環境変数も確認する。
- 実際の Render 画面操作、`render.yaml` 追加、料金・プラン条件の確認は今回行わない。
- Render の Cron Job 利用可否や料金は変わる可能性があるため、実設定前に最新情報を確認する。

migration との関係:

- Cron Job は本番 DB の `MapArea` と `GridCell` を直接読む。
- Cron Job を動かす前に、本番 DB へ migration が適用済みである必要がある。
- 特に `map_grid_rows` / `map_grid_cols` など、pending 後の GridCell 生成に必要な列が本番 DB に存在している必要がある。
- migration 未適用の状態で Cron Job を動かすと、DB列不足でエラーになる可能性がある。

Overpass API への配慮:

- auto 作成の後処理では Overpass API を使う。
- Overpass API は混雑時に 504 / 429 などで失敗することがある。
- 失敗しても fallback 生成できた場合は `fallback_completed` になり、標準値で GridCell は使える。
- 短い間隔や limitなしで大量処理すると、失敗率や外部 API 負荷が上がる可能性がある。
- 初期運用は低頻度・少件数にし、ログと `grid_generation_status` を見て調整する。

pending が溜まった場合:

- `--limit 1` では、作成数が増えると pending が溜まる可能性がある。
- まずは手動で `python manage.py process_pending_grid_areas --limit 3` を一時実行して解消する案を検討する。
- 継続的に溜まる場合は、Cron 頻度を上げる、`--limit 2`〜`--limit 3` を試す、または Celery / RQ / Redis を検討する。
- limitなしで一気に処理する運用は、Overpass への負荷が読みにくいため避ける。

`failed` / `fallback_completed` の扱い:

- 現在の command は `grid_generation_status=pending` の MapArea だけを処理する。
- `completed` は処理対象外。
- `fallback_completed` は処理対象外。
- `failed` は処理対象外。
- Cron Job では自動再試行を行わない。
- failed 再処理や fallback からの再採点は、既存 GridCell やユーザー採点をどう扱うかが関わるため別タスクで設計する。

background thread を採用しない理由:

- Web リクエスト内で重い処理を走らせると、Web 応答がタイムアウトしやすい。
- background thread は、Render の再起動や複数プロセス構成で処理完了を保証しづらい。
- 処理が途中で消えた場合の追跡や再実行が難しい。
- ログや失敗状態を command / Cron Job に寄せた方が、初心者にも運用を追いやすい。

Celery / RQ / Redis との比較:

- Celery / RQ / Redis は、本格的な非同期ジョブキューとしては有力。
- MapArea 作成直後にジョブ投入でき、retry や worker 管理もしやすい。
- ただし Redis などの追加サービス、Render 側の構成、料金、学習コストが増える。
- 現段階のポートフォリオ用途では、まず Render Cron Job + management command の方が小さく始めやすい。
- 利用者が増え、pending 消化や再試行が重要になった段階で Celery / RQ / Redis を再検討する。

## Render上でのprocess_pending_grid_areas単発実行確認

目的:

- Render Cron Job 化の前に、Render 本番環境で `process_pending_grid_areas` が単発実行できるか確認する。
- command が本番 DB に接続できること、migration 適用済みであること、Overpass 後処理が本番環境で動くことを切り分けて確認する。
- いきなり Cron Job を作らず、まず手動の `dry-run` と `--limit 1` で安全に確認する。

実行前提:

- 最新コードが GitHub に push 済みである。
- Render の最新デプロイが成功している。
- 本番 DB に migration が適用済みである。
- Render 上の単発実行環境が、Web Service と同じ `DATABASE_URL` などの環境変数を参照できる。
- Render Shell、Manual Job / One-Off Job 相当の機能、または Render 管理画面からの単発コマンド実行手段が使える。

本番 DB migration 確認:

```bash
python manage.py showmigrations maps
```

- `map_grid_rows` / `map_grid_cols` を追加する migration が本番 DB に適用済みか確認する。
- migration 未適用のまま command を実行すると、DB カラム不足で失敗する可能性がある。
- 必要な場合のみ、慎重に以下を実行する。

```bash
python manage.py migrate
```

注意:

- 本番 DB への `migrate` はデータ構造を変える操作なので、実行前にローカルや検証環境で成功確認しておく。
- 今回は Render 上での実行手順を整理するだけで、こちらでは本番 DB に対する操作は行わない。

実行前の画面確認:

1. 本番 URL で `initial_score_mode=auto` の MapArea を1件作成する。
2. 作成直後の一覧で `pending` / `作成待ち` 表示になることを確認する。
3. pending 中でも `9×9` などの行数・列数が表示されることを確認する。
4. 詳細画面で作成待ち/作成中表示になり、GridCell 地図や採点 UI がまだ表示されないことを確認する。

最初に実行する command:

```bash
python manage.py process_pending_grid_areas --dry-run
```

確認すること:

- command 自体が起動できる。
- 本番 DB に接続できる。
- pending MapArea の件数が表示される。
- `Dry run: no changes will be made.` が表示され、DB 更新が行われない。
- `no such column: maps_maparea.map_grid_rows` などの migration 未適用エラーが出ない。

dry-run で問題がない場合に1件だけ処理:

```bash
python manage.py process_pending_grid_areas --limit 1
```

確認すること:

- `Processing MapArea id=...` が表示される。
- `Completed MapArea id=... status=... cells=...` が表示される。
- 最後に `Done. processed=1 ...` の summary が表示される。
- command 全体が例外で落ちず、1件処理で止まる。

実行後の画面確認:

1. 本番 URL の一覧を再読み込みする。
2. 状態バッジが `completed` / `fallback_completed` / `failed` のいずれかに変わることを確認する。
3. `completed` の場合、詳細画面に地図、GridCell、採点 UI が表示されることを確認する。
4. `fallback_completed` の場合、標準値で作成した注意表示が出ることを確認する。
5. `failed` の場合、失敗メッセージが出ることを確認する。
6. `9×9` で作成した場合、pending 中も生成後も `9×9` 表記が維持され、生成後の GridCell 数が 81 件になることを確認する。

Django shell での補助確認:

```bash
python manage.py shell
```

```python
from django.db.models import Min, Max
from maps.models import MapArea

area = MapArea.objects.order_by("-id").first()

print(area.id)
print(area.name)
print(area.initial_score_mode)
print(area.grid_generation_status)
print(area.map_grid_rows, area.map_grid_cols)
print(area.grid_cells.count())
print(area.grid_cells.aggregate(
    min_row=Min("row_index"),
    max_row=Max("row_index"),
    min_col=Min("col_index"),
    max_col=Max("col_index"),
))
```

期待例:

```text
pending中:
grid_generation_status=pending
map_grid_rows=9
map_grid_cols=9
grid_cells.count()=0

生成後:
grid_generation_status=completed または fallback_completed
map_grid_rows=9
map_grid_cols=9
grid_cells.count()=81
row_index: 0〜8
col_index: 0〜8
```

失敗時に見るポイント:

- migration 未適用:
  - `no such column: maps_maparea.map_grid_rows`
  - `no such column: maps_maparea.map_grid_cols`
  - 対応: `python manage.py showmigrations maps` で確認し、必要なら `python manage.py migrate` を検討する。
- 環境変数不足:
  - `DATABASE_URL` が参照できない。
  - `DJANGO_SECRET_KEY` や `DJANGO_SETTINGS_MODULE` 周辺で起動に失敗する。
  - 対応: 単発実行環境が Web Service と同じ環境変数を参照できているか確認する。
- Overpass API 失敗:
  - `status_code=504`
  - `status_code=429`
  - 対応: `fallback_completed` なら仕様どおり。`failed` なら Render ログと `grid_generation_error_message` を確認する。大量処理せず `--limit 1` を維持する。

この確認でやらないこと:

- Render Cron Job はまだ作成しない。
- `render.yaml` は追加・変更しない。
- HTTP endpoint、自動ポーリング、background thread は追加しない。
- `failed` / `fallback_completed` の自動再処理は行わない。

## 管理者限定pending処理画面

目的:

- Render無料環境で Shell や Cron Job が使いにくい場合の代替手段として用意する。
- staffユーザーが画面上のボタンから、古い pending MapArea を1件だけ処理できるようにする。
- 一般ユーザーには処理ボタンを出さず、URLを直接開いても実行できないようにする。

仕様:

- URL は `/maps/admin/pending-grid-jobs/`。
- staffユーザーのみアクセス可能。
- 一覧画面には staffユーザーだけ `pending処理管理` リンクを表示する。
- GET では pending 件数と、次に処理される MapArea の情報だけを表示する。
- POST では `grid_generation_status=pending` の MapArea を `created_at`, `id` 順に1件だけ取得する。
- 取得した MapArea に対して `run_grid_generation_for_area(area)` を呼び出す。
- 処理後は同じ画面へ redirect し、Django messages で結果を表示する。
- `failed` / `fallback_completed` / `completed` は処理対象にしない。

注意:

- この画面はHTTPリクエスト中に Overpass API を使う可能性があるため、10〜20秒程度かかる場合がある。
- 短時間に連続して実行しない。
- 1回のPOSTで処理するのは1件だけ。
- 本格運用では Render Cron Job や Celery / RQ / Redis に置き換える可能性がある。

現時点で未実装のこと:

- Celery / RQ / Redis は未導入。
- 自動で management command を起動する仕組みは未実装。
- 自動ポーリングは未実装。
- 本番スケジューラ設定は未実装。
- Render Cron Job 設定や `render.yaml` の追加は未実装。
- 再試行ボタンは未実装。
- 現状は完全な非同期ジョブキューではなく、management command を使った試験的な遅延実行。

注意点:

- auto 作成直後は GridCell が存在しない。
- pending のままでは詳細画面に地図は出ない。
- GridCell 生成には management command の実行が必要。
- `fallback_completed` は「自動設定に成功した」状態ではないが、GridCell は生成済みなので採点は可能。

fallback 方針:

- 現在は `fallback_completed` を採用している。
- 理由は、Overpass が混雑していてもユーザーはメモグリッド自体を使い始められるため。
- ただし、fallback は「自動設定に成功した」とは扱わない。状態と画面表示で区別する。
- fallback 生成に失敗した場合だけ `failed` にする。

再試行の扱い:

- 初期実装では自動再試行ボタンや再試行 API は作らない。
- `grid_generation_attempt_count` は将来の再試行に備えて持っておく。
- 再試行を入れる場合は、既存 GridCell がある `fallback_completed` を消して作り直すのか、別 MapArea として作るのかを先に決める必要がある。
- ユーザー採点済み GridCell を消す可能性があるため、再生成は削除と同じくらい慎重に扱う。

段階的な実装状況:

1. `MapArea` に `grid_generation_status` などの状態 field を追加済み。
2. serializer / list / detail API に状態 field を read-only で追加済み。
3. GridCell 生成処理を `run_grid_generation_for_area(area)` に切り出し済み。
4. manual 作成では同期のまま新 service を呼び、状態を記録済み。
5. pending MapArea を処理する management command を追加済み。
6. auto 作成時だけ `pending` で返し、management command が後から生成する流れに切り替え済み。
7. 一覧画面と詳細画面に `pending` / `running` / `fallback_completed` / `failed` 表示を追加済み。
8. Celery / RQ / Redis は未導入。必要性と運用方法が固まってから検討する。

方式比較:

- A: service 切り出しだけの疑似非同期
  - 既存動作を保ったまま整理できる。
  - 状態遷移のテストを書きやすい。
  - ただし、リクエスト待ち時間そのものはまだ短くならない。
- B: management command で pending を処理
  - Celery なしで非同期に近い運用ができる。
  - Render などでは別プロセスや手動実行の設計が必要。
  - 初心者が処理の入口を追いやすい。
- C: Celery / RQ
  - 本格的な job queue と retry が扱える。
  - Redis などの追加依存と運用が必要。
  - 現段階では導入コストが大きい。

今後の検討:

- A の service 切り出しと状態 field は実装済み。
- B の management command による pending 処理も試験実装済み。
- C の Celery / RQ は、非同期処理の必要性と運用方法が固まってから検討する。
- 次に本格運用する場合は、スケジューラ設定、失敗時の再試行、再生成時の既存 GridCell / 採点データの扱いを先に決める。

### 現時点の方針

採用済み・採用候補:

- 通常 road 取得除外。
- expressway 取得維持。
- 不完全 building feature の安全化。
- building center mode は本採用候補として検証中。現在のデフォルトは center。

保留:

- building 完全除外。
- building 広範囲除外のデフォルト有効化。
- Overpass 取得分割。
- Overpass 軽量出力の本採用。
- 2km 制限解除。
- キャッシュ。
- Celery / RQ / Redis による本格的な非同期ジョブキュー。

現在は自動設定の安定性を優先して、画面側で広範囲作成を制限している。
road 取得除外や building 処理の軽量化は、将来的に制限緩和できるかを検証するための負荷対策であり、現時点で 2km 制限を解除したわけではない。
非同期化については、management command を使った試験的な遅延実行まで実装済みで、完全なジョブキュー化は未実装。

## テスト状況

直近で実行済み:

```bash
.venv/bin/python manage.py test maps.tests
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
```

確認結果:

```text
maps.tests: 237 tests OK
MapDemoViewTests: 2 tests OK
System check identified no issues
```

Score Map 削除後、demo 表示テストは以下を確認するよう更新済み。

- `Score Map` が表示されない。
- Score Map 関連 DOM ID / class が出ない。
- `セルの再取得` が表示される。
- `selected-area-name` が表示される。
- `selected-area-label` / `grids-heading` は表示されない。
- Map Preview と選択中のマス UI は表示される。

## 注意点

- `TASK.md` は古い task 内容のまま残っている可能性がある。次の作業開始時は、ユーザーの最新依頼を優先しつつ `TASK.md` の内容が現在の作業に合っているか確認すること。
- `memo.md` は今回ユーザー依頼で更新している。通常の実装 task では、ユーザーが明示しない限り `memo.md` を触らない方針だった。
- `.venv` を使ってテストする。グローバル Python 環境には依存しない。
- DB / model / migration を変更する場合は、影響と migration の意味を初心者向けに説明する。

## 次にやるとよいこと

- demo 画面をブラウザで開き、上部のメモグリッド名、`セルの再取得` ボタン、共有相手管理との余白を目視確認する。
- UI 変更をさらに進める場合は、Map Preview と `選択中のマス` パネルの役割が重複していないかを見直す。
- scoring を変更する場合は、`maps/services.py` の breakdown と `maps/test_osm_services.py` の期待値をセットで更新する。
- demo 表示を変更する場合は、`maps.tests.MapDemoViewTests` を最低限実行する。

## 本サイト移行の現在地（2026-06-09 追記）

demo 画面で確認していた主要機能は、本サイト側の画面へかなり移行済み。
現在は demo を直接使う段階から、`/maps/`、`/maps/new/`、`/maps/<area_id>/` に分けた本サイト用 UI で確認する段階に近づいている。

### demo から本サイトへ移行済みの主な機能

- メモグリッド一覧表示。
- メモグリッド作成。
- メモグリッド詳細表示。
- 地図プレビュー上での GridCell 確認。
- Leaflet Map Preview。
- MapArea 全体枠表示。
- GridCell 境界表示。
- GridCell のスコア色分け。
- GridCell のスコアラベル表示。
- マスの単体選択、複数選択、Shift + ドラッグ範囲選択。
- 単体採点。
- 同一値一括採点。
- 採点後の GridCell 再取得と地図色更新。
- 自動採点理由表示。
- 共有相手管理。
- メモグリッド削除。
- 手動再取得。
- 画面全体ローディングオーバーレイ。

### 現在の本サイト画面構成

- `/maps/`
  - ログイン必須のメモグリッド一覧画面。
  - 自分のメモグリッドと共有されたメモグリッドを表示する。
  - 詳細画面へのリンクを表示する。
  - 新しいメモグリッド作成画面へのリンクを表示する。
  - 自分のメモグリッドは一覧から削除できる。
- `/maps/new/`
  - ログイン必須のメモグリッド作成画面。
  - name、description、center_lat、center_lng、rows、cols、grid_size_meters、initial_score_mode / region_feature_level を入力できる。
  - 作成処理は本サイト用 JS から Session 認証 + CSRF で `POST /api/maps/areas/` を呼ぶ。
  - 作成成功後は作成したメモグリッドの詳細画面へ移動する。
  - 作成処理中は共通ローディングオーバーレイを表示する。
  - 入力値に連動する Leaflet Map Preview を表示する。
  - PC 幅ではフォームと Map Preview を 2 カラムで表示する。
- `/maps/<area_id>/`
  - ログイン必須のメモグリッド詳細画面。
  - 地図プレビュー、選択中マス詳細、採点フォーム、共有相手管理、削除を扱う。
  - 本サイト側 JS は Session 認証前提で、Basic 認証欄は使わない。

### 本サイト画面改善の進捗

- ログイン画面
  - `/maps/` 系画面と近いカード風デザインに整理済み。
  - `ユーザー名`、`パスワード` の日本語ラベルに変更済み。
  - ログイン失敗時の表示を `.message` 系の見た目に寄せている。
- `/maps/`
  - 0 件時に `/maps/new/` への導線を表示する。
  - 一覧取得失敗時に再読み込みボタンを表示し、既存の一覧取得処理を再実行できる。
  - 一覧カードのメタ情報に `マスの数` を追加済み。`1マスの大きさ` の次に `マスの数: 縦 10 × 横 10` 形式で表示する。
  - 一覧 API レスポンスに `map_grid_rows` / `map_grid_cols` を追加済み。現在は MapArea に保存した作成時の行数・列数を返すため、pending 中で GridCell がなくても表示できる。
  - 一覧 API レスポンス変更に合わせて `API_SPEC.md` も更新済み。
  - 通常メモグリッドカードは青系の枠線で表示する。
  - 共有メモグリッドカードは緑系の枠線、薄い緑背景、緑系バッジで表示する。
  - 一覧カードの削除導線を詳細リンクから分離し、危険操作として見えるように調整済み。
  - 一覧カード下部の削除欄は、`gap`、`margin-top`、`padding`、左線幅、削除欄内の削除ボタンサイズを調整してコンパクト化済み。
  - 警告文は `削除すると元に戻せません。` を維持し、赤系背景、枠・左線、赤い削除ボタンも残して危険操作の見た目を保っている。
  - 削除 API、確認ダイアログ、削除ボタン表示条件は変更していない。
- `/maps/new/`
  - 作成フォームと Map Preview を並べる 2 カラム構成に調整済み。
  - 中心緯度、中心経度、行数、列数、1マスの大きさから作成予定範囲を概算表示する。
  - マス数が多い場合は境界表示を省略し、重くなりすぎないようにしている。
- `/maps/<area_id>/`
  - 地図、一覧、選択状態、採点、管理の役割が分かるようにセクション導線を整理済み。
  - 説明文は提出前に読みやすい長さへ短縮済み。
  - 共有と削除は管理セクションにまとめている。
- 共通スタイル
  - `site.css` にボタン、メッセージ、フォーム、ローディング、セクション見出しなどの共通スタイルを整理済み。
  - 表示文言は本サイト向けに日本語化済み。
  - `Map Preview` は `地図プレビュー`、`score` は `スコア`、`comment` は `コメント`、`username` は画面上では `ユーザー名` / `共有相手のユーザー名` と表示する。
  - form の `name`、`id`、data 属性、API 送信用キーは既存機能を壊さないため英語名のまま維持している。

### 詳細画面で実装済みの機能

- 基本情報
  - ブラウザタイトルは `<メモグリッド名> | Grid Journey` 形式。
  - 画面上の `h1` はメモグリッド名。
  - `メモグリッド詳細` は見出し下の補助テキストとして表示する。
  - 概要セクション見出しは `基本情報`。
  - 説明文は常時表示する。
  - `種別`、`作成者`、`1マスの大きさ`、`マスの数`、`初期スコア設定`、`地域特徴レベル`、`作成日時` は `詳細情報` の折りたたみ欄に入れている。
  - `マスの数` は `縦 10 × 横 10` 形式。
  - `MapArea` に保存した `map_grid_rows` / `map_grid_cols` を使って表示する。
  - pending / running / failed で GridCell が無い場合も、作成時の `マスの数` は表示できる。
- Leaflet Map Preview
  - 詳細画面は地図プレビュー中心の UI に整理済み。
  - PC 幅では左に地図プレビュー、右に `選択中のマス` と `採点フォーム` を配置する。
  - GridCell のテキスト一覧は復活させず、地図プレビュー上で確認・選択する。
  - 地図プレビューの高さは PC 幅で大きめに調整済み。
  - `グリッドを再取得` ボタンは `地図プレビュー` 見出し横に移動し、小さめの補助ボタンにしている。
  - 地図操作・色の濃さ・表示切替はコンパクトに配置している。
  - 地図ステータスメッセージ欄は小型化済み。
  - MapArea 全体枠を表示する。
  - GridCell 境界を表示する。
  - GridCell 面を `calculated_score` に応じた半透明色で塗る。
  - スコア色分け凡例を表示する。
  - GridCell のスコア数値ラベルを表示する。
  - スコアラベルはズームに応じてサイズ class を切り替える。
  - スコア数値ラベルは背景・枠線・影を削除し、数値だけを軽く表示する。
  - 色の濃さスライダーでグリッド面の塗りを調整できる。
  - スコア数値ラベル表示 ON/OFF を切り替えられる。
  - 採点済み表示 ON/OFF を切り替えられる。
  - 採点済み表示の初期状態は OFF。
  - 採点済み印は小さめの `✓`。
  - 採点済み表示は `rating_count` ではなく、ログイン中ユーザー自身の採点有無で判定する。
  - 判定用に GridCell 一覧レスポンスへ `current_user_has_rating` を追加済み。
  - 表示 ON/OFF 状態はページ内 state で保持し、localStorage は使わない。
  - 通常地図にはズーム操作バーを追加済み。
    - `−`
    - `＋`
    - `範囲に戻す`
  - Leaflet 標準の左上ズームボタンは残している。
  - `範囲に戻す` は MapArea 全体が見える位置へ戻す。
- 選択操作
  - 通常クリックで単体選択できる。
  - Ctrl / Command クリックで複数選択できる。
  - Shift + ドラッグで範囲内のマスをまとめて選択できる。
  - 範囲選択中は Escape でキャンセルできる。
  - 選択状態は地図、拡大地図、右カラム、採点フォームへ同期する。
- 拡大表示モーダル
  - `拡大表示` ボタンを追加済み。
  - Fullscreen API ではなく、モーダル方式。
  - 拡大表示用 Leaflet map は通常地図とは別インスタンス。
  - モーダル表示後にコンテナサイズが安定してから map を作成する。
  - 背景地図タイルを先に表示し、その後に MapArea 枠、GridCell 境界、ラベル類を重ねる流れ。
  - `invalidateSize()` / `fitBounds()` のタイミングは調整済み。
  - 拡大表示を閉じる時は、拡大用 map / layer state を破棄・初期化する。
  - 以前発生した `Cannot read properties of undefined (reading 'parentNode')` は対策済み。
  - 拡大表示内にもズーム操作バーを追加済み。
    - `−`
    - `＋`
    - `範囲に戻す`
  - 拡大表示内でも通常クリック、Ctrl / Command クリック、Shift + ドラッグ範囲選択に対応済み。
- 採点
  - 単体選択時は単体採点フォームを表示する。
  - 複数選択時は同一スコア・同一コメントで一括採点するフォームだけを表示する。
  - 複数選択時の個別採点 UI は廃止済み。
  - 採点後は GridCell を再取得し、地図色分けとスコアラベルを更新する。
  - 採点中は画面全体ローディングオーバーレイを表示する。
- 選択中のマス表示
  - 右カラム側の `選択中のマス` と `採点フォーム` は余白・文字サイズを軽く調整済み。
  - `グリッド詳細`、`コメント`、`自動採点理由` は折りたたみ表示。
  - コメントはログイン中ユーザー自身の `GridRating.comment`。
  - GridCell 一覧レスポンスに `current_user_comment` を追加済み。
  - 複数選択時は一覧表示を短くし、`#1: 行 ...` のような形式にしている。
  - 選択中のマスに `auto_score_breakdown` がある場合、主な理由や内訳を表示する。
- 共有相手管理
  - メモグリッド作成者は共有相手一覧を表示できる。
  - username を指定して共有相手を追加できる。
  - 共有を解除できる。
- 削除
  - 自分のメモグリッドは詳細画面から削除できる。
  - 削除時は確認ダイアログを表示する。

### JS の整理状況

- `grid-detail-utils.js`
  - 表示用フォーマット、CSRF cookie 取得、API レスポンス読み取り、エラー文言生成、自動採点理由ラベルなどを担当する。
  - 詳細画面の小さな共通関数をまとめる場所になっている。
- `grid-detail-api.js`
  - 詳細画面で使う API 呼び出しを担当する。
  - GridCell 取得、単体採点、一括採点、メモグリッド削除、共有相手取得、共有追加、共有解除を扱う。
  - Session 認証 + CSRF 前提。
- `grid-detail.js`
  - 詳細画面の DOM 描画、選択状態、Leaflet 表示、採点フォーム、共有相手管理、削除などの画面制御を担当する。
  - かなり大きくなってきているので、今後は DOM 描画系の棚卸しと小分けを検討してよい。

### ローディングオーバーレイ

- 画面全体ローディングオーバーレイは `base.html` に共通化済み。
- CSS は `site-loading-overlay` 系 class で定義している。
- 詳細画面では、単体採点、同一値一括採点の処理中に表示する。
- 作成画面では、メモグリッド作成処理中に表示する。
- どちらも `finally` で非表示にする方針。

### demo 専用として本サイトに移行しないもの

- Basic 認証の username / password 入力欄。
- demo 用の 1 ページ完結 UI。
- demo 用の固定値や固定コメント文言。
- demo.js / demo.css の見た目や構造の直接移植。
- demo ページ内でメモグリッド一覧、作成、詳細をすべて切り替える検証用構成。

## 提出前の最終調整（2026-06-15 追記）

提出前の調整は、主に本サイト側の画面改善、スコア計算の安定化、コメント追加に絞って行った。
大きなDB設計変更ではなく、既存 model / migration を保ったまま UI と説明性を整える方針。

### サービス名と認証画面

- サービス名は `Grid Journey` に統一した。
- 共通ヘッダー、ログイン画面、一覧画面、作成画面、詳細画面の表示名を `Grid Journey` に寄せた。
- 詳細画面のブラウザタイトルは `<メモグリッド名> | Grid Journey`。
- 機能名としての `メモグリッド` は残している。
- ヘッダーのブランド名は、サービス名として少し目立つようにフォントや見た目を調整した。
- `/signup/` を追加し、Django 標準の `UserCreationForm` で新規登録できるようにした。
- 登録成功後はログイン画面へ遷移する。
- ログイン画面から新規登録画面へ移動でき、新規登録画面からログイン画面へ戻れる。
- ログイン画面の `メモグリッドへ戻る` 導線は削除し、`ログイン` と `新規登録` に導線を絞った。
- 独自 User model は使っていない。
- 新規登録機能追加で model / migration は変更していない。

### 作成画面

- 作成画面の地図プレビューを改善した。
- 地図中央座標を表示するようにした。
- 地図中央座標を `center_lat` / `center_lng` に反映できるようにした。
- 地図中央を示すクロスヘアを追加した。
- 作成画面にズーム操作ボタンを追加した。
  - `−`
  - `＋`
  - `入力座標へ戻す`
- 作成フォームが縦に長い場合に備えて、下部固定の `メモグリッドを作成` ボタンを追加した。
- 固定ボタンは、通常の作成ボタンが画面内に見えていない場合だけ表示する。
- 固定ボタンは既存フォームの submit を使い、送信処理は複製していない。
- `取得元` 欄と `source` 送信は作成画面から外した。
- `description` の説明 textarea は残している。
- 作成処理、CSRF、作成成功後の詳細画面遷移、Map Preview の入力値連動は維持している。

### 自動設定時の注意と送信前制限

- 自動設定では OSM / Overpass 取得と自動採点を行うため、手動設定より作成に時間がかかる場合がある。
- 都市部の広範囲では Render 上で 500 / 502 が出やすいことが分かった。
- そのため、作成画面側で自動設定時のみ送信前制限を追加した。
- `grid_size_meters * rows` または `grid_size_meters * cols` が `2000m以上` の場合、自動設定では API 送信前に止める。
- 手動設定ではこの制限をかけない。
- 目安として、都市部の自動設定は 1 辺 1.5km 以内が安定しやすい。
- 作成画面に自動設定時の注意文を追加した。
- 画面上の選択は `region_feature_level` を使い、送信時に `initial_score_mode` へ変換する形を維持している。

### 自動初期スコアと表示スコア

- 大きいマスほど地物が多く入りやすく、自動スコアが上がりやすい問題に対応した。
- `calculate_grid_size_score_multiplier` を追加した。
- `base_score` / `diversity_bonus` / `context_bonus` にマスサイズ補正をかける。
- `penalty` には補正をかけない。
- `auto_score_breakdown` に `grid_size_multiplier` を保存する。
- 0.0〜3.0 の clamp は維持している。
- 補正係数の目安:
  - 100m以下: 1.4
  - 200m以下: 1.25
  - 300m以下: 1.0
  - 400m以下: 0.95
  - 500m以下: 0.9
  - 1000m未満: 0.8
  - 1000m以上: 0.7
- 表示スコア計算を、初期スコアを最初の1票として扱う形へ修正した。
- `calculated_score = (initial_score + 全ユーザー採点の合計) / (1 + rating_count)`。
- ユーザー採点が増えるほど、初期スコアの影響が自然に薄まる。
- `average_user_score` はユーザー採点だけの平均として維持している。
- `rating_count` はユーザー採点数として維持している。
- 採点がない場合は `calculated_score = initial_score`。
- APIフィールド名は変更していない。

### 一覧画面

- 一覧カードのサービス名・説明文を `Grid Journey` に合わせた。
- 一覧カードに `マスの数: 縦 n × 横 n` を表示するようにした。
- 一覧 API レスポンスに `map_grid_rows` / `map_grid_cols` を追加した。
- `map_grid_rows` / `map_grid_cols` は MapArea に保存した作成時の行数・列数を返す。
- pending 中で GridCell がまだ無い場合も、一覧画面は保存済みの行数・列数を表示できる。
- APIレスポンス変更に合わせて `API_SPEC.md` も更新済み。
- 自動設定時の地域特徴レベルは `-` と表示するようにした。
- 通常メモグリッドカードは、はっきりめの青い枠線にした。
- 共有メモグリッドカードは、はっきりめの緑の枠線にした。
- 共有メモグリッドカードは青系の反転配色をやめ、文字やリンクは通常カード寄りに戻した。
- 共有メモグリッドカードの背景は、薄く自然な緑色にした。
- `共有メモグリッド` バッジは緑系の背景色にした。
- 一覧カード下部の削除欄はコンパクト化した。
- 警告文は `削除すると元に戻せません。` を維持している。
- 共有メモグリッドでは削除ボタンが表示されない既存仕様を維持している。

### 詳細画面

- 詳細画面タイトルは `<メモグリッド名> | Grid Journey`。
- 画面見出しはメモグリッド名にした。
- `メモグリッド詳細` は見出し下の補助テキストとして残し、リンクに見えない色に調整した。
- 自動設定時の地域特徴レベル表示は `-` にした。
- GridCell 地図表示、スコア色、スコア数値ラベル、採点済み表示を整理した。
- スコアラベルは背景・枠線・影を外し、数値だけを表示する形にした。
- グリッド面の半透明色でスコア傾向を見せる方針。
- 色の濃さスライダーに `薄い` / `標準` / `濃い` と現在値 `0〜100` を表示するようにした。
- `スコア数値を表示` と `採点済みを表示` のチェックボックスを地図操作欄に整理した。
- 採点済み表示のデフォルトは OFF。
- 採点済み印は小さめの `✓` で、軽い半透明背景にした。
- `グリッドを再取得` ボタンは地図プレビュー見出し横へ移動し、小型化した。
- 地図ステータスメッセージ欄は小型化した。
- 地図プレビューの高さを広げ、Leaflet クレジット表記が邪魔になりにくいようにした。
- 通常地図と拡大表示モーダルにズーム操作バーを追加した。
  - `−`
  - `＋`
  - `範囲に戻す`
- Leaflet 標準のズームボタンは残している。
- 複数選択・範囲選択・一括採点の UI を整理した。
- 1件選択時と2件以上選択時の採点欄は、見た目上1つの採点エリアに統合した。
- 複数選択時の個別採点 UI は廃止し、同一スコア・同一コメントの一括採点に絞った。
- 選択中のマスには、`グリッド詳細`、`コメント`、`自動採点理由` を折りたたみ表示する。
- コメントはログイン中ユーザー自身の `GridRating.comment` を表示する。
- GridCell 一覧レスポンスに `current_user_comment` / `current_user_has_rating` を追加済み。
- 自動採点理由 `auto_score_breakdown` は、主な理由や内訳を表示できるようにした。
- 共有相手管理は詳細画面で行える。
- 自分のメモグリッドは詳細画面から削除できる。

### コメント追加

- 提出前に主要ファイルへコメントを追加した。
- コメント追加はロジック変更ではなく、意図説明のため。
- `services.py`
  - OSM / Overpass 取得
  - 自動採点
  - マスサイズ補正
  - 表示スコア計算
  - GridCell 生成
- `grid-create.js`
  - 作成画面の地図操作
  - 自動設定制限
  - 固定作成ボタン
- `grid-detail.js`
  - 詳細画面の地図描画
  - GridCell 選択
  - 採点
  - 共有管理
  - 削除
- 軽いコメント追加:
  - `models.py`
  - `urls.py`
  - `page_urls.py`
  - `admin.py`
  - `grid-detail-api.js`
  - `grid-detail-utils.js`
- migration にはコメント追加していない。

### 変更しなかった方針

- UI調整の多くは model / migration 変更なしで行った。
- APIフィールド名は極力変更していない。
- demo.js / demo.css は提出前の変更対象から外している。
- migrationファイルは Django のDB変更履歴なので、コメント目的では触らない。
- テストファイルへのコメント追加は今回は必須にしていない。

### 今後の候補

- 見た目改善は、提出前に小修正単位で進める。
- 詳細画面は機能が多いので、必要ならセクション順や余白の最終調整を行う。
- `/maps/new/` の Map Preview は表示まで実装済み。今後は地図クリックで中心座標を入力するかどうかを検討する。
- `grid-detail.js` が大きくなってきたため、DOM 描画、Leaflet、採点、共有管理などの分割を検討する。
- 必要になったタイミングで、本サイトと demo の機能差分を再確認する。
