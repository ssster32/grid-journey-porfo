# 引き継ぎメモ

## プロジェクト概要

- Django REST Framework を使った地図採点 API。
- `MapArea` で地図範囲を登録し、`GridCell` に分割し、`GridRating` でユーザー採点を保存する。
- ユーザー向けには、個人用の `MapArea` を「メモグリッド」、特定ユーザーに共有したものを「共有メモグリッド」と呼ぶ。
- 共用 Mac 前提のため、Python は `.venv` を使う。
- 作業は小さく分け、`API_SPEC.md`、`TASK.md`、README、実装の差をできるだけ作らない方針。

## 作業前に読むファイル

- `AGENTS.md`
- `README.md`
- `RULES.md`
- `TASK.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `API_SPEC.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`
- `maps/admin.py`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`

## 現在の Git 状態

直近確認時点では、未コミット差分がある。

主な未コミット差分:

- `README.md`
- `TASK.md`
- `maps/serializers.py`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`
- `maps/tests.py`
- `memo.md`

直近の作業では、共有相手管理 API 実装後に demo ページから共有相手を追加・削除できる UI を追加し、その後メモグリッド一覧と Score Map の見た目を調整した。

## 実装済みモデル

`MapAreaShare` まで実装済み。

実装済み:

- `MapArea`
  - 地図として扱う範囲。
  - `created_by` は nullable。
  - 作成 API ではログイン中ユーザーを `created_by` に入れる。
- `MapAreaShare`
  - どの `MapArea` をどのユーザーに共有しているかを表す。
  - `area` と `user` の組み合わせは一意。
  - `area.shares` と `user.shared_map_areas` から参照できる。
- `GridCell`
  - `MapArea` を一定距離幅で分割した 1 マス。
  - `area`, `row_index`, `col_index` の組み合わせで一意。
  - 点数集計結果を保持する。
- `GridRating`
  - ユーザーが 1 つの `GridCell` に付けた採点。
  - `grid` と `user` の組み合わせは一意。
  - `score` は 1 から 10。

作成済み migration:

- `maps/migrations/0001_initial.py`
- `maps/migrations/0002_gridrating.py`
- `maps/migrations/0003_mapareashare.py`

## 認証

現在の地図 API はログイン必須。

各 API view では基本的に次を使う。

```python
authentication_classes = [
    TokenAuthentication,
    BasicAuthentication,
    SessionAuthentication,
]
permission_classes = [IsAuthenticated]
```

実装済み:

- Basic 認証
- Session 認証
- Token 認証
- `POST /api/auth/token/`

JWT 認証はまだ実装しない方針。

## 実装済み service

### `generate_grid_cells_for_area(map_area)`

- `MapArea` の緯度経度範囲と `grid_size_meters` から `GridCell` を自動生成する。
- 1 度を約 111000m として計算している。
- `ceil()` を使い、端の半端な範囲も 1 マスとして生成する。
- 既に対象 `MapArea` に `GridCell` がある場合は `ValueError` を返す。
- `bulk_create()` でまとめて DB に保存する。
- 地球の丸みや緯度による経度距離の違いはまだ考慮していない。

### `update_grid_cell_score(grid_cell)`

- 対象 `GridCell` の `GridRating` を集計する。
- 採点がある場合は平均点と採点数を保存する。
- `calculated_score` は `(initial_score + average_user_score) / 2`。
- 採点が 0 件なら `calculated_score = initial_score` に戻す。

## 実装済み API

### MapArea 作成 API

```text
POST /api/maps/areas/
```

- ログイン中ユーザーで `MapArea` を作成する。
- `created_by` はリクエストから受け取らず、サーバー側で `request.user` を入れる。
- 作成後、同じ transaction 内で `generate_grid_cells_for_area(area)` を呼び、`GridCell` も自動生成する。
- GridCell 生成に失敗した場合、MapArea だけが保存される状態にはしない。
- 一般ユーザーは、緯度差または経度差が 20 分を超えるメモグリッドを作成できない。
- 管理者はこの 20 分制限の対象外。

### MapArea 一覧 API

```text
GET /api/maps/areas/
```

- 自分が作成した `MapArea` と、自分に共有された `MapArea` を返す。
- 自分のメモグリッドには `visibility: "private"`、`display_type: "メモグリッド"`、`is_owner: true` が付く。
- 共有メモグリッドには `visibility: "shared"`、`display_type: "共有メモグリッド"`、`is_owner: false` が付く。
- `created_by_username` を返す。
- demo ページでは、自分のメモグリッドは `作成者: 自分`、共有メモグリッドは `作成者: <username>` と表示する。
- 他ユーザーが作成し、自分に共有されていない `MapArea` は一覧に出ない。

### MapArea 詳細 API

```text
GET /api/maps/areas/{area_id}/
```

- 自分が作成した `MapArea`、または自分に共有された `MapArea` だけ取得できる。
- 共有されていない他ユーザーの `MapArea`、存在しない ID は `404 Not Found`。
- `created_by=None` の `MapArea` も、自分に共有されていれば取得できる。

### GridCell 自動生成 API

```text
POST /api/maps/areas/{area_id}/grids/
```

- 対象 `MapArea` から `GridCell` を自動生成する。
- `area.created_by == request.user` の場合だけ生成できる。
- 共有されたユーザーは実行できない。
- 他ユーザーの `MapArea` や `created_by is None` の `MapArea` は `403 Forbidden`。
- 既に `GridCell` がある場合は `400 Bad Request`。

### 点数付きグリッド一覧 API

```text
GET /api/maps/areas/{area_id}/grids/
```

- 自分が作成した `MapArea`、または自分に共有された `MapArea` の `GridCell` を取得できる。
- 保存済みの点数集計値を読むだけで、再集計はしない。
- 共有されていない他ユーザーの `MapArea` は `404 Not Found`。

### 単体採点 API

```text
POST /api/maps/grids/{grid_id}/ratings/
```

- ログイン中ユーザーが 1 つの `GridCell` に採点する。
- 初回なら `GridRating` を作成し、同じユーザーの再採点なら更新する。
- 採点後に `update_grid_cell_score(grid)` を呼ぶ。
- 自分のメモグリッド、または自分に共有された共有メモグリッドの `GridCell` だけ採点できる。
- 採点者は常にログイン中ユーザー。
- 共有メモグリッドを採点しても、作成者ではなく共有されたユーザー自身の `GridRating` として保存される。

### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

- 複数の `GridCell` に同じ点数をまとめて付ける。
- 各グリッドで初回採点なら作成、既存採点なら更新する。
- 各グリッドで `update_grid_cell_score(grid)` を呼ぶ。
- すべての `GridCell` が自分のメモグリッド、または自分に共有された共有メモグリッドに属する場合だけ採点できる。
- 権限外または存在しない `GridCell` が 1 件でも含まれる場合は `400 Bad Request`。
- 一部だけ採点して成功、という動きにはしない。

### 共有相手管理 API

```text
GET /api/maps/areas/{area_id}/shares/
POST /api/maps/areas/{area_id}/shares/
DELETE /api/maps/areas/{area_id}/shares/{share_id}/
```

- 作成者だけが共有相手一覧取得・追加・削除できる。
- 共有されたユーザーは閲覧・採点はできるが、共有相手管理はできない。
- 共有相手追加は `username` 指定。
- レスポンスには `id` と `username` を返し、`email` は返さない。
- 権限がない場合は、他ユーザーのデータ存在を推測しにくくするため `404 Not Found`。
- 削除成功時は `204 No Content`。

## 確認用 demo ページ

```text
GET /api/maps/demo/
```

ブラウザで既存 API を確認するための簡易 UI。
本格的な地図 UI ではなく、API 動作確認用。

demo ページ自体は認証なしで表示できる。
実際の API 呼び出しでは、画面に入力した username/password から JavaScript が Basic 認証ヘッダーを作る。
本番向けのログイン UI ではない。

現在できること:

- username/password 入力。
- MapArea 作成。
- MapArea 一覧取得。
- MapArea 選択。
- MapArea 作成後の GridCell 自動生成。
- GridCell 一覧取得。
- 単体採点。
- 採点後の GridCell 一覧再取得。
- `calculated_score` に応じた Score Map の色分け表示。
- Score Map 背景画像 URL の指定。
- 共有相手一覧取得。
- 共有相手 username による共有追加。
- 共有相手一覧から共有解除。
- Score Map のマスクリックによる GridCell 選択。
- 選択中 GridCell の採点パネルからの単体採点。

メモグリッド一覧表示:

- 共有メモグリッドは背景 `#EEEEFF`、枠線は背景より濃い青。
- hover / 選択時は少し濃い青。
- ボタン右下に `display_type / 作成者: ...` を小さめに表示。
- 自分のメモグリッドは `作成者: 自分`。
- 共有メモグリッドは `作成者: <created_by_username>`。

