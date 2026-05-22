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
| `POST` | `/api/maps/areas/{area_id}/grids/` | 地図範囲からグリッドを自動生成する | 必要 |
| `POST` | `/api/auth/token/` | Token 認証用 token を発行する | 不要 |

未実装 API 候補:

| メソッド | パス | 目的 | 認証 | 状態 |
| --- | --- | --- | --- | --- |
| `GET` | `/api/maps/grids/search/` | 周辺の高得点グリッドを検索する | 必要 | 未実装 |

## 認証

現在実装済みの地図 API はログイン必須です。

実装では各 view に次を設定しています。

```python
authentication_classes = [
    TokenAuthentication,
    BasicAuthentication,
    SessionAuthentication,
]
permission_classes = [IsAuthenticated]
```

初心者向け補足:

- 認証は「誰が使っているか」を確認する仕組みです。
- 権限は「その人が何をしてよいか」を確認する仕組みです。
- `BasicAuthentication` は、ユーザー名とパスワードを使う認証方式です。
- `SessionAuthentication` は、Django のログイン状態を使う認証方式です。
- `TokenAuthentication` は、発行済み token を HTTP ヘッダーで送る認証方式です。

現在は Basic 認証、Session 認証、Token 認証を併用します。
Basic 認証は開発確認用として当面残します。
JWT 認証はまだ実装しません。

### Token 発行 API

```text
POST /api/auth/token/
```

username/password から Token 認証用 token を発行します。

#### リクエスト

```json
{
  "username": "testuser",
  "password": "test-password"
}
```

#### レスポンス

