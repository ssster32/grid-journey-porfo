# API_SPEC.md

Grid Journey の API 仕様を整理するドキュメントです。

Grid Journey は、地図上の範囲をメモグリッドとして作成し、生成された GridCell に対してユーザーが採点・コメントできる Web アプリです。
画面上では `MapArea` を「メモグリッド」と呼びますが、API 内部の model 名や URL は `MapArea` / `GridCell` のままです。

初心者向け補足:

- API は、フロントエンドや外部ツールがサーバーの機能を使うための入口です。
- request は API に送る内容、response は API から返る内容です。
- serializer は Python のデータと JSON の変換、入力チェックを担当します。
- view は request を受け取り、権限確認や保存処理を行って response を返します。

## 認証・権限

地図 API はログイン必須です。

API view では、次の認証方式を併用しています。

- Token 認証
- Basic 認証
- Session 認証

本サイト画面では Django ログイン + Session + CSRF を使います。
API 手動確認では Token 認証も使えます。
既存テストや開発確認では Basic 認証も利用できます。

POST / DELETE を Session 認証で呼ぶ場合は、Django の CSRF チェックを通す必要があります。
本サイトの JavaScript では cookie の `csrftoken` を `X-CSRFToken` ヘッダーに付けています。

### Token 発行

```text
POST /api/auth/token/
```

リクエスト:

```json
{
  "username": "testuser",
  "password": "test-password"
}
```

レスポンス:

```json
{
  "token": "xxxxxxxxxxxxxxxx"
}
```

Token 認証ヘッダー:

```http
Authorization: Token <TOKEN>
```

### 権限の基本方針

- 作成者本人は、自分のメモグリッドを閲覧・採点・共有管理・削除できます。
- 共有されたユーザーは、共有メモグリッドを閲覧・採点できます。
- 共有されたユーザーは、共有相手管理とメモグリッド削除はできません。
- 共有されていないユーザーは、対象メモグリッドを取得できません。
- 権限がない MapArea / GridCell は、存在を推測しにくくするため `404 Not Found` または validation error として扱います。

## エンドポイント一覧

### API

| メソッド | パス | 目的 | 認証 |
| --- | --- | --- | --- |
| `POST` | `/api/auth/token/` | Token 発行 | 不要 |
| `GET` | `/api/maps/areas/` | メモグリッド一覧取得 | 必要 |
| `POST` | `/api/maps/areas/` | メモグリッド作成 | 必要 |
| `GET` | `/api/maps/areas/<area_id>/` | メモグリッド詳細取得 | 必要 |
| `DELETE` | `/api/maps/areas/<area_id>/` | メモグリッド削除 | 必要 |
| `GET` | `/api/maps/areas/<area_id>/shares/` | 共有相手一覧取得 | 必要 |
| `POST` | `/api/maps/areas/<area_id>/shares/` | 共有相手追加 | 必要 |
| `DELETE` | `/api/maps/areas/<area_id>/shares/<share_id>/` | 共有解除 | 必要 |
| `GET` | `/api/maps/areas/<area_id>/grids/` | GridCell 一覧取得 | 必要 |
| `POST` | `/api/maps/areas/<area_id>/grids/` | GridCell 生成 | 必要 |
| `POST` | `/api/maps/grids/<grid_id>/ratings/` | 単体採点 | 必要 |
| `POST` | `/api/maps/grids/bulk-ratings/` | 一括採点 | 必要 |

補足:

- 通常のメモグリッド作成では、`POST /api/maps/areas/` の中で GridCell も生成されます。
- `POST /api/maps/areas/<area_id>/grids/` は実装上残っていますが、通常画面の主導線ではありません。
- `/api/maps/demo/` は開発確認用 HTML を返す demo 画面で、通常の JSON API 仕様の主対象ではありません。

### 画面 URL

API ではありませんが、本サイト画面は次の URL で提供しています。

