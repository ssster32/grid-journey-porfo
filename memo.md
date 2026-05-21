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
- `TASK.md`: 現在の作業指示。直近では MapArea 閲覧制限の実装タスクが書かれている。
- `API_SPEC.md`: API 仕様と権限方針。
- `maps/models.py`: `MapArea`, `GridCell`, `GridRating`。
- `maps/serializers.py`: MapArea、採点、点数付きグリッド、一括採点の serializer。
- `maps/services.py`: GridCell 自動生成、GridCell 点数再計算。
- `maps/views.py`: 実装済み API の view。
- `maps/urls.py`: `api/maps/` 以下の URL。
- `maps/tests.py`: serializer、service、view のテスト。

## 現在の Git 状態

直近確認時点では、ワークツリーはクリーン。

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
- `GridCell` の自動生成はしない。

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

現在の注意点:

- `grid.area.created_by == request.user` の権限チェックはまだ入っていない。
- そのため、ID が分かれば他ユーザーの `GridCell` に採点できる可能性がある。
- 次に優先度が高い実装候補。

### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

- 複数の `GridCell` に同じ点数をまとめて付ける。
- 各グリッドで初回採点なら作成、既存採点なら更新する。
- 各グリッドで `update_grid_cell_score(grid)` を呼ぶ。

現在の注意点:

- 単体採点 API と同じく、`grid.area.created_by == request.user` の権限チェックはまだ入っていない。
- 一括採点では、複数 ID の中に他ユーザーの `GridCell` が混ざるケースも考える必要がある。

## API_SPEC.md の状態

反映済み:

- 実装済み API 一覧。
- GridCell 自動生成 API の仕様。
- GridCell 自動生成 API の `created_by` ベース権限。
- MapArea 一覧、詳細、点数付きグリッド一覧の閲覧権限方針。

注意:

- `API_SPEC.md` の MapArea 閲覧権限セクションは、見出しが「設計中」のまま。
- 実装とテストは完了済みなので、次のドキュメント整理で「実装済み」扱いに直すとよい。

## README.md の状態

手動確認手順に以下を追加済み。

- GridCell 自動生成 API の確認。
- 同じ `MapArea` に再度自動生成すると `400 Bad Request` になる確認。
- MapArea 閲覧制限の確認。
- `otheruser` で `testuser` の `MapArea` を見ようとすると、一覧では出ず、詳細とグリッド一覧は `404 Not Found` になる確認。

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

直近の確認結果:

```bash
.venv/bin/python manage.py test maps
```

結果:

```text
Ran 81 tests
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
git diff --check -- maps/views.py maps/tests.py
```

結果:

```text
問題なし
```

## 現在未対応

- 採点 API の `created_by` ベース権限チェック。
- 一括採点 API の `created_by` ベース権限チェック。
- `API_SPEC.md` の MapArea 閲覧権限セクションを「実装済み」扱いに整理すること。
- `TASK.md` を完了済みとして整理すること。
- `MapArea` 更新 API。
- `MapArea` 削除 API。
- 周辺の高得点グリッド検索 API。
- 外部地図 API 連携。
- ページネーション。
- 地図表示範囲による絞り込み。
- Token 認証 / JWT 認証の検討。

## 次にやるとよい作業

優先度が高い順:

1. 採点 API と一括採点 API に `created_by` ベースの権限チェックを設計する。
2. `API_SPEC.md` に採点 API の権限仕様を書く。
3. `TASK.md` に「採点 API の権限チェック実装 + テスト追加」の小さいタスクを作る。
4. 実装する場合は `maps/views.py` と `maps/tests.py` を中心に進める。
5. README に採点 API の権限手動確認手順を短く追加する。

採点 API の権限方針案:

- 未ログインは `401 Unauthorized`。
- 自分の `MapArea` に属する `GridCell` なら採点可能。
- 他ユーザーの `MapArea` に属する `GridCell` は採点不可。
- `created_by is None` の `MapArea` に属する `GridCell` も採点不可。
- エラーを `403` にするか `404` にするかは、API_SPEC で先に決める。

実装候補:

```python
grid = get_object_or_404(GridCell, id=grid_id, area__created_by=request.user)
```

一括採点 API では、`grid_ids` の全件がログイン中ユーザーの `MapArea` に属するかを検証する必要がある。
存在しない ID と権限なし ID を同じ扱いにするなら、取得件数と入力 ID 件数を比較する方針が分かりやすい。

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