```json
{
  "token": "xxxxxxxxxxxxxxxx"
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| token 発行成功 | `200 OK` |
| username/password が不正 | `400 Bad Request` |

#### Token 認証ヘッダー

Token 認証で既存 API を呼ぶ場合は、次の HTTP ヘッダーを送ります。

```http
Authorization: Token <TOKEN>
```

created_by ベースの権限チェックは、認証方式に関係なく同じです。
Basic 認証でも Token 認証でも、`request.user` が `MapArea.created_by` と一致するかで閲覧・採点可否を判断します。

## 実装済み: 採点 API の権限

単体採点 API と一括採点 API では、`GridCell.area.created_by` を使って採点できる対象を制限します。

採点できるのは、ログイン中ユーザーが作成した `MapArea` に属する `GridCell` だけです。

| 状況 | 結果 |
| --- | --- |
| 未ログイン | `401 Unauthorized` |
| `GridCell.area.created_by == request.user` | 採点許可 |
| `GridCell.area.created_by != request.user` | 採点不可 |
| `GridCell.area.created_by is None` | 採点不可 |

他ユーザーが作成した `MapArea` に属する `GridCell` や、`created_by` が `null` の `MapArea` に属する `GridCell` は採点できません。

単体採点 API では、採点不可の `GridCell` は存在しないものとして扱い、`404 Not Found` を返します。
一括採点 API では、採点不可の ID が 1 件でも含まれる場合、存在しない ID が含まれる場合と同じく、全体を `400 Bad Request` にします。

一括採点 API は、一部だけ採点して成功にはしません。
すべての `grid_ids` がログイン中ユーザーの `MapArea` に属している場合だけ、採点と点数再集計を実行します。

実装では、単体採点 API は次のように対象を絞ります。

```python
grid = get_object_or_404(GridCell, id=grid_id, area__created_by=request.user)
```

一括採点 API は、指定された `grid_ids` を `area__created_by=request.user` で絞り、取得できた件数が入力 ID 数と一致する場合だけ処理します。

## 実装済み: MapArea の閲覧権限

現在の MapArea 一覧 API、MapArea 詳細 API、点数付きグリッド一覧 API は、ログイン済みであれば他ユーザーが作成した `MapArea` も取得できる状態です。
今後は、`MapArea.created_by` を使って、作成者本人だけが自分の `MapArea` と紐づく `GridCell` を閲覧できる方針にします。

対象 API:

| メソッド | パス | 方針 |
| --- | --- | --- |
| `GET` | `/api/maps/areas/` | ログイン中ユーザーが作成した `MapArea` だけ返す |
| `GET` | `/api/maps/areas/{area_id}/` | ログイン中ユーザーが作成した `MapArea` だけ取得できる |
| `GET` | `/api/maps/areas/{area_id}/grids/` | ログイン中ユーザーが作成した `MapArea` の `GridCell` だけ取得できる |

### 基本方針

`MapArea.created_by` と `request.user` を比較します。

| 状況 | 結果 |
| --- | --- |
| 未ログイン | `401 Unauthorized` |
| `MapArea.created_by == request.user` | 閲覧許可 |
| `MapArea.created_by != request.user` | `404 Not Found` |
| `MapArea.created_by is None` | `404 Not Found` |

他ユーザーの `MapArea` や `created_by` が `null` の `MapArea` は、存在しないものとして扱います。
これは、他ユーザーのデータが存在すること自体をレスポンスから推測しにくくするためです。

GridCell 自動生成 API は「存在するが操作できない」ことを `403 Forbidden` で返します。
一方、閲覧 API は、一覧や詳細の取得範囲を `created_by=request.user` に絞るため、他ユーザーのデータは `404 Not Found` または一覧に出ない形にします。

### 実装方針

MapArea 一覧 API:

```python
areas = MapArea.objects.filter(created_by=request.user)
```

MapArea 詳細 API:

```python
area = get_object_or_404(MapArea, id=area_id, created_by=request.user)
```

点数付きグリッド一覧 API:

```python
area = get_object_or_404(MapArea, id=area_id, created_by=request.user)
grids = area.grid_cells.order_by("row_index", "col_index")
```

### レスポンス方針

MapArea 一覧 API:

- 自分が作成した `MapArea` だけ `areas` に含めます。
- 他ユーザーが作成した `MapArea` は含めません。
- `created_by is None` の `MapArea` も含めません。
- 対象が 0 件なら `areas: []` を返します。

MapArea 詳細 API:

- 自分が作成した `MapArea` なら `200 OK` を返します。
- 他ユーザーが作成した `MapArea` なら `404 Not Found` を返します。
- `created_by is None` の `MapArea` も `404 Not Found` を返します。

点数付きグリッド一覧 API:

- 自分が作成した `MapArea` なら、その `MapArea` に属する `GridCell` を返します。
- 他ユーザーが作成した `MapArea` なら `404 Not Found` を返します。
- `created_by is None` の `MapArea` も `404 Not Found` を返します。

### 今回は実装しないこと

- `maps/views.py` の変更
- `maps/tests.py` の変更
- `created_by` を必須にする model 変更
- migration の作成
- 管理者だけ全件閲覧できる特別ルール
- 共有用の MapArea や公開 MapArea の設計

`created_by` は現在 nullable です。
既存データや管理画面で作成者なしの `MapArea` が作られる可能性があるため、今回は閲覧 API からは見えない扱いにします。

## 設計メモ: MapArea のユーザー向け呼称

実装上の model 名や API 名は、当面 `MapArea` のままにします。
ただし、ユーザー画面や説明資料では、共有範囲に応じて次の呼称を使います。

| 用途 | ユーザー向け呼称 | 意味 |
| --- | --- | --- |
| 個人用 | メモグリッド | ユーザー本人だけが閲覧・採点する小さめの地図範囲 |
| ユーザー個人の間で共有 | 共有メモグリッド | 特定のユーザー同士で共有する地図範囲 |
| ユーザー全体用 | ワールドグリッド | ログインユーザー全体で閲覧・採点する広めの地図範囲 |

`MapArea` は内部実装名です。
画面表示では、ユーザーが触る意味に合わせて `メモグリッド`、`共有メモグリッド`、`ワールドグリッド` を使います。

現時点で実装済みなのは、作成者本人だけが扱える `メモグリッド` 相当の `MapArea` です。
`共有メモグリッド` と `ワールドグリッド` は今後の設計・実装対象です。

## 設計メモ: 共有 MapArea

将来的に、他ユーザーと共有できる `MapArea` を実装する想定です。
この時点では設計メモのみで、model 変更や migration 作成はまだ行いません。

この節の既存 `is_public` 方針は、主に `ワールドグリッド` を想定した初期案です。
今後 `共有メモグリッド` を実装する場合は、特定ユーザーだけを許可する共有メンバー管理も別途設計します。

### 共有メモグリッドの設計メモ

`共有メモグリッド` は、作成者が特定のユーザーにだけ共有する `MapArea` です。
ワールドグリッドのようにログインユーザー全員へ公開するものではありません。

想定する model 追加:

```python
class MapAreaShare(models.Model):
    area = models.ForeignKey(MapArea, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

`MapAreaShare` は、どの `MapArea` をどのユーザーに共有しているかを表します。
同じ `area` と `user` の組み合わせは重複できないようにします。

共有メモグリッドの権限方針:

| ユーザー | 閲覧 | 採点 | 共有相手の管理 | GridCell 自動生成 |
| --- | --- | --- | --- | --- |
| 作成者 | 可 | 可 | 可 | 可 |
| 共有されたユーザー | 可 | 可 | 不可 | 不可 |
| 共有されていないユーザー | 不可 | 不可 | 不可 | 不可 |

共有されたユーザーは閲覧と採点だけできます。
編集、削除、共有相手の追加・削除、GridCell 自動生成は作成者だけが実行できる方針です。

MapArea 一覧 API では、共有メモグリッドも判別できる形で返します。
一覧には少なくとも次のような表示用情報を含める想定です。

```json
{
  "areas": [
    {
      "id": 1,
      "name": "自分のメモ",
      "visibility": "private",
      "display_type": "メモグリッド",
      "is_owner": true,
      "created_by": 3
    },
    {
      "id": 2,
      "name": "友人から共有されたメモ",
      "visibility": "shared",
      "display_type": "共有メモグリッド",
      "is_owner": false,
      "created_by": 4
    }
  ]
}
```

`visibility` の想定値:

| 値 | 意味 |
| --- | --- |
| `private` | 自分が作成した個人用メモグリッド |
| `shared` | 他ユーザーから共有された共有メモグリッド |
| `world` | ログインユーザー全体用のワールドグリッド |

`display_type` は UI 表示用の呼称です。
API の内部名は引き続き `MapArea` のままにします。

一覧 API の取得対象は、将来的に次の合算にします。

```text
自分が作成した MapArea
+ MapAreaShare で自分に共有された MapArea
+ ワールドグリッドとして公開された MapArea
```

同じ `MapArea` が複数条件に当てはまる場合は重複させず、1 件だけ返します。

### 想定する model 変更

将来的に `MapArea` に次のようなフィールドを追加する想定です。

```python
is_public = models.BooleanField(default=False)
```

`is_public` は、その `MapArea` を他ユーザーにも共有するかどうかを表します。

### 権限方針

| 状況 | 閲覧 | 採点 |
| --- | --- | --- |
| `is_public=False` | 作成者本人だけ可 | 作成者本人だけ可 |
| `is_public=True` | ログインユーザー全員可 | ログインユーザー全員可 |

`is_public=False` は、現在の仕様と同じく `created_by == request.user` の場合だけ閲覧・採点できます。
`is_public=True` は、ログインユーザー全員が閲覧・採点できます。

### API ごとの方針

MapArea 一覧 API:

- 自分が作成した `MapArea` を返します。
- `is_public=True` の `MapArea` も返します。
- つまり、一覧 API は「自分の `MapArea` + public `MapArea`」を返します。

MapArea 詳細 API:

- 自分が作成した `MapArea` は取得できます。
- `is_public=True` の `MapArea` も取得できます。
- どちらにも当てはまらない `MapArea` は `404 Not Found` として扱います。

点数付きグリッド一覧 API:

- 自分が作成した `MapArea` の `GridCell` は取得できます。
- `is_public=True` の `MapArea` の `GridCell` も取得できます。

単体採点 API / 一括採点 API:

- 自分が作成した `MapArea` に属する `GridCell` は採点できます。
- `is_public=True` の `MapArea` に属する `GridCell` もログインユーザー全員が採点できます。
- `GridRating` は現在どおり、1 ユーザーにつき 1 `GridCell` 1 採点の制約を使います。

GridCell 自動生成 API:

- `is_public` の値に関係なく、作成者本人だけ実行できます。
- 共有 MapArea であっても、他ユーザーは GridCell 自動生成を実行できません。
- 理由は、GridCell 自動生成は既存のグリッド構成や採点結果に影響し得る操作だからです。

### `created_by=None` の扱い

`created_by=None` の `MapArea` は public 扱いしません。

理由:

- 管理画面や古いデータで作成者なしの `MapArea` ができる可能性があるため。
- `created_by=None` を共有扱いにすると、意図せず全ユーザーに公開される危険があるため。

そのため、`created_by=None` かつ `is_public=False` の `MapArea` は、通常ユーザーからは見えない扱いにします。

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

#### 権限

採点できるのは、自分が作成した `MapArea` に属する `GridCell` だけです。

他ユーザーが作成した `MapArea` に属する `GridCell` や、`created_by` が `null` の `MapArea` に属する `GridCell` は、存在しないものとして扱い `404 Not Found` を返します。

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
| 他ユーザーの `GridCell` を指定した | `404 Not Found` |
| `created_by` が `null` の `MapArea` に属する `GridCell` を指定した | `404 Not Found` |
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

#### 権限

採点できるのは、自分が作成した `MapArea` に属する `GridCell` だけです。

`grid_ids` に他ユーザーの `GridCell` や、`created_by` が `null` の `MapArea` に属する `GridCell` が 1 件でも含まれる場合は、全体を `400 Bad Request` にします。

一括採点 API では、一部だけ採点して成功にはしません。
すべての `grid_ids` が採点可能な場合だけ、`GridRating` の作成または更新と `GridCell` の点数再集計を実行します。

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
| `grid_ids` に他ユーザーの `GridCell` がある | `400 Bad Request` |
| `grid_ids` に `created_by` が `null` の `MapArea` に属する `GridCell` がある | `400 Bad Request` |
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

#### 表示方針メモ

- demo ページの Score Map では、`calculated_score` を各マスのメイン表示に使います。
- `GridCell ID` と `row_index` / `col_index` は、現在は確認用に小さく表示します。
- demo ページでは、MapArea の `north`, `south`, `east`, `west` を使って Score Map の概算縦横比を決めます。
- demo ページでは、任意の画像 URL を Score Map の背景として指定できます。
- 背景画像指定は表示確認用であり、画像アップロードや外部地図 API 連携は行いません。
- 現時点では正確な地図投影は行わず、`row_index` / `col_index` による簡易グリッド配置を維持します。
- この表示改善では API レスポンス形式は変更しません。

### GridCell 自動生成 API

```text
POST /api/maps/areas/{area_id}/grids/
```

指定した `MapArea` から `GridCell` を自動生成する API です。
`MapArea.north`, `south`, `east`, `west`, `grid_size_meters` をもとに、`generate_grid_cells_for_area(area)` service を呼び出します。

#### 認証

ログイン必須です。

#### 権限

対象 `MapArea` の作成者本人だけが GridCell を生成できます。
具体的には、`MapArea.created_by` とログイン中ユーザー `request.user` が同じ場合だけ生成を許可します。

| 状況 | 結果 |
| --- | --- |
| `MapArea.created_by == request.user` | 生成許可 |
| `MapArea.created_by != request.user` | `403 Forbidden` |
| `MapArea.created_by is None` | `403 Forbidden` |

初心者向け補足:

- 認証は「誰が使っているか」を確認する仕組みです。
- 権限は「その人が何をしてよいか」を確認する仕組みです。
- `created_by` は、その `MapArea` を作成したユーザーです。
- `request.user` は、今 API を使っているログイン中ユーザーです。

#### URL パラメータ

| 名前 | 型 | 内容 |
| --- | --- | --- |
| `area_id` | integer | グリッドを生成する対象の `MapArea` ID |

#### リクエスト

リクエストボディはありません。

#### レスポンス

生成に成功した場合は、対象エリアと生成されたグリッド一覧を返します。

```json
{
  "area": {
    "id": 1,
    "name": "東京駅周辺"
  },
  "grids": [
    {
      "id": 10,
      "area": 1,
      "row_index": 0,
      "col_index": 0,
      "north": 35.7,
      "south": 35.6954954954955,
      "east": 139.7045045045045,
      "west": 139.7,
      "initial_score": 0.0,
      "average_user_score": 0.0,
      "rating_count": 0,
      "calculated_score": 0.0,
      "score_updated_at": null
    }
  ]
}
```

`grids` は次の順に並びます。

1. `row_index`
2. `col_index`

#### エラーレスポンス

既に対象 `MapArea` に `GridCell` がある場合など、service が `ValueError` を返した場合は `detail` に理由を入れます。

```json
{
  "detail": "この MapArea には既に GridCell があります。"
}
```

作成者本人ではない場合や、`created_by` が `null` の場合も `detail` に理由を入れます。

```json
{
  "detail": "この MapArea の GridCell を生成する権限がありません。"
}
```

#### ステータスコード

| 状況 | ステータス |
| --- | --- |
| 生成成功 | `201 Created` |
| 未ログイン | `401 Unauthorized` |
| `area_id` が存在しない | `404 Not Found` |
| `MapArea.created_by != request.user` | `403 Forbidden` |
| `MapArea.created_by is None` | `403 Forbidden` |
| 既に `GridCell` がある | `400 Bad Request` |
| service の入力チェックで不正値 | `400 Bad Request` |

#### 注意点

- 作成者本人ではないユーザーは `GridCell` を生成できません。
- `created_by` が `null` の `MapArea` でも `GridCell` を生成できません。
- 既に `GridCell` がある `MapArea` では、新しい `GridCell` を追加しません。
- 重複生成を防ぎ、既存の採点や集計値を壊さないためです。
- この API では外部地図 API は使いません。
- `initial_score` はまず `0` で生成します。
- 正確な地球測地計算はまだ行いません。

### MapArea 作成 API

```text
POST /api/maps/areas/
```

ログイン中ユーザーが、新しい `MapArea` を作成する API です。

この API では地図範囲を保存したあと、同じリクエスト処理内で `GridCell` も自動生成します。
GridCell 生成には既存の `generate_grid_cells_for_area(area)` service を使います。

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
| 一般ユーザーが緯度差または経度差 20 分を超える範囲を作成しようとした | `400 Bad Request` |
| 必須項目がない | `400 Bad Request` |

#### 作成可能範囲の制限

一般ユーザーは、緯度差または経度差が 20 分を超える `MapArea` を作成できません。
20 分は `20 / 60` 度、つまり約 `0.333333` 度として扱います。

判定に使う値:

```text
latitude_diff = north - south
longitude_diff = east - west
limit = 20 / 60
```

| ユーザー | 条件 | 結果 |
| --- | --- | --- |
| 一般ユーザー | `latitude_diff <= limit` かつ `longitude_diff <= limit` | 作成許可 |
| 一般ユーザー | `latitude_diff > limit` または `longitude_diff > limit` | `400 Bad Request` |
| 管理者 | 範囲の大きさに関係なく作成可 | 作成許可 |

管理者判定は、Django 標準の `request.user.is_staff` を使う方針です。
この制限は、巨大な `MapArea` 作成によって `GridCell` が大量生成されることを防ぐために入れます。
大阪市のような一定以上の広さを持つ共有用 `MapArea` は、管理者が作成する想定です。

エラーレスポンス例:

```json
{
  "detail": "一般ユーザーは緯度差・経度差が20分を超えるMapAreaを作成できません。"
}
```

初心者向け補足:

- バリデーションは、変なデータを DB に保存しないためのチェックです。
- `north > south` と `east > west` を確認するのは、地図範囲として上下左右が逆にならないようにするためです。
- `grid_size_meters` が 0 以下だと、グリッドの大きさとして使えないためエラーにします。
- `is_staff` は Django のユーザーにある管理者向けフラグで、管理画面を使える運用担当者かどうかの判断に使えます。

#### レスポンス

作成に成功した場合は、作成された `MapArea` を返します。
生成された GridCell はレスポンスに含めず、点数付きグリッド一覧 API で取得します。

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
| GridCell 生成に失敗した | `400 Bad Request` |

#### GridCell 自動生成の扱い

- `MapArea.created_by` はログイン中ユーザーをサーバー側で設定します。
- GridCell は、作成された `MapArea` に紐づけて自動生成します。
- MapArea 作成と GridCell 生成は 1 つの transaction でまとめます。
- GridCell 生成に失敗した場合、MapArea だけが保存される状態にはしません。
- 作成後の GridCell は `GET /api/maps/areas/{area_id}/grids/` で確認できます。
- 既存の `POST /api/maps/areas/{area_id}/grids/` は残します。
- 既に GridCell がある MapArea に対して自動生成 API を実行した場合は `400 Bad Request` を返します。

初心者向け補足:

- transaction は、複数の DB 操作をひとまとまりとして扱う仕組みです。
- 今回は「MapArea は作れたが GridCell は作れなかった」という中途半端な状態を避けるために使います。

#### 今回は実装しないこと

- 同じ名前の `MapArea` を許可するかどうか
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

## 実装済み service: GridCell 自動生成

### 目的

`MapArea` の緯度経度範囲と `grid_size_meters` をもとに、`GridCell` を自動生成するための service です。
`POST /api/maps/areas/` と `POST /api/maps/areas/{area_id}/grids/` から呼び出します。

初心者向け補足:

- service は、view から切り出した共通処理を置く場所です。
- view はリクエストを受け取りレスポンスを返す処理です。
- グリッドは、地図を一定の大きさに区切った 1 マスです。

### service 名

```python
generate_grid_cells_for_area(map_area)
```

### 入力

| 項目 | 内容 |
| --- | --- |
| `map_area` | `MapArea` instance |

`map_area` の存在確認は、基本的には API 側で行います。
たとえば `area_id` が存在しない場合は、view 側で `404 Not Found` にする想定です。

### 出力

生成して DB に保存した `GridCell` の一覧を返します。

例:

```python
[grid_cell_1, grid_cell_2, grid_cell_3]
```

GridCell 自動生成 API では、この一覧を serializer で JSON に変換して返します。
serializer は、Python のデータと JSON の変換を担当する部品です。

### 使用する MapArea の値

| フィールド | 内容 |
| --- | --- |
| `north` | 地図範囲の北端 |
| `south` | 地図範囲の南端 |
| `east` | 地図範囲の東端 |
| `west` | 地図範囲の西端 |
| `grid_size_meters` | 1 マスの大きさ |

### 生成する GridCell の項目

| フィールド | 方針 |
| --- | --- |
| `area` | 対象の `MapArea` |
| `row_index` | 上から何行目か。0 始まり |
| `col_index` | 左から何列目か。0 始まり |
| `north` | そのマスの北端 |
| `south` | そのマスの南端 |
| `east` | そのマスの東端 |
| `west` | そのマスの西端 |
| `initial_score` | まずは `0` |
| `average_user_score` | 初期値 `0` |
| `rating_count` | 初期値 `0` |
| `calculated_score` | まずは `initial_score` と同じ `0` |
| `score_updated_at` | `null` |

`GridCell` には集計済みの表示用スコアを保存します。
採点データそのものは `GridRating` に保存するため、自動生成時点では採点数は 0 件です。

### 緯度経度の簡易計算方針

最初の学習用実装では、厳密な地球測地計算ではなく簡易計算を使います。

```text
1 度の緯度は約 111,000m として扱う
緯度方向の 1 マス = grid_size_meters / 111000
経度方向も最初は同じ近似値を使う
```

計算例:

```python
lat_step = map_area.grid_size_meters / 111000
lng_step = map_area.grid_size_meters / 111000
```

注意点:

- 緯度は北南方向の位置です。
- 経度は東西方向の位置です。
- 経度 1 度あたりの距離は、本来は緯度によって変わります。
- そのため、この計算は学習用の簡易実装です。
- より正確な計算は、別タスクで扱います。

### 行数・列数の計算方針

`MapArea` 全体を覆えるように、行数と列数は切り上げで計算します。

```python
row_count = ceil((map_area.north - map_area.south) / lat_step)
col_count = ceil((map_area.east - map_area.west) / lng_step)
```

`ceil` は、小数を切り上げる処理です。
たとえば `2.1` は `3` になります。
範囲が 2.1 マス分ある場合に 2 マスだけ作ると端が足りなくなるため、切り上げます。

### 端のグリッドの扱い

範囲ぴったりに割り切れない場合、最後の行や列は `MapArea` の境界に合わせて小さめのグリッドにします。
これにより、生成した `GridCell` が `MapArea` の範囲外にはみ出さないようにします。

```python
cell_north = map_area.north - row_index * lat_step
cell_south = max(map_area.south, cell_north - lat_step)

cell_west = map_area.west + col_index * lng_step
cell_east = min(map_area.east, cell_west + lng_step)
```

行と列の考え方:

- `row_index` は上から下へ増えます。
- `col_index` は左から右へ増えます。
- 北端から南へ進むため、緯度は `north` から引き算します。
- 西端から東へ進むため、経度は `west` に足し算します。

### 既存 GridCell がある場合の扱い

安全のため、対象の `MapArea` に `GridCell` が 1 件以上ある場合は新規生成しません。
service 側でエラーにする方針です。

理由:

- 重複生成を防ぐため
- 既存の採点や集計値を壊さないため
- 削除して再生成する処理は影響が大きいため、別タスクで扱うため

想定する確認:

```python
if map_area.grid_cells.exists():
    raise ValueError("この MapArea には既に GridCell があります。")
```

API 側では、この `ValueError` を `400 Bad Request` として扱います。

### 想定エラー

| 状況 | 方針 |
| --- | --- |
| `map_area` が存在しない | API 側で `404 Not Found` にする |
| 対象 `MapArea` に既に `GridCell` がある | service でエラーにする |
| `grid_size_meters <= 0` | model 制約上は保存できない想定だが、service 側でも念のためエラー候補 |
| `north <= south` | model 制約上は保存できない想定 |
| `east <= west` | model 制約上は保存できない想定 |

model は DB のテーブル設計に対応します。
現在の `MapArea` model には `north > south`、`east > west`、`grid_size_meters > 0` の制約があります。
ただし service を安全に使うため、実装時には service 側でも入力チェックを検討します。

### この service ではやらないこと

- `models.py` の変更
- migration の作成
- 外部地図 API の利用
- 正確な地球測地計算
- 地形情報や観光情報からの `initial_score` 計算
- 認証方式の変更
- 依存関係の追加

migration は、model の変更を DB に反映するための履歴です。
この service では model を変えないため、migration も作りません。

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
