# 引き継ぎメモ

## プロジェクト概要

- Django REST Framework を使った地図採点 API
- 地図範囲をグリッド状に分割し、各グリッドに点数を付ける API を段階的に作っている
- ユーザー採点を `GridRating` に保存し、`GridCell` に集計済み点数を保持する方針
- 共用 Mac 前提のため `.venv` を使い、グローバル Python 環境に依存しない
- 初心者が学習しながら開発する前提なので、作業は小さく分け、理由も説明する

## 作業ルール

作業前に読むファイル:

- `AGENTS.md`
- `README.md`
- `RULES.md`
- `TASK.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `API_SPEC.md`
- 対象アプリの `models.py`, `serializers.py`, `views.py`, `urls.py`, `tests.py`, `admin.py`

基本方針:

- 変更前に作業計画を出す
- 1 回の作業は小さくする
- 不明点は仮定として明記する
- `.venv` の Python を使う
- 依存関係、認証、権限、セキュリティ設定を変える場合は理由を説明する
- model / migration の変更は特に慎重に行う

## 現在の主要ファイル

- `AGENTS.md`: Codex 作業ルール、役割分担
- `README.md`: 環境構築、起動方法、実装済み API の手動確認手順
- `RULES.md`: 短い開発ルール
- `TASK.md`: 現在の作業タスク
- `API_SPEC.md`: API 設計メモ
- `memo.md`: この引き継ぎメモ
- `maps/models.py`: `MapArea`, `GridCell`, `GridRating`
- `maps/serializers.py`: 採点入力・出力、グリッド点数出力、一括採点入力
- `maps/services.py`: グリッド点数の集計処理
- `maps/views.py`: 単体採点、一括採点、点数付きグリッド一覧 API
- `maps/urls.py`: `maps` アプリの API URL
- `maps/tests.py`: serializer、service、view のテスト

## 実装済み

### Django / 環境

- Django REST Framework 導入済み
- `maps` アプリ作成済み
- `config/settings.py` の `INSTALLED_APPS` に `rest_framework` と `maps` 追加済み
- `config/urls.py` で `api/maps/` を `maps.urls` に接続済み
- README に `.venv` 前提のセットアップ、起動、手動確認手順を記載済み

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
- `score` は 1 から 10

### Serializer

`maps/serializers.py` に実装済み:

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
  - 空配列、不存在 ID、重複 ID、score 範囲を検証する

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

### API

実装済み API:

```text
POST /api/maps/grids/{grid_id}/ratings/
POST /api/maps/grids/bulk-ratings/
GET /api/maps/areas/{area_id}/grids/
```

#### 単体採点 API

```text
POST /api/maps/grids/{grid_id}/ratings/
```

目的:

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

#### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

目的:

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

#### 点数付きグリッド一覧 API

```text
GET /api/maps/areas/{area_id}/grids/
```

目的:

- 指定した `MapArea` に属する `GridCell` 一覧を点数付きで取得する
- 地図画面で `calculated_score` を使って色分け表示するためのデータを返す

レスポンス:

- `area`
- `grids`

方針:

- `GridCellScoreSerializer` を使う
- `row_index`, `col_index` の順に並べる
- グリッドが 0 件なら `grids: []`
- この API では `update_grid_cell_score()` を呼ばない
- 保存済みの `GridCell` の集計値を読むだけ

ステータス:

- 成功: `200 OK`
- 未ログイン: `401 Unauthorized`
- `area_id` なし: `404 Not Found`

### 認証・権限

現在の実装では、各 API view に次を設定している。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

つまり、採点 API とグリッド一覧 API はログイン必須。
新しい認証方式はまだ追加していない。

## README に記載済みの手動確認

README の `実装済み API の手動確認` に以下を記載済み。

- 確認用ユーザー、`MapArea`, `GridCell` 作成手順
- 単体採点 API の `curl` 確認
- 一括採点 API の `curl` 確認
- 点数付きグリッド一覧 API の `curl` 確認
- 未ログイン、score 範囲外、不存在 `grid_id`、不存在 `area_id` のエラー確認

## API_SPEC.md に記載済み

- モデル設計案
- Serializer 設計案
- View 設計案
- 集計処理設計案
- 単体採点 API
- 一括採点 API
- 点数付きグリッド一覧 API
- 未決定事項

点数付きグリッド一覧 API は、`GET /api/maps/areas/{area_id}/grids/` として仕様追記済み。

## テスト

`maps/tests.py` に以下のテストがある。

- serializer テスト
- `update_grid_cell_score()` の service テスト
- 単体採点 API の view テスト
- 一括採点 API の view テスト
- 点数付きグリッド一覧 API の view テスト

直近の確認結果:

```bash
.venv/bin/python manage.py test maps
```

結果:

```text
Ran 37 tests

OK
```

```bash
.venv/bin/python manage.py check
```

結果:

```text
System check identified no issues (0 silenced).
```

## Git 状態

`git status --short` は実行できる。
ただし、プロジェクト内のファイルが未追跡として表示されている。

表示例:

```text
?? .env.example
?? .gitignore
?? AGENTS.md
?? API_SPEC.md
?? README.md
?? RULES.md
?? TASK.md
?? config/
?? manage.py
?? maps/
?? memo.md
?? requirements.txt
```

考えられる状態:

- Git リポジトリとしては初期化されている
- まだ `git add` されていない
- `.gitignore` の内容を確認してから初回 commit するのがよい

注意:

- `.venv/`
- `db.sqlite3`
- `.env`
- `__pycache__/`
- `.pip-cache/`
- `.DS_Store`

これらは Git に入れない。

## まだ未実装

- 地図範囲登録 API
- 地図範囲一覧 API
- グリッド自動生成 API
- 地図データ取得処理
- 周辺の高得点グリッド検索 API
- 認証方式の本格設計
- MapArea / GridCell ごとの権限制御
- ページネーション
- 地図表示範囲による絞り込み
- 同時更新対策
- 本番向け設定

## 次にやるとよい作業

おすすめは、まず Git 管理を整理すること。

理由:

- 現在、多くのファイルが未追跡になっている
- このまま作業を続けると、どの変更がいつ入ったか追いにくくなる
- 初回 commit を作ると、以後の差分確認がしやすくなる

小さな次タスク案:

```text
.gitignore の内容を確認し、Git に入れてよいファイルだけを初回 commit する準備をしてください。
```

その次の機能開発候補:

```text
地図範囲一覧 API `GET /api/maps/areas/` の仕様を API_SPEC.md に書いてください。
```

または:

```text
地図範囲登録 API `POST /api/maps/areas/` の仕様を API_SPEC.md に書いてください。
```

## 初心者向け用語メモ

- `model`: DB のテーブル設計に対応する Python クラス
- `serializer`: Python のデータと JSON の変換、入力チェックを担当する部品
- `view`: リクエストを受け取り、レスポンスを返す処理
- `url`: API の入り口を決める設定
- `migration`: model の変更を DB に反映するための履歴
- `GridCell`: 地図を一定の大きさに区切った 1 マス
- `GridRating`: ユーザー 1 人分の採点
- `集計`: 複数の点数から表示用の点数を計算する処理
- `認証`: 誰かを確認する仕組み
- `権限`: 何をしてよいかを確認する仕組み
- `.venv`: このプロジェクト専用の Python 環境
- `.env`: PC ごとの秘密情報や設定を置くファイル
