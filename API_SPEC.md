# API_SPEC.md

このファイルは、地図採点 API の仕様を整理するためのドキュメントです。
現在は、実装済み API と今後の設計メモを分けて記録します。

初心者向け補足:

- API は、フロントエンドや外部ツールがサーバーの機能を使うための入口です。
- リクエストは「API に送る内容」、レスポンスは「API から返ってくる内容」です。
- ステータスコードは、処理が成功したか、どんなエラーだったかを表す番号です。

## 目的

地図を一定距離幅のグリッドに分割し、各グリッドに点数を付けます。
ユーザーはグリッドを採点でき、システムは初期点数やユーザー採点をもとに表示用の点数を計算します。
最終的には、具体的な観光情報を見すぎず、点数を手がかりに気ままに旅先を選べる API を目指します。

## 現在の実装状況

実装済み API:

| メソッド | パス | 目的 | 認証 |
| --- | --- | --- | --- |
| `POST` | `/api/maps/areas/` | 地図範囲を登録する | 必要 |
| `GET` | `/api/maps/areas/` | 地図範囲一覧を取得する | 必要 |
| `GET` | `/api/maps/areas/{area_id}/` | 地図範囲詳細を取得する | 必要 |
| `POST` | `/api/maps/grids/{grid_id}/ratings/` | 1 つのグリッドを採点する | 必要 |
| `POST` | `/api/maps/grids/bulk-ratings/` | 複数グリッドをまとめて採点する | 必要 |
| `GET` | `/api/maps/areas/{area_id}/grids/` | 点数付きグリッド一覧を取得する | 必要 |

未実装 API 候補:

| メソッド | パス | 目的 | 認証 | 状態 |
| --- | --- | --- | --- | --- |
| `POST` | `/api/maps/areas/{area_id}/grids/` | 地図範囲をグリッドに分割する | 必要 | 未実装 |
| `GET` | `/api/maps/grids/search/` | 周辺の高得点グリッドを検索する | 必要 | 未実装 |

## 認証

現在実装済みの API はログイン必須です。

実装では各 view に次を設定しています。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

初心者向け補足:

- 認証は「誰が使っているか」を確認する仕組みです。
- 権限は「その人が何をしてよいか」を確認する仕組みです。
- `BasicAuthentication` は、ユーザー名とパスワードを使う認証方式です。
- `SessionAuthentication` は、Django のログイン状態を使う認証方式です。

新しい認証方式はまだ追加していません。
Token 認証や JWT 認証を使うかどうかは未定です。

## 用語

| 用語 | 意味 |
| --- | --- |
| MapArea | 地図として扱う対象範囲 |
| GridCell | 地図を一定距離幅で分割した 1 マス |
| GridRating | ユーザーが 1 つのグリッドに付けた採点 |
| Initial Score | 地形情報などからシステムが最初に付ける点数 |
| Average User Score | ユーザー採点の平均点 |
| Rating Count | そのグリッドに付いた採点数 |
| Calculated Score | 地図表示に使う最終的な点数 |

## 実装済み API

### 単体採点 API

```text
POST /api/maps/grids/{grid_id}/ratings/
```

ログイン中ユーザーが 1 つの `GridCell` に点数を付ける API です。

初回採点なら `GridRating` を作成します。
同じユーザーが同じグリッドを再採点した場合は、新しい行を作らず既存の `GridRating` を更新します。
採点後は `GridCell` の集計済み点数を再計算します。

#### 認証

ログイン必須です。

#### URL パラメータ

| 名前 | 型 | 内容 |
| --- | --- | --- |
| `grid_id` | integer | 採点対象の `GridCell` ID |

#### リクエスト

```json
{
  "score": 8,
  "comment": "水辺が近くて良さそう"
}
```

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `score` | 必須 | 1 から 10 の整数 |
| `comment` | 任意 | 採点理由やメモ。空文字も可 |

`grid` と `user` はリクエストボディでは受け取りません。
`grid` は URL の `grid_id` から、`user` はログイン中ユーザーからサーバー側で決めます。

#### レスポンス

