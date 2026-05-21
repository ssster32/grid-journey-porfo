# 引き継ぎメモ

## プロジェクト概要

- Django REST Framework を使った地図採点 API。
- `MapArea` で地図範囲を登録し、`GridCell` に分割し、`GridRating` でユーザー採点を保存する。
- 採点後は `GridCell` に平均点、採点数、表示用点数を保存する。
- 共用 Mac 前提のため、Python は `.venv` を使う。
- 作業は小さく分け、`API_SPEC.md`、`TASK.md`、README と実装の差をできるだけ作らない方針。

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

## 現在の主要ファイル

- `README.md`: セットアップ、起動、手動確認手順。
- `TASK.md`: 現在の作業指示。直近では demo ページの Score Map 表示改善タスクが書かれている。
- `API_SPEC.md`: API 仕様と権限方針。
- `maps/models.py`: `MapArea`, `GridCell`, `GridRating`。
- `maps/serializers.py`: MapArea、採点、点数付きグリッド、一括採点の serializer。
- `maps/services.py`: GridCell 自動生成、GridCell 点数再計算。
- `maps/views.py`: 実装済み API の view。
- `maps/urls.py`: `api/maps/` 以下の URL。
- `maps/tests.py`: serializer、service、view のテスト。
- `maps/static/maps/demo.html`: 確認用 demo ページ。
- `maps/static/maps/demo.css`: demo ページのスタイル。
- `maps/static/maps/demo.js`: demo ページから既存 API を呼ぶ処理。

## 現在の Git 状態

直近確認時点では、未コミット差分がある。

主な未コミット差分:

- `README.md`
- `TASK.md`
- `maps/tests.py`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`
- `API_SPEC.md`
- `memo.md`

直近の主なコミット:

- `e59c2d6 GridJouney3日目終了`
- `9526b33 GridCell自動生成API-README`
- `e15ac2e GridCell自動生成service`

## 実装済みモデル

`models.py` と migration は既に作成済み。
指示がない限り、今後も変更しない。

実装済み:

- `MapArea`
  - 地図として扱う範囲。
  - `created_by` は nullable。
  - 作成 API ではログイン中ユーザーを `created_by` に入れる。
- `GridCell`
  - `MapArea` を一定距離で分割した 1 マス。
  - `area`, `row_index`, `col_index` の組み合わせで一意。
  - 点数集計結果を保持する。
- `GridRating`
  - ユーザーが 1 つの `GridCell` に付けた採点。
  - `grid` と `user` の組み合わせは一意。
  - `score` は 1 から 10。

作成済み migration:

- `maps/migrations/0001_initial.py`
- `maps/migrations/0002_gridrating.py`

## 実装済み service

### `generate_grid_cells_for_area(map_area)`

`maps/services.py` に実装済み。

- `MapArea` の緯度経度範囲と `grid_size_meters` から `GridCell` を自動生成する。
- 1 度を約 111000m として計算している。
- `ceil()` を使い、端の半端な範囲も 1 マスとして生成する。
- 既に対象 `MapArea` に `GridCell` がある場合は `ValueError` を返す。
- `bulk_create()` でまとめて DB に保存する。

現在の注意点:

- 地球の丸みや緯度による経度距離の違いはまだ考慮していない。
- これは学習用の簡易実装。
- 外部地図 API 連携はまだない。

### `update_grid_cell_score(grid_cell)`

`maps/services.py` に実装済み。

- 対象 `GridCell` の `GridRating` を集計する。
- 採点がある場合は平均点と採点数を保存する。
- `calculated_score` は `(initial_score + average_user_score) / 2`。
- 採点が 0 件なら `calculated_score = initial_score` に戻す。

## 実装済み API

すべてログイン必須。

各 view では基本的に次を使っている。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

### MapArea 作成 API

```text
POST /api/maps/areas/
```

- ログイン中ユーザーで `MapArea` を作成する。
- `created_by` はリクエストから受け取らず、サーバー側で `request.user` を入れる。
- 作成後、同じ transaction 内で `generate_grid_cells_for_area(area)` を呼び、`GridCell` も自動生成する。
- GridCell 生成に失敗した場合、MapArea だけが保存される状態にはしない。

### MapArea 一覧 API

```text
GET /api/maps/areas/
```

- `MapArea.objects.filter(created_by=request.user)` で絞り込む。
- 自分が作成した `MapArea` だけ返す。
- 他ユーザーの `MapArea` と `created_by is None` の `MapArea` は一覧に出ない。
- 対象が 0 件なら `areas: []`。

### MapArea 詳細 API

```text
GET /api/maps/areas/{area_id}/
```

- `get_object_or_404(MapArea, id=area_id, created_by=request.user)` で取得する。
- 自分の `MapArea` なら `200 OK`。
- 他ユーザーの `MapArea`、`created_by is None`、存在しない ID は `404 Not Found`。

### GridCell 自動生成 API

```text
POST /api/maps/areas/{area_id}/grids/
```

- 対象 `MapArea` から `GridCell` を自動生成する。
- `area.created_by == request.user` の場合だけ生成できる。
- 他ユーザーの `MapArea` や `created_by is None` の `MapArea` は `403 Forbidden`。
- 既に `GridCell` がある場合は `400 Bad Request`。
- 成功時は `201 Created` で `area` と `grids` を返す。

閲覧 API は他ユーザーのデータを `404` にしている。
一方、自動生成 API は「対象は存在するが操作権限がない」という扱いで `403` にしている。
この差は `API_SPEC.md` に記載済み。

### 点数付きグリッド一覧 API

```text
GET /api/maps/areas/{area_id}/grids/
```

- `get_object_or_404(MapArea, id=area_id, created_by=request.user)` で `MapArea` を取得する。
- 自分の `MapArea` に属する `GridCell` だけ取得できる。
- 他ユーザーの `MapArea`、`created_by is None`、存在しない ID は `404 Not Found`。
- 保存済みの点数集計値を読むだけで、再集計はしない。

### 単体採点 API

```text
POST /api/maps/grids/{grid_id}/ratings/
```

- ログイン中ユーザーが 1 つの `GridCell` に採点する。
- 初回なら `GridRating` を作成し、同じユーザーの再採点なら更新する。
- 採点後に `update_grid_cell_score(grid)` を呼ぶ。
- `GridCell.area.created_by == request.user` の場合だけ採点できる。
- 他ユーザーの `MapArea` に属する `GridCell` や `created_by is None` の `MapArea` に属する `GridCell` は `404 Not Found`。

### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

- 複数の `GridCell` に同じ点数をまとめて付ける。
- 各グリッドで初回採点なら作成、既存採点なら更新する。
- 各グリッドで `update_grid_cell_score(grid)` を呼ぶ。
- すべての `GridCell` がログイン中ユーザーの `MapArea` に属する場合だけ採点できる。
- 他ユーザーの `GridCell` や `created_by is None` の `GridCell` が 1 件でも含まれる場合は `400 Bad Request`。
- 一部だけ採点して成功、という動きにはしない。

## 確認用 demo ページ

```text
GET /api/maps/demo/
```

ブラウザで既存 API を確認するための簡易 UI を追加済み。
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

Score Map:

- 将来の地図背景に重ねる想定の、一枚の地図状の四角として表示。
- `MapArea.east - MapArea.west` と `MapArea.north - MapArea.south` から概算した縦横比を反映する。
- 正確な地図投影や外部地図表示はまだ行わない。
- `row_index` / `col_index` に対応した簡易グリッド配置は維持。
- 各マスは `calculated_score` を大きく表示し、`GridCell ID`、`row/col` は確認用に小さく表示。
- テーブルの `calculated_score` にも色付きバッジを表示。

色分け:

| calculated_score | 表示 |
| --- | --- |
| `0 <= score < 3` | 低スコア |
| `3 <= score < 6` | 中スコア |
| `6 <= score < 8` | 高スコア |
| `8 <= score` | 最高スコア |

注意:

- MapArea 作成 API は、MapArea 作成後に GridCell も自動生成する。
- demo ページには `GridCell を自動生成` ボタンは表示しない。
- demo ページでは `GridCell を再取得` ボタンで表示を更新できる。
- 外部ライブラリ、React、Vue、Leaflet、Google Maps は使っていない。

## API_SPEC.md の状態

反映済み:

- 実装済み API 一覧。
- GridCell 自動生成 API の仕様。
- GridCell 自動生成 API の `created_by` ベース権限。
- MapArea 一覧、詳細、点数付きグリッド一覧の閲覧権限方針。
- 採点 API / 一括採点 API の `created_by` ベース権限。
- 設計メモ: 共有 MapArea。

共有 MapArea 設計メモ:

- 将来的に `MapArea.is_public` を追加する想定。
- `is_public=False` は作成者本人だけ閲覧・採点可。
- `is_public=True` はログインユーザー全員が閲覧・採点可。
- GridCell 自動生成は `is_public` に関係なく作成者だけ。
- `created_by=None` は public 扱いしない。
- 一覧 API は「自分の MapArea + public MapArea」を返す方針。

## README.md の状態

手動確認手順に以下を追加済み。

- GridCell 自動生成 API の確認。
- 同じ `MapArea` に再度自動生成すると `400 Bad Request` になる確認。
- MapArea 閲覧制限の確認。
- `otheruser` で `testuser` の `MapArea` を見ようとすると、一覧では出ず、詳細とグリッド一覧は `404 Not Found` になる確認。
- 他ユーザーでは単体採点 API と一括採点 API を実行できないことの確認。
- 確認用 demo ページの使い方。
- demo ページで MapArea 作成、GridCell 自動生成済み Score Map 表示、採点、Score Map の色更新を確認する手順。
- Score Map を一枚の地図状の四角として表示し、MapArea bounds から概算縦横比を反映する説明。

## テスト

`maps/tests.py` に以下のテストがある。

- `MapAreaSerializer` の入力検証。
- `GridRatingCreateSerializer` の入力検証。
- `BulkGridRatingSerializer` の入力検証。
- `update_grid_cell_score()` の service テスト。
- `generate_grid_cells_for_area()` の service テスト。
- MapArea 作成 API の view テスト。
- MapArea 一覧 API の view テスト。
- MapArea 詳細 API の view テスト。
- GridCell 自動生成 API の view テスト。
- 単体採点 API の view テスト。
- 一括採点 API の view テスト。
- 点数付きグリッド一覧 API の view テスト。
- demo ページ表示テスト。

直近の確認結果:

```bash
.venv/bin/python manage.py test maps
```

結果:

```text
Ran 94 tests
OK
```

```bash
.venv/bin/python manage.py check
```

結果:

```text
System check identified no issues
```

直近で確認した差分チェック:

```bash
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.css maps/static/maps/demo.js README.md maps/tests.py
```

結果:

```text
問題なし
```

JavaScript 構文チェック:

```bash
node --check maps/static/maps/demo.js
```

結果:

```text
問題なし
```

ローカルサーバー確認:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8001
curl -s http://127.0.0.1:8001/api/maps/demo/
curl -I http://127.0.0.1:8001/static/maps/demo.js
curl -I http://127.0.0.1:8001/static/maps/demo.css
```