| パス | 目的 |
| --- | --- |
| `/login/` | ログイン |
| `/signup/` | 新規ユーザー登録 |
| `/maps/` | メモグリッド一覧 |
| `/maps/new/` | メモグリッド作成 |
| `/maps/<area_id>/` | メモグリッド詳細 |

## MapArea

### 作成

```text
POST /api/maps/areas/
```

中心座標、1マスの大きさ、縦横のマス数から地図範囲を計算し、MapArea と GridCell を作成します。
現在の作成 API は中心座標方式を基本にしています。
`north` / `south` / `east` / `west` の直接指定は作成入力では使えません。

リクエスト:

```json
{
  "name": "大阪駅周辺調査",
  "description": "駅周辺を散歩候補として確認する",
  "center_lat": 34.702485,
  "center_lng": 135.495951,
  "grid_size_meters": 200,
  "rows": 10,
  "cols": 10,
  "initial_score_mode": "manual",
  "region_feature_level": 2
}
```

主な入力項目:

| 項目 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `name` | string | 必須 | メモグリッド名 |
| `description` | string | 任意 | 説明 |
| `center_lat` | number | 必須 | 中心緯度 |
| `center_lng` | number | 必須 | 中心经度 |
| `grid_size_meters` | integer | 必須 | 1マスの大きさ |
| `rows` | integer | 必須 | 縦方向のマス数 |
| `cols` | integer | 必須 | 横方向のマス数 |
| `initial_score_mode` | string | 任意 | `manual` または `auto`。未指定時は `manual` |
| `region_feature_level` | integer | 任意 | 0〜3。未指定時は 0 |
| `source` | string | 任意 | model / serializer には残っている任意項目。現在の作成画面の主要入力ではない |

`source` は API 項目としては残っていますが、現在の `/maps/new/` 画面では入力欄や主要 payload から外しています。

一般ユーザー向けの API 側制限:

- `rows * cols <= 500`
- `grid_size_meters * rows <= 30000`
- `grid_size_meters * cols <= 30000`

staff ユーザーはこの一般ユーザー制限の対象外です。

ステータス:

| 状況 | ステータス |
| --- | --- |
| 作成成功 | `201 Created` |
| 入力不正 | `400 Bad Request` |
| 未認証 | `401 Unauthorized` |

### initial_score_mode / region_feature_level

`initial_score_mode`:

| 値 | 意味 |
| --- | --- |
| `manual` | `region_feature_level` を初期スコアとして使う |
| `auto` | OSM / Overpass から地域特徴を取得し、自動初期スコアを計算する |

`region_feature_level`:

| 値 | 意味 |
| --- | --- |
| `0` | 初期値 |
| `1` | ありふれた地域 |
| `2` | 普通の地域 |
| `3` | 特徴的な地域 |

手動設定では、`region_feature_level` が各 GridCell の `initial_score` として使われます。
自動設定では、OSM / Overpass の取得結果から `initial_score` と `auto_score_breakdown` を作成します。
画面上では「自動設定」を選ぶと `initial_score_mode="auto"`、`region_feature_level=0` として送信します。
自動設定時の地域特徴レベルは画面では `-` と表示しますが、API値としては `region_feature_level` を持ちます。

### 自動設定時の注意

自動設定は OSM / Overpass API 取得を伴うため、手動設定より時間がかかる場合があります。
都市部や広範囲では地物数が多くなり、処理が重くなりやすいです。

画面側では自動設定時のみ、1辺が `2000m以上` の作成を API 送信前に制限しています。
手動設定ではこの画面側制限はかけていません。

API 側には、上記とは別に一般ユーザー向けの `500マス / 南北30000m / 東西30000m` 制限があります。
都市部の自動設定は、1辺 1.5km 以内が安定しやすい目安です。

Overpass 取得や特徴集計で `ValueError` が発生した場合、MapArea 作成自体は止めず、手動設定相当の fallback で GridCell を生成します。

