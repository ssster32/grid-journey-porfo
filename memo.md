# 引き継ぎメモ

## プロジェクト概要

- Django REST Framework を使った地図採点 API
- 地図範囲を `MapArea` として登録し、その範囲を将来的に `GridCell` に分割する
- ユーザー採点を `GridRating` に保存し、`GridCell` に集計済み点数を保持する方針
- 共用 Mac 前提のため `.venv` を使い、グローバル Python 環境に依存しない
- 最近の進行方針は、単純な API なら「設計、実装、テスト、API_SPEC 更新」を 1 回で進める形に寄せている

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
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`
- `maps/admin.py`

## 現在の主要ファイル

- `AGENTS.md`: Codex 作業ルール、役割分担
- `README.md`: 環境構築、起動方法、実装済み API の手動確認手順
- `RULES.md`: 短い開発ルール
- `TASK.md`: 現在の作業指示
- `API_SPEC.md`: 実装済み API と未実装 API 候補
- `memo.md`: この引き継ぎメモ
- `maps/models.py`: `MapArea`, `GridCell`, `GridRating`
- `maps/serializers.py`: `MapAreaSerializer`, 採点系 serializer, グリッド出力 serializer
- `maps/services.py`: グリッド点数の集計処理
- `maps/views.py`: MapArea 作成、一覧、詳細、採点、グリッド一覧 API
- `maps/urls.py`: `maps` アプリの API URL
- `maps/tests.py`: serializer、service、view のテスト

## 実装済み

### Django / 環境

- Django REST Framework 導入済み
- `maps` アプリ作成済み
- `config/settings.py` の `INSTALLED_APPS` に `rest_framework` と `maps` 追加済み
- `config/urls.py` で `api/maps/` を `maps.urls` に接続済み
- README に `.venv` 前提のセットアップ、起動、手動確認手順を記載済み
- GitHub remote は `https://github.com/ssster32/grid-journey-porfo.git`

### モデル

実装済みモデル:

- `MapArea`
- `GridCell`
- `GridRating`

作成済み migration:

- `maps/migrations/0001_initial.py`
- `maps/migrations/0002_gridrating.py`

主な設計:

- `MapArea` は地図全体の対象範囲
- `GridCell` は地図範囲を分割した 1 マス
- `GridRating` はユーザー 1 人分の採点
- `GridRating` は `grid` と `user` の組み合わせを重複禁止
- `GridRating.score` は 1 から 10

### Serializer

`maps/serializers.py` に実装済み:

- `MapAreaSerializer`
  - `MapArea` 作成、一覧、詳細の入力チェックと出力に使用
  - `id`, `created_by`, `created_at`, `updated_at` は読み取り専用
  - `north > south`, `east > west`, `grid_size_meters > 0` を検証
- `GridRatingCreateSerializer`
  - 単体採点入力用
  - `score`, `comment` を受け取る
  - `grid` と `user` はクライアントから受け取らない
- `GridRatingResponseSerializer`
  - 採点結果出力用
- `GridCellScoreSerializer`
  - 点数付きグリッド情報出力用
- `BulkGridRatingSerializer`
  - 一括採点入力用
  - `grid_ids`, `score`, `comment` を受け取る
  - 空配列、不存在 ID、重複 ID、score 範囲を検証

### Service

`maps/services.py` に実装済み:

- `update_grid_cell_score(grid_cell)`

採点が 1 件以上ある場合:

```text
average_user_score = 対象 GridCell に紐づく GridRating.score の平均
rating_count = 対象 GridCell に紐づく GridRating の件数
calculated_score = (initial_score + average_user_score) / 2
score_updated_at = 現在時刻
```

採点が 0 件の場合:

```text
average_user_score = 0
rating_count = 0
calculated_score = initial_score
score_updated_at = null
```

## 実装済み API

すべてログイン必須。
各 view では次を設定している。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

### MapArea 作成 API

```text
POST /api/maps/areas/
```

- ログイン中ユーザーが新しい `MapArea` を作成する
- `created_by` はリクエストから受け取らず、ログイン中ユーザーを設定する
- `GridCell` の自動生成はしない

ステータス:

- 作成成功: `201 Created`
- 未ログイン: `401 Unauthorized`
- 入力不正: `400 Bad Request`

### MapArea 一覧 API

```text
GET /api/maps/areas/
```

- 登録済み `MapArea` 一覧を返す
- レスポンスは `{ "areas": [...] }`
- `MapArea` が 0 件なら `areas: []`
- 並び順は model の ordering に従い `name`, `id`

ステータス:

- 成功: `200 OK`
- 未ログイン: `401 Unauthorized`

### MapArea 詳細 API