Score Map:

- 将来の地図背景に重ねる想定の、一枚の地図状の四角として表示。
- `MapArea.east - MapArea.west` と `MapArea.north - MapArea.south` から概算した縦横比を反映する。
- 正確な地図投影や外部地図表示はまだ行わない。
- `row_index` / `col_index` に対応した簡易グリッド配置は維持。
- 各マスは `calculated_score` を表示する。
- 各マスはクリック可能。
- クリックしたマスは選択状態になり、採点パネルに GridCell 情報が表示される。
- スコア文字は以前より小さめ。
- スコア値に応じて文字色を変えている。
- グリッド自体の背景色は控えめにしている。
- `GridCell ID`、`row/col` は確認用に小さく表示。
- テーブルの `calculated_score` にも色付きバッジを表示。

共有操作の確認結果:

- `testuser` で demo ページから共有相手 `otheruser` を追加できた。
- `otheruser` に切り替えるには、demo ページ上部の認証欄を `otheruser` / `other-password` に変更する。
- 共有後、`otheruser` で共有メモグリッドの閲覧・GridCell 表示・採点を確認できた。
- `testuser` に戻って共有解除できた。

## README の現状

README には以下を記載済み。

- セットアップ手順。
- Token 認証手順。
- MapArea 作成と GridCell 自動生成。
- 単体採点、一括採点。
- MapArea 閲覧制限。
- 他ユーザーでは採点できないことの確認。
- 共有相手管理 API の curl 手動確認。
- demo ページでの共有相手管理確認。
- Score Map 背景画像 URL の使い方。