結果:

```text
demo ページの HTML、demo.js、demo.css が返ることを確認済み
確認用サーバーは停止済み
```

## 2026-05-21 手動確認結果

README の手順に沿って、主要 API の一連の流れを手動確認済み。
ユーザー確認では、期待通りの結果が返っている。

確認済みの流れ:

1. `runserver` を起動したまま、別ターミナルで確認用データを作成。
2. `testuser` で単体採点 API を実行し、初回採点と再採点ができることを確認。
3. `testuser` で一括採点 API を実行し、複数 GridCell の採点と再集計ができることを確認。
4. 点数付きグリッド一覧 API で、採点後の `average_user_score`、`rating_count`、`calculated_score` が返ることを確認。
5. `otheruser` で MapArea 一覧、詳細、点数付きグリッド一覧の閲覧制限を確認。
6. `otheruser` で単体採点 API が `404 Not Found` になることを確認。
7. `otheruser` で一括採点 API が `400 Bad Request` になることを確認。

この確認により、簡易的には次の最小フローが動く状態になっている。

```text
MapArea 作成
→ GridCell 用意または自動生成
→ 点数付きグリッド一覧取得
→ 採点
→ 点数再集計
→ 他ユーザーの閲覧・採点拒否
```

## 2026-05-21 demo ページ更新結果