```text
GET /api/maps/areas/{area_id}/
```

- 指定した `MapArea` 1 件の詳細を返す

ステータス:

- 成功: `200 OK`
- 未ログイン: `401 Unauthorized`
- `area_id` なし: `404 Not Found`

### 単体採点 API

```text
POST /api/maps/grids/{grid_id}/ratings/
```

- ログイン中ユーザーが 1 つの `GridCell` に点数を付ける
- 初回採点なら `GridRating` を作成
- 同じユーザーの再採点なら既存 `GridRating` を更新
- 採点後に `update_grid_cell_score(grid)` を呼び出す

レスポンス:

- `rating`
- `grid`

ステータス:

- 初回採点: `201 Created`
- 再採点: `200 OK`
- 未ログイン: `401 Unauthorized`
- `grid_id` なし: `404 Not Found`
- 入力不正: `400 Bad Request`

### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

- ログイン中ユーザーが複数の `GridCell` に同じ点数をまとめて付ける
- 各グリッドについて初回採点なら作成、既存採点なら更新
- 各グリッドで `update_grid_cell_score(grid)` を呼び出す

レスポンス:

- `grids`

ステータス:

- 全件新規採点: `201 Created`
- 既存採点を 1 件以上更新: `200 OK`
- 未ログイン: `401 Unauthorized`
- `grid_ids` 空、不存在 ID、score 範囲外: `400 Bad Request`

### 点数付きグリッド一覧 API

```text
GET /api/maps/areas/{area_id}/grids/
```

- 指定した `MapArea` に属する `GridCell` 一覧を点数付きで取得する
- `row_index`, `col_index` の順に並べる
- グリッドが 0 件なら `grids: []`
- この API では `update_grid_cell_score()` を呼ばない
- 保存済みの `GridCell` の集計値を読むだけ

レスポンス:

- `area`
- `grids`

ステータス:

- 成功: `200 OK`
- 未ログイン: `401 Unauthorized`
- `area_id` なし: `404 Not Found`

## API_SPEC.md の状態

`API_SPEC.md` は次を反映済み。

- 実装済み API 一覧
- 未実装 API 候補
- MapArea 作成 API
- MapArea 一覧 API
- MapArea 詳細 API
- 単体採点 API
- 一括採点 API
- 点数付きグリッド一覧 API
- 現在の model / serializer / 集計処理
- 未実装・未定のこと

未実装 API 候補:

- `POST /api/maps/areas/{area_id}/grids/`
- `GET /api/maps/grids/search/`

## テスト

`maps/tests.py` に以下のテストがある。

- serializer テスト
- `update_grid_cell_score()` の service テスト
- MapArea 作成 API の view テスト
- MapArea 一覧 API の view テスト
- MapArea 詳細 API の view テスト
- 単体採点 API の view テスト
- 一括採点 API の view テスト
- 点数付きグリッド一覧 API の view テスト

直近の確認結果:

```bash
.venv/bin/python manage.py test maps
```

結果:

```text
Ran 54 tests
OK
```

```bash
.venv/bin/python manage.py check
```

結果:

```text
System check identified no issues
```

```bash
git diff --check
```

結果:

```text
問題なし
```

## Git 状態の注意

直近で `API_SPEC.md`, `TASK.md`, `maps/tests.py`, `maps/urls.py`, `maps/views.py` に未コミット差分がある。

`TASK.md` はユーザーが作業指示として編集するファイルなので、コミット前に含めるか確認するとよい。

## 現在未対応

- `MapArea` 更新 API
- `MapArea` 削除 API
- `GridCell` 自動生成 service / API
- 周辺の高得点グリッド検索 API
- 外部地図 API 連携
- ユーザー別の `MapArea` / `GridCell` 閲覧・採点権限制御
- ページネーション
- 地図表示範囲による絞り込み
- Token 認証 / JWT 認証の検討

## 次にやる候補

ペース重視なら、次は以下のどちらか。

1. `MapArea` 更新 API
2. `MapArea` 削除 API

機能価値重視なら、次は以下。

1. `GridCell` 自動生成 service の仕様決め
2. `POST /api/maps/areas/{area_id}/grids/` の設計と実装

## 最近決めた進め方

小さい API は、次を 1 回で進める。

- API_SPEC.md の設計追記
- 実装
- テスト追加
- API_SPEC.md の実装済み更新
- `.venv/bin/python manage.py test maps`
- `.venv/bin/python manage.py check`
- `git diff --check`

ただし、以下が絡む場合は設計だけで止める。

- `models.py` 変更
- migration 作成
- 認証方式変更
- 外部 API 利用
- セキュリティ設定変更