### 一覧取得

```text
GET /api/maps/areas/
```

ログインユーザーが作成したメモグリッドと、ログインユーザーに共有されたメモグリッドを返します。

レスポンス:

```json
{
  "areas": [
    {
      "id": 1,
      "name": "大阪駅周辺調査",
      "description": "駅周辺を散歩候補として確認する",
      "north": 34.711,
      "south": 34.693,
      "east": 135.506,
      "west": 135.486,
      "grid_size_meters": 200,
      "region_feature_level": 2,
      "initial_score_mode": "manual",
      "source": "",
      "created_by": 1,
      "created_at": "2026-06-15T10:00:00+09:00",
      "updated_at": "2026-06-15T10:00:00+09:00",
      "visibility": "private",
      "display_type": "メモグリッド",
      "is_owner": true,
      "created_by_username": "testuser",
      "map_grid_rows": 10,
      "map_grid_cols": 10
    }
  ]
}
```

一覧用の追加項目:

| 項目 | 説明 |
| --- | --- |
| `visibility` | `private` または `shared` |
| `display_type` | `メモグリッド` または `共有メモグリッド` |
| `is_owner` | ログインユーザーが作成者かどうか |
| `created_by_username` | 作成者の username。作成者がない場合は `null` |
| `map_grid_rows` | GridCell の最大 `row_index` + 1。GridCell がない場合は `null` |
| `map_grid_cols` | GridCell の最大 `col_index` + 1。GridCell がない場合は `null` |

`map_grid_rows` / `map_grid_cols` は、一覧 API で `annotate()` を使ってまとめて取得し、MapArea ごとの個別集計による N+1 を避けています。

### 詳細取得

```text
GET /api/maps/areas/<area_id>/
```

閲覧できる MapArea の詳細を返します。
レスポンス項目は基本的に `MapAreaSerializer` の項目です。

主なレスポンス項目:

- `id`
- `name`
- `description`
- `north`
- `south`
- `east`
- `west`
- `grid_size_meters`
- `region_feature_level`
- `initial_score_mode`
- `source`
- `created_by`
- `created_at`
- `updated_at`

### 削除

```text
DELETE /api/maps/areas/<area_id>/
```

作成者のみ削除できます。
削除すると、関連する GridCell、採点、共有設定も cascade で削除されます。
共有されたユーザーは削除できません。

ステータス:

| 状況 | ステータス |
| --- | --- |
| 削除成功 | `204 No Content` |
| 権限なし / 存在しない | `404 Not Found` |

## GridCell

### 一覧取得

```text
GET /api/maps/areas/<area_id>/grids/
```

閲覧できる MapArea に属する GridCell 一覧を、`row_index` / `col_index` 順で返します。

レスポンス:

```json
{
  "area": {
    "id": 1,
    "name": "大阪駅周辺調査"
  },
  "grids": [
    {
      "id": 1,
      "area": 1,
      "row_index": 0,
      "col_index": 0,
      "north": 34.703,
      "south": 34.701,
      "east": 135.497,
      "west": 135.495,
      "initial_score": 2.0,
      "auto_score_breakdown": null,
      "average_user_score": 8.0,
      "rating_count": 1,
      "calculated_score": 5.0,
      "score_updated_at": "2026-06-15T10:30:00+09:00",
      "current_user_comment": "駅が近くて使いやすそう",
      "current_user_has_rating": true
    }
  ]
}
```

GridCell レスポンス項目:

| 項目 | 説明 |
| --- | --- |
| `id` | GridCell ID |
| `area` | 所属 MapArea ID |
| `row_index` | 0 始まりの行番号 |
| `col_index` | 0 始まりの列番号 |
| `north` / `south` / `east` / `west` | GridCell の緯度経度範囲 |
| `initial_score` | 初期スコア |
| `auto_score_breakdown` | 自動採点理由。ない場合は `null` |
| `average_user_score` | ユーザー採点だけの平均 |
| `rating_count` | ユーザー採点数 |
| `calculated_score` | 地図表示に使うスコア |
| `score_updated_at` | スコア更新日時。採点がない場合は `null` |
| `current_user_comment` | ログインユーザー自身のコメント。未採点時は空文字 |
| `current_user_has_rating` | ログインユーザー自身が採点済みかどうか |