## 2026-05-25 Score Map クリック採点対応

- Score Map のマスをクリックして GridCell を選択できるようにした。
- 選択中 GridCell を demo ページ内の `選択中のマス` パネルから採点できるようにした。
- 採点 API 呼び出し処理を `submitRating()` に寄せ、既存のテーブル採点と採点パネルの両方から使う形にした。
- 採点後は `loadGrids()` で GridCell 一覧と Score Map を再読み込みする。
- 再読み込み後も対象 GridCell が存在すれば選択状態を維持する。
- メモグリッド切り替え時は選択中 GridCell をリセットする。
- README の demo 確認手順に、Score Map クリック採点の確認を追加した。

確認:

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
.venv/bin/python manage.py check
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
.venv/bin/python manage.py test maps
```

結果:

- `MapDemoViewTests` 通過。
- `150 tests` 通過。
- `System check identified no issues`。

次:

- ブラウザで Score Map のマス選択、採点パネル採点、テーブル採点、共有メモグリッドでの採点を手動確認するとよい。
- 必要に応じて、選択中マスの枠線や採点パネルの位置を微調整する。

## 直近の確認コマンド

直近作業で確認済み:

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
.venv/bin/python manage.py check
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
```

直近の全体テスト:

```bash
.venv/bin/python manage.py test maps
```

結果:

- `150 tests` 通過。
- `System check identified no issues`。

## 2026-05-25 Score Map 複数選択採点対応

- Score Map のマスを複数選択できるようにした。
- 選択済みのマスをもう一度クリックすると、選択解除できるようにした。
- `選択中のマス` パネルに、選択数、選択中 GridCell 一覧、個別 score 入力欄、選択解除ボタンを表示するようにした。
- 採点方式として、`個別に入力し、まとめて採点` と `選択グリッドを全て同じ値で採点` を選べるようにした。
- 個別入力方式では、単体採点 API を複数回呼び、最後に GridCell を再読み込みする。
- 同じ値方式では、一括採点 API を使う。
- 下部の表形式採点 UI は使わず、Score Map と選択中マスパネルで採点する流れに寄せた。
- README の demo ページ確認手順を、複数選択採点の流れに更新した。

確認:

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py check
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
.venv/bin/python manage.py test maps
```

ブラウザ確認:

- `http://127.0.0.1:8001/api/maps/demo/` で demo ページを開き、複数選択用 UI が表示されることを確認した。
- 旧単体採点フォームと下部テーブル用 `grids-body` が表示されていないことを確認した。

次:

- ブラウザで Score Map の複数選択、個別入力まとめ採点、同じ値での一括採点を手動確認するとよい。
- 必要に応じて、ドラッグ選択や矩形選択を検討する。

## 2026-05-25 Score Map 表示モード対応

- Score Map に `全体表示` / `詳細表示` を追加した。
- 初期表示は `全体表示`。
- 全体表示では、CSS Grid ベースのまま Score Map 全体が表示枠内に収まるようにした。
- 詳細表示では、1マスの最低サイズを確保し、縦横スクロールで GridCell を確認できるようにした。
- Score Map 周りを `stage / background / grid-layer` として扱いやすい構造に整理した。
- GridCell の緯度経度から絶対配置する方式は、次回以降の検討に残した。
- README の demo ページ確認手順に、表示モードと `grid_size_meters` の扱いを短く追記した。

確認:

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py check
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
.venv/bin/python manage.py test maps
```

ブラウザ確認:

- `http://127.0.0.1:8001/api/maps/demo/` で demo ページを開いた。
- `表示モード`、`全体表示`、`詳細表示`、`score-map-grid-layer` が表示されることを確認した。
- `詳細表示` に切り替えると `score-map-wrap` / `score-map-stage` に `is-detail` が付き、`全体表示` に戻すと `is-fit` が付くことを確認した。

次:

- ブラウザで GridCell 数が多いメモグリッドを開き、全体表示と詳細表示の切り替えを手動確認するとよい。
- 必要に応じて、GridCell の `north/south/east/west` を使った割合配置方式を検討する。

## 次にやるとよいこと

- Score Map クリック採点をブラウザで手動確認する。
- 採点パネルの位置や選択中マスの枠線を、見た目に合わせて微調整する。
- 必要に応じて、共有メモグリッドでも Score Map クリック採点できることを README に短く追記する。

## 注意点

- `models.py` と migration は、指示がない限り変更しない。
- `created_by=None` は public 扱いしない。
- 共有されたユーザーは閲覧・採点だけ可能。
- GridCell 自動生成と共有相手管理は作成者だけ可能。
- ワールドグリッド用の `is_public` はまだ未実装。
- ユーザー検索 API、username オートコンプリート、email 共有はまだ未実装。