```json
{
  "rating": {
    "id": 1,
    "grid": 10,
    "user": 3,
    "score": 8,
    "comment": "水辺が近くて良さそう",
    "created_at": "2026-05-15T10:00:00+09:00",
    "updated_at": "2026-05-15T10:00:00+09:00"
  },
  "grid": {
    "id": 10,
    "area": 1,
    "row_index": 0,
    "col_index": 0,
    "north": 35.7,
    "south": 35.69,
    "east": 139.8,
    "west": 139.79,
    "initial_score": 3.0,
    "average_user_score": 8.0,
    "rating_count": 1,
    "calculated_score": 5.5,
    "score_updated_at": "2026-05-15T10:00:00+09:00"
  }
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 初回採点を作成した | `201 Created` |
| 既存採点を更新した | `200 OK` |
| 未ログイン | `401 Unauthorized` |
| `grid_id` が存在しない | `404 Not Found` |
| `score` が範囲外 | `400 Bad Request` |
| `score` がない | `400 Bad Request` |

### 一括採点 API

```text
POST /api/maps/grids/bulk-ratings/
```

ログイン中ユーザーが複数の `GridCell` に同じ点数をまとめて付ける API です。

各グリッドについて、初回採点なら `GridRating` を作成します。
既存採点がある場合は更新します。
各 `GridCell` の集計済み点数を再計算し、更新後のグリッド一覧を返します。

#### 認証

ログイン必須です。

#### リクエスト

```json
{
  "grid_ids": [10, 11],
  "score": 5,
  "comment": "まとめて採点"
}
```

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `grid_ids` | 必須 | 採点対象の `GridCell` ID 配列 |
| `score` | 必須 | 1 から 10 の整数 |
| `comment` | 任意 | 採点理由やメモ。空文字も可 |

`grid_ids` に重複がある場合、重複は取り除いて 1 回だけ処理します。
`grid_ids` に存在しない ID が 1 つでも含まれる場合は、全体を `400 Bad Request` にします。

#### レスポンス

```json
{
  "grids": [
    {
      "id": 10,
      "area": 1,
      "row_index": 0,
      "col_index": 0,
      "north": 35.7,
      "south": 35.69,
      "east": 139.8,
      "west": 139.79,
      "initial_score": 3.0,
      "average_user_score": 5.0,
      "rating_count": 1,
      "calculated_score": 4.0,
      "score_updated_at": "2026-05-15T10:00:00+09:00"
    },
    {
      "id": 11,
      "area": 1,
      "row_index": 0,
      "col_index": 1,
      "north": 35.7,
      "south": 35.69,
      "east": 139.79,
      "west": 139.78,
      "initial_score": 7.0,
      "average_user_score": 5.0,
      "rating_count": 1,
      "calculated_score": 6.0,
      "score_updated_at": "2026-05-15T10:00:00+09:00"
    }
  ]
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 全件新規採点を作成した | `201 Created` |
| 既存採点を 1 件以上更新した | `200 OK` |
| 未ログイン | `401 Unauthorized` |
| `grid_ids` が空 | `400 Bad Request` |
| `grid_ids` に存在しない ID がある | `400 Bad Request` |
| `score` が範囲外 | `400 Bad Request` |
| `score` がない | `400 Bad Request` |

### 点数付きグリッド一覧 API

```text
GET /api/maps/areas/{area_id}/grids/
```

指定した `MapArea` に属する `GridCell` 一覧を、点数付きで取得する API です。
地図画面でグリッドを表示し、`calculated_score` をもとに色分けするための元データを返します。

この API では集計値を再計算しません。
保存済みの `GridCell` の集計値を読み取って返します。

#### 認証

ログイン必須です。

#### URL パラメータ

| 名前 | 型 | 内容 |
| --- | --- | --- |
| `area_id` | integer | 取得対象の `MapArea` ID |

#### リクエスト

リクエストボディはありません。

#### レスポンス

```json
{
  "area": {
    "id": 1,
    "name": "Manual Test Area"
  },
  "grids": [
    {
      "id": 10,
      "area": 1,
      "row_index": 0,
      "col_index": 0,
      "north": 35.7,
      "south": 35.69,
      "east": 139.8,
      "west": 139.79,
      "initial_score": 3.0,
      "average_user_score": 8.0,
      "rating_count": 1,
      "calculated_score": 5.5,
      "score_updated_at": "2026-05-15T10:00:00+09:00"
    }
  ]
}
```

対象 `MapArea` に `GridCell` が 0 件の場合:

```json
{
  "area": {
    "id": 1,
    "name": "Manual Test Area"
  },
  "grids": []
}
```

#### 並び順

`grids` は次の順に並びます。

1. `row_index`
2. `col_index`

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 一覧を取得できた | `200 OK` |
| 未ログイン | `401 Unauthorized` |
| `area_id` が存在しない | `404 Not Found` |

#### 注意点

- 採点数が 0 件のグリッドも返します。
- 別の `MapArea` に属する `GridCell` は含めません。
- ページネーションはまだ入れていません。
- 地図表示範囲による絞り込みはまだ入れていません。

### MapArea 作成 API

```text
POST /api/maps/areas/
```

ログイン中ユーザーが、新しい `MapArea` を作成する API です。

この API では地図範囲だけを保存します。
`GridCell` の自動生成は行いません。
グリッド生成は処理が大きくなりやすいため、別の API または service として後続タスクで設計します。

#### 認証

ログイン必須です。

`created_by` はリクエストボディでは受け取りません。
ログイン中ユーザーをサーバー側で `created_by` に設定します。

#### リクエスト

```json
{
  "name": "東京駅周辺",
  "description": "手動作成した確認用エリア",
  "north": 35.7,
  "south": 35.6,
  "east": 139.8,
  "west": 139.7,
  "grid_size_meters": 500,
  "source": "manual"
}
```

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `name` | 必須 | 地図範囲の名前 |
| `description` | 任意 | 地図範囲の説明やメモ。空文字も可 |
| `north` | 必須 | 地図範囲の北端の緯度 |
| `south` | 必須 | 地図範囲の南端の緯度 |
| `east` | 必須 | 地図範囲の東端の経度 |
| `west` | 必須 | 地図範囲の西端の経度 |
| `grid_size_meters` | 必須 | グリッド 1 マスの大きさ。0 より大きい整数 |
| `source` | 任意 | 地図データの取得元。手動作成なら `manual` など |

クライアントから受け取らない項目:

| 項目 | 理由 |
| --- | --- |
| `created_by` | ログイン中ユーザーからサーバー側で決めるため |
| `created_at` | 作成日時は Django が自動で保存するため |
| `updated_at` | 更新日時は Django が自動で保存するため |

#### バリデーション

| 条件 | エラー |
| --- | --- |
| `name` が空 | `400 Bad Request` |
| `north` が `south` 以下 | `400 Bad Request` |
| `east` が `west` 以下 | `400 Bad Request` |
| `grid_size_meters` が 0 以下 | `400 Bad Request` |
| 必須項目がない | `400 Bad Request` |

初心者向け補足:

- バリデーションは、変なデータを DB に保存しないためのチェックです。
- `north > south` と `east > west` を確認するのは、地図範囲として上下左右が逆にならないようにするためです。
- `grid_size_meters` が 0 以下だと、グリッドの大きさとして使えないためエラーにします。

#### レスポンス

作成に成功した場合は、作成された `MapArea` を返します。

```json
{
  "id": 1,
  "name": "東京駅周辺",
  "description": "手動作成した確認用エリア",
  "north": 35.7,
  "south": 35.6,
  "east": 139.8,
  "west": 139.7,
  "grid_size_meters": 500,
  "source": "manual",
  "created_by": 3,
  "created_at": "2026-05-18T10:00:00+09:00",
  "updated_at": "2026-05-18T10:00:00+09:00"
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 作成成功 | `201 Created` |
| 未ログイン | `401 Unauthorized` |
| 入力不正 | `400 Bad Request` |

#### 今回は実装しないこと

- 作成と同時に `GridCell` を自動生成するかどうか
- 同じ名前の `MapArea` を許可するかどうか
- ユーザーごとに `MapArea` の閲覧範囲を制限するかどうか
- 外部地図 API から座標を自動取得するかどうか
- `source` の選択肢を固定するかどうか

### MapArea 一覧 API

```text
GET /api/maps/areas/
```

ログイン中ユーザーが、登録済みの `MapArea` 一覧を取得する API です。

#### 認証

ログイン必須です。

#### リクエスト

リクエストボディはありません。

#### レスポンス

```json
{
  "areas": [
    {
      "id": 1,
      "name": "東京駅周辺",
      "description": "手動作成した確認用エリア",
      "north": 35.7,
      "south": 35.6,
      "east": 139.8,
      "west": 139.7,
      "grid_size_meters": 500,
      "source": "manual",
      "created_by": 3,
      "created_at": "2026-05-18T10:00:00+09:00",
      "updated_at": "2026-05-18T10:00:00+09:00"
    }
  ]
}
```

`MapArea` が 0 件の場合:

```json
{
  "areas": []
}
```

#### 並び順

`MapArea` model の ordering に従い、`name`, `id` の順に並びます。

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 一覧を取得できた | `200 OK` |
| 未ログイン | `401 Unauthorized` |

### MapArea 詳細 API

```text
GET /api/maps/areas/{area_id}/
```

指定した `MapArea` 1 件の詳細を取得する API です。

#### 認証

ログイン必須です。

#### URL パラメータ

| 名前 | 型 | 内容 |
| --- | --- | --- |
| `area_id` | integer | 取得対象の `MapArea` ID |

#### リクエスト

リクエストボディはありません。

#### レスポンス

```json
{
  "id": 1,
  "name": "東京駅周辺",
  "description": "手動作成した確認用エリア",
  "north": 35.7,
  "south": 35.6,
  "east": 139.8,
  "west": 139.7,
  "grid_size_meters": 500,
  "source": "manual",
  "created_by": 3,
  "created_at": "2026-05-18T10:00:00+09:00",
  "updated_at": "2026-05-18T10:00:00+09:00"
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 詳細を取得できた | `200 OK` |
| 未ログイン | `401 Unauthorized` |
| `area_id` が存在しない | `404 Not Found` |

## 現在のモデル

model は DB のテーブル設計に対応します。
現在は `MapArea`、`GridCell`、`GridRating` の 3 つの model を実装済みです。

### MapArea

地図全体の対象範囲を表します。
たとえば「東京駅周辺」や「京都市中心部」のように、グリッド分割する元の範囲です。

| フィールド | 必須 | 役割 |
| --- | --- | --- |
| `name` | 必須 | 地図範囲の名前 |
| `description` | 任意 | 地図範囲の説明やメモ |
| `north` | 必須 | 北端の緯度 |
| `south` | 必須 | 南端の緯度 |
| `east` | 必須 | 東端の経度 |
| `west` | 必須 | 西端の経度 |
| `grid_size_meters` | 必須 | グリッド 1 マスの大きさ |
| `source` | 任意 | 地図データの取得元 |
| `created_by` | 任意 | この地図範囲を作成したユーザー |
| `created_at` | 必須 | 作成日時 |
| `updated_at` | 必須 | 更新日時 |

制約:

- `north` は `south` より大きい必要があります。
- `east` は `west` より大きい必要があります。
- `grid_size_meters` は 0 より大きい必要があります。

### GridCell

`MapArea` を分割した 1 マスを表します。
複数ユーザーの採点結果そのものは `GridRating` に保存し、`GridCell` には集計済みの表示用スコアを保存します。

| フィールド | 必須 | 役割 |
| --- | --- | --- |
| `area` | 必須 | どの地図範囲に属するか |
| `row_index` | 必須 | 上から何行目のグリッドか |
| `col_index` | 必須 | 左から何列目のグリッドか |
| `north` | 必須 | グリッド北端の緯度 |
| `south` | 必須 | グリッド南端の緯度 |
| `east` | 必須 | グリッド東端の経度 |
| `west` | 必須 | グリッド西端の経度 |
| `initial_score` | 必須 | 地形情報などから付ける初期点数 |
| `average_user_score` | 必須 | ユーザー採点の平均点 |
| `rating_count` | 必須 | 採点数 |
| `calculated_score` | 必須 | 表示用の最終点数 |
| `score_updated_at` | 任意 | 集計点を最後に更新した日時 |
| `created_at` | 必須 | 作成日時 |
| `updated_at` | 必須 | 更新日時 |

制約:

- 同じ `MapArea` の中で、`row_index` と `col_index` の組み合わせは重複できません。

### GridRating

ユーザー 1 人分の採点を表します。
複数ユーザーが同じ `GridCell` を採点できるように、採点データは `GridCell` とは別 model にしています。

| フィールド | 必須 | 役割 |
| --- | --- | --- |
| `grid` | 必須 | どのグリッドへの採点か |
| `user` | 必須 | 誰が採点したか |
| `score` | 必須 | ユーザーが付けた点数 |
| `comment` | 任意 | 採点理由やメモ |
| `created_at` | 必須 | 作成日時 |
| `updated_at` | 必須 | 更新日時 |

制約:

- `score` は 1 から 10 の整数です。
- 同じ `grid` と `user` の組み合わせは重複できません。

## 現在の serializer

serializer は、Python のデータと JSON を変換する部品です。
また、不正な入力を防ぐバリデーションも担当します。

| serializer | 用途 |
| --- | --- |
| `MapAreaSerializer` | 地図範囲の入力チェックと出力 |
| `GridRatingCreateSerializer` | 単体採点 API の入力チェック |
| `GridRatingResponseSerializer` | 採点結果の出力 |
| `GridCellScoreSerializer` | 点数付きグリッド情報の出力 |
| `BulkGridRatingSerializer` | 一括採点 API の入力チェック |

### MapAreaSerializer

入力・出力項目:

| 項目 |
| --- |
| `id` |
| `name` |
| `description` |
| `north` |
| `south` |
| `east` |
| `west` |
| `grid_size_meters` |
| `source` |
| `created_by` |
| `created_at` |
| `updated_at` |

`id`, `created_by`, `created_at`, `updated_at` は読み取り専用です。
`created_by` はログイン中ユーザーからサーバー側で設定します。

### GridRatingCreateSerializer

入力項目:

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `score` | 必須 | 1 から 10 の整数 |
| `comment` | 任意 | 空文字も可 |

### GridRatingResponseSerializer

出力項目:

| 項目 |
| --- |
| `id` |
| `grid` |
| `user` |
| `score` |
| `comment` |
| `created_at` |
| `updated_at` |

### GridCellScoreSerializer

出力項目:

| 項目 |
| --- |
| `id` |
| `area` |
| `row_index` |
| `col_index` |
| `north` |
| `south` |
| `east` |
| `west` |
| `initial_score` |
| `average_user_score` |
| `rating_count` |
| `calculated_score` |
| `score_updated_at` |

### BulkGridRatingSerializer

入力項目:

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `grid_ids` | 必須 | 空ではない `GridCell` ID 配列 |
| `score` | 必須 | 1 から 10 の整数 |
| `comment` | 任意 | 空文字も可 |

バリデーション:

- `grid_ids` は空配列にできません。
- `grid_ids` に存在しない ID が含まれる場合はエラーにします。
- `grid_ids` に重複がある場合は、重複を取り除きます。
- `score` は 1 から 10 の範囲です。

## 集計処理

採点 API は、`GridRating` の作成または更新後に `update_grid_cell_score(grid_cell)` を呼び出します。

`update_grid_cell_score(grid_cell)` は `maps/services.py` に実装済みです。

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

初心者向け補足:

- 集計は、複数の点数から表示用の点数を計算する処理です。
- `average_user_score` はユーザーが付けた点数の平均です。
- `rating_count` は、そのグリッドに何件の採点があるかです。
- `calculated_score` は、地図上で色分け表示するときに使う最終点数です。
- 採点後に再計算しないと、地図上に古い点数が表示される可能性があります。

## 未実装・未定のこと

現在未実装:

- 地図範囲からグリッドを自動生成する API
- 周辺の高得点グリッドを検索する API
- 外部地図 API から地図情報を取得する処理
- フロントエンド向けの表示範囲絞り込み
- ページネーション

現在未定:

- 地図データの取得元
- グリッド幅の最終仕様
- 初期点数の計算方法
- 平均値以外の集計方法を使うか
- 匿名採点を許可するか
- 採点履歴を保存するか
- Token 認証や JWT 認証を導入するか
- ユーザーごとの `MapArea` や `GridCell` の閲覧・採点権限をどう制限するか
- 位置情報や行動履歴を保存するか
- フロントエンドでどの地図ライブラリを使うか

## 次に設計するとよい候補

次に進めるなら、次のどれか 1 つに絞ると学習しやすいです。

1. 地図範囲から `GridCell` を自動生成する service の仕様を決める
2. グリッド数が多くなった場合のページネーション方針を決める
3. 認証方式を Basic / Session のまま進めるか、Token 系にするかを検討する