### GridCell 生成

```text
POST /api/maps/areas/<area_id>/grids/
```

指定 MapArea の GridCell を生成します。
通常は `POST /api/maps/areas/` の作成処理で GridCell も生成されるため、画面の主導線では使いません。

作成者のみ実行できます。
作成者以外は `403 Forbidden` です。
既に GridCell がある場合など、生成できない条件では `400 Bad Request` になります。

## auto_score_breakdown

`auto_score_breakdown` は、自動設定時に GridCell ごとの自動採点内訳として保存される JSON です。
詳細画面の「自動採点理由」に使います。

主な項目:

| 項目 | 説明 |
| --- | --- |
| `base_score` | マス自体の基本点 |
| `diversity_bonus` | 要素の多様性による加点 |
| `context_bonus` | 周辺要素による加点 |
| `penalty` | 減点 |
| `raw_score` | clamp 前のスコア |
| `clamped_score` | 0.0〜3.0 に収めた自動初期スコア |
| `grid_size_multiplier` | マスサイズ補正係数 |
| `flags` | 採点理由の真偽値 |
| `bonuses` | 加点内訳 |
| `counts` | 件数・要素数 |

自動設定でない場合や、自動特徴を取得できなかった場合は `null` になる可能性があります。
自動採点では最終的に `0.0〜3.0` へ clamp します。

## 表示スコア計算

`calculated_score` は、地図上の色分けやスコア数値ラベルで使う表示スコアです。

現在の計算仕様:

```text
calculated_score = (initial_score + 全ユーザー採点の合計) / (1 + rating_count)
```

- `initial_score` を最初の1票として扱います。
- ユーザー採点が増えるほど、初期スコアの影響が自然に薄まります。
- `average_user_score` はユーザー採点だけの平均です。
- `rating_count` はユーザー採点数です。
- 採点がない場合は `calculated_score = initial_score` です。

## 採点 API

### 単体採点

```text
POST /api/maps/grids/<grid_id>/ratings/
```

対象 GridCell に対して、ログインユーザーの採点を作成または更新します。
同じユーザーが同じ GridCell へ複数回採点した場合は、新規行を増やさず既存採点を更新します。
採点後に対象 GridCell のスコア集計を更新します。

リクエスト:

```json
{
  "score": 8,
  "comment": "駅が近くて使いやすそう"
}
```

入力項目:

| 項目 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `score` | integer | 必須 | 1〜10 |
| `comment` | string | 任意 | コメント。空文字可 |

レスポンス:

```json
{
  "rating": {
    "id": 1,
    "grid": 1,
    "user": 1,
    "score": 8,
    "comment": "駅が近くて使いやすそう",
    "created_at": "2026-06-15T10:30:00+09:00",
    "updated_at": "2026-06-15T10:30:00+09:00"
  },
  "grid": {
    "id": 1,
    "area": 1,
    "row_index": 0,
    "col_index": 0,
    "initial_score": 2.0,
    "average_user_score": 8.0,
    "rating_count": 1,
    "calculated_score": 5.0,
    "current_user_comment": "駅が近くて使いやすそう",
    "current_user_has_rating": true
  }
}
```

ステータス:

| 状況 | ステータス |
| --- | --- |
| 初回採点 | `201 Created` |
| 既存採点更新 | `200 OK` |
| 入力不正 | `400 Bad Request` |
| GridCell なし / 権限なし | `404 Not Found` |

### 一括採点

```text
POST /api/maps/grids/bulk-ratings/
```