確認用 demo ページに、ブラウザだけで最小フローを確認しやすくする機能を追加済み。

追加済みの流れ:

```text
demo ページを開く
→ username/password を入力
→ MapArea を作成
→ 作成した MapArea を選択
→ 自動生成済み GridCell を再取得
→ Score Map と GridCell テーブルを確認
→ GridCell に score を入力して採点
→ calculated_score と色分け表示が更新されることを確認
```

ユーザーへの説明済み:

- マス表示は demo ページ右側の `Score Map` に出る。
- MapArea 作成後、または GridCell 一覧取得後に表示される。
- `Score Map` が「GridCell はまだ表示されていません。」の場合は、対象 MapArea に GridCell がない。
- `Score Map` はマス間の gap をなくし、一枚の地図状の面として表示する。
- score 値を主役にし、ID と row/col は確認用に小さく表示する。
- Score Map には将来の地図背景用に `score-map-background` レイヤーを用意済み。
- 表示領域の縦横比は MapArea の緯度経度範囲から概算する。
- ただし、外部地図 API、地図画像、正確な地図投影はまだ実装していない。

## 2026-05-21 demo ページ手動確認結果

ユーザー確認で、demo ページの最新表示が期待通り動作することを確認済み。

確認済み:

- MapArea 作成後に GridCell が自動生成される。
- demo ページには `GridCell を自動生成` ボタンを表示しない。
- `GridCell を再取得` で Score Map と GridCell 一覧を更新できる。
- Score Map は一枚の大きな四角として表示される。
- `calculated_score` が各マスのメイン表示になる。
- `GridCell ID` と `row_index` / `col_index` は確認用に小さく表示される。
- MapArea の緯度経度範囲から概算した `area ratio` が表示される。
- 採点後、`calculated_score` と色分け表示が更新される。

## 現在未対応

- `TASK.md` を完了済みとして整理すること。
- `MapArea` 更新 API。
- `MapArea` 削除 API。
- 周辺の高得点グリッド検索 API。
- 外部地図 API 連携。
- ページネーション。
- 地図表示範囲による絞り込み。
- Token 認証 / JWT 認証の検討。
- 共有 MapArea の `is_public` 実装。
- Score Map を実際の地図座標に合わせて正確に描画すること。
- 外部地図 API や地図画像を Score Map 背景として表示すること。

## 次にやるとよい作業

優先度が高い順:

1. `TASK.md` を今日の完了状態に整理する。
2. 現在の差分を確認して、必要ならコミットする。
3. README の手動確認結果を必要に応じて追記する。
4. 共有 MapArea の `is_public` 実装に進むか、MapArea 更新 / 削除 API に進むか決める。
5. 外部地図背景、正確な地図投影、Token/JWT 認証のどれを次に扱うか決める。

## 作業時の注意

- `models.py` と migration は、明示指示がない限り変更しない。
- 権限や認証の変更は、実装前に方針と影響を説明する。
- Python コマンドは `.venv/bin/python` または `.venv` 有効化後の `python` を使う。
- 実装後は最低限、次を確認する。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff --check
```