複数 GridCell に同じスコア・コメントをまとめて登録します。
権限のない GridCell には採点できません。
一部だけ採点して成功にはせず、権限なしや存在しない ID が含まれる場合は全体を `400 Bad Request` にします。

リクエスト:

```json
{
  "grid_ids": [1, 2, 3],
  "score": 7,
  "comment": "まとめて評価"
}
```

入力項目:

| 項目 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `grid_ids` | integer[] | 必須 | GridCell ID 配列。空配列不可 |
| `score` | integer | 必須 | 1〜10 |
| `comment` | string | 任意 | コメント。空文字可 |

`grid_ids` に重複 ID が含まれる場合、serializer 側で順序を保ったまま重複を取り除きます。
存在しない GridCell ID が含まれる場合は validation error です。

レスポンス:

```json
{
  "grids": [
    {
      "id": 1,
      "area": 1,
      "row_index": 0,
      "col_index": 0,
      "initial_score": 2.0,
      "average_user_score": 7.0,
      "rating_count": 1,
      "calculated_score": 4.5,
      "current_user_comment": "まとめて評価",
      "current_user_has_rating": true
    }
  ]
}
```

ステータス:

| 状況 | ステータス |
| --- | --- |
| すべて初回採点 | `201 Created` |
| 1件以上が既存採点更新 | `200 OK` |
| 入力不正 / 権限なし ID を含む | `400 Bad Request` |

## 共有 API

共有 API は作成者のみ利用できます。
共有されたユーザーは共有相手一覧の取得・追加・削除はできません。

### 共有相手一覧

```text
GET /api/maps/areas/<area_id>/shares/
```

レスポンス:

```json
{
  "area": {
    "id": 1,
    "name": "大阪駅周辺調査"
  },
  "shares": [
    {
      "id": 1,
      "area": 1,
      "user": {
        "id": 2,
        "username": "otheruser"
      },
      "created_at": "2026-06-15T11:00:00+09:00"
    }
  ]
}
```

### 共有相手追加

```text
POST /api/maps/areas/<area_id>/shares/
```

共有相手は `username` で指定します。

リクエスト:

```json
{
  "username": "otheruser"
}
```

レスポンス:

```json
{
  "share": {
    "id": 1,
    "area": 1,
    "user": {
      "id": 2,
      "username": "otheruser"
    },
    "created_at": "2026-06-15T11:00:00+09:00"
  }
}
```

追加できない例:

- 存在しない username
- 作成者自身
- 既に共有済みのユーザー

### 共有解除

```text
DELETE /api/maps/areas/<area_id>/shares/<share_id>/
```

指定した共有レコードを削除します。
成功時は `204 No Content` です。

## エラー・権限レスポンス

| 状況 | 主なステータス | 補足 |
| --- | --- | --- |
| 未認証 | `401 Unauthorized` | 認証情報がない |
| 入力不正 | `400 Bad Request` | serializer validation error など |
| 閲覧権限なし | `404 Not Found` | 対象の存在を推測しにくくする |
| 採点権限なし | `404 Not Found` または `400 Bad Request` | 単体採点は `404`、一括採点は `400` |
| 共有管理の権限なし | `404 Not Found` | 作成者だけが操作可能 |
| GridCell 生成権限なし | `403 Forbidden` | `POST /areas/<area_id>/grids/` の作成者以外 |
| 削除権限なし | `404 Not Found` | 作成者だけが削除可能 |
| Overpass 取得失敗 | 作成自体は継続 | fallback で GridCell を生成する場合がある |

## 実装しない・変更しない方針

- `north` / `south` / `east` / `west` の直接指定を作成 API の基本入力にはしない。
- 作成画面では `source` を主要入力として扱わない。
- 共有されたユーザーに共有管理や削除は許可しない。
- 自動設定時の画面側 2km 制限と、API 側の一般ユーザー制限を混同しない。
- model / migration の変更はこの仕様更新には含めない。
