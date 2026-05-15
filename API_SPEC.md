# API_SPEC.md

このファイルは、地図採点 API の仕様を整理するための設計メモです。
現時点では仕様未定の点が多いため、実装済み API ではなく「これから作る API のたたき台」として扱います。

## 目的

地図を一定距離幅のグリッドに分割し、各グリッドに点数を付けます。
ユーザーはグリッドを採点でき、システムは初期点数やユーザー採点をもとに表示用の点数を計算します。
最終的には、具体的な観光情報を見すぎず、点数を手がかりに気ままに旅先を選べる API を目指します。

## 現時点の仮定

- Django REST Framework で API を作る
- 最初はローカル開発環境または Google Colab で検証する
- 地図データの取得元は未定
- グリッドの大きさは未定
- 点数の範囲は仮に 1 から 10 とする
- 集計方法は仮に平均値とする
- 認証方式は未定だが、ユーザー採点には認証が必要になる想定
- 地図 API キーなどの秘密情報は `.env` で管理し、コードには直接書かない

## 用語

| 用語 | 意味 |
| --- | --- |
| Map Area | 地図として扱う対象範囲 |
| Grid Cell | 地図を一定距離幅で分割した 1 マス |
| Initial Score | 地形情報などからシステムが最初に付ける点数 |
| User Rating | ユーザーがグリッドに付ける点数 |
| Calculated Score | 初期点数とユーザー採点から計算した表示用点数 |

## モデル設計案

この設計案は、まだ `models.py` には反映しません。
まずは DB の形を学習しながら確認するためのたたき台です。

### 全体の関係

```text
User
  └─ GridRating
       └─ GridCell
            └─ MapArea
```

見方を変えると、次の関係になります。

```text
MapArea 1件
  └─ GridCell 複数件
       └─ GridRating 複数件
            └─ User 1人
```

### MapArea

`MapArea` は、地図全体の対象範囲を表します。
たとえば「東京駅周辺」や「京都市中心部」のように、グリッド分割する元の範囲です。

| フィールド | 型の候補 | 必須 | 役割 |
| --- | --- | --- | --- |
| `name` | 文字列 | 必須 | 地図範囲の名前 |
| `description` | 長い文字列 | 任意 | 地図範囲の説明やメモ |
| `north` | 小数 | 必須 | 北端の緯度 |
| `south` | 小数 | 必須 | 南端の緯度 |
| `east` | 小数 | 必須 | 東端の経度 |
| `west` | 小数 | 必須 | 西端の経度 |
| `grid_size_meters` | 整数 | 必須 | グリッド 1 マスの大きさ |
| `source` | 文字列 | 任意 | 地図データの取得元 |
| `created_by` | User への外部キー | 任意 | この地図範囲を作成したユーザー |
| `created_at` | 日時 | 必須 | 作成日時 |
| `updated_at` | 日時 | 必須 | 更新日時 |

設計上の注意:

- `north` は `south` より大きい必要があります。
- `east` は `west` より大きい必要があります。
- `grid_size_meters` は 0 より大きい値にします。

### GridCell

`GridCell` は、`MapArea` を分割した 1 マスを表します。
複数ユーザーの採点結果そのものは `GridRating` に保存し、`GridCell` には集計済みの表示用スコアを保存します。

| フィールド | 型の候補 | 必須 | 役割 |
| --- | --- | --- | --- |
| `area` | MapArea への外部キー | 必須 | どの地図範囲に属するか |
| `row_index` | 整数 | 必須 | 上から何行目のグリッドか |
| `col_index` | 整数 | 必須 | 左から何列目のグリッドか |
| `north` | 小数 | 必須 | グリッド北端の緯度 |
| `south` | 小数 | 必須 | グリッド南端の緯度 |
| `east` | 小数 | 必須 | グリッド東端の経度 |
| `west` | 小数 | 必須 | グリッド西端の経度 |
| `initial_score` | 小数 | 必須 | 地形情報などから付ける初期点数 |
| `average_user_score` | 小数 | 必須 | ユーザー採点の平均点 |
| `rating_count` | 整数 | 必須 | 採点したユーザー数 |
| `calculated_score` | 小数 | 必須 | 表示用に計算した最終点数 |
| `score_updated_at` | 日時 | 任意 | 集計点を最後に更新した日時 |
| `created_at` | 日時 | 必須 | 作成日時 |
| `updated_at` | 日時 | 必須 | 更新日時 |

設計上の注意:

- 同じ `MapArea` の中で、`row_index` と `col_index` の組み合わせは重複させません。
- `average_user_score` は `GridRating.score` の平均です。
- `rating_count` はそのグリッドに紐づく `GridRating` の件数です。
- `calculated_score` は、初期点数とユーザー平均点から計算する表示用の点数です。

暫定の計算式:

```text
average_user_score = GridRating.score の平均
rating_count = GridRating の件数
calculated_score = (initial_score + average_user_score) / 2
```

### GridRating

`GridRating` は、ユーザー 1 人分の採点を表します。
複数ユーザーが同じ `GridCell` を採点できるように、採点データは `GridCell` とは別モデルにします。

| フィールド | 型の候補 | 必須 | 役割 |
| --- | --- | --- | --- |
| `grid` | GridCell への外部キー | 必須 | どのグリッドへの採点か |
| `user` | User への外部キー | 必須 | 誰が採点したか |
| `score` | 整数 | 必須 | ユーザーが付けた点数 |
| `comment` | 長い文字列 | 任意 | 採点理由やメモ |
| `created_at` | 日時 | 必須 | 作成日時 |
| `updated_at` | 日時 | 必須 | 更新日時 |

設計上の注意:

- `score` は暫定で 1 から 10 の整数にします。
- 同じ `grid` と `user` の組み合わせは重複させません。
- 同じユーザーが同じグリッドを再採点した場合は、新しい行を追加せず既存の `GridRating` を更新します。
- 採点履歴は今回は保存しません。必要になったら `GridRatingHistory` を追加する方針にします。

### User と GridRating の関係

Django 標準の `User` を使う想定です。
`GridRating.user` があることで、「誰が」「どのグリッドに」「何点を付けたか」を保存できます。

```text
ユーザーA -> Grid 1 に 4点
ユーザーB -> Grid 1 に 2点
ユーザーC -> Grid 1 に 5点
```

この場合、`GridCell` は次のように集計できます。

```text
average_user_score = 3.67
rating_count = 3
calculated_score = initial_score と average_user_score から再計算
```

### 複数ユーザー採点時の処理方針

採点操作が行われるたびに、対象の `GridCell` の集計値を再計算します。

1. ユーザーがグリッドに点数を付ける
2. `GridRating` を作成または更新する
3. 対象 `GridCell` に紐づく全 `GridRating` を集計する
4. `average_user_score` を更新する
5. `rating_count` を更新する
6. `calculated_score` を更新する
7. `score_updated_at` を更新する

学習用の最初の実装では、採点 API の中でその都度再計算する方針にします。
本格運用を考える段階では、同時更新への対策として DB トランザクションやロックを検討します。

### 初心者向け説明

`model` は DB のテーブル設計に対応します。
今回なら `MapArea`、`GridCell`、`GridRating` という 3 つのテーブルを作るイメージです。

`ForeignKey` は別のモデルとのつながりを表します。
たとえば `GridCell.area` は「このグリッドはどの地図範囲に属しているか」を表します。

`GridCell` は地図を分割した 1 マスです。
地図上に色を付けたり、点数を表示したりする対象になります。

`GridRating` はユーザー 1 人分の採点です。
複数ユーザーの点数を扱うため、点数は `GridCell` に直接 1 つだけ保存せず、`GridRating` に分けて保存します。

`grid + user` を重複禁止にする理由は、同じユーザーが同じグリッドに何件も採点データを作ってしまうのを防ぐためです。
再採点したい場合は、既存の `GridRating` を更新します。

平均点と件数を再計算する理由は、複数ユーザーの採点結果を `GridCell` に表示しやすくするためです。
API でグリッド一覧を返すとき、毎回すべての採点を数え直さなくても、`GridCell` の集計済みフィールドを見れば表示できます。

## Serializer 設計案

この設計案は、まだ `maps/serializers.py` には反映しません。
採点 API を実装する前に、入力と出力の形を整理するためのメモです。

serializer は、Django の model など Python 側のデータと、API で使う JSON を変換する部品です。
また、不正な入力を防ぐバリデーションも担当します。

### GridRatingCreateSerializer

1 つのグリッドを採点するときの入力用 serializer です。

想定する API:

```text
POST /api/maps/grids/{grid_id}/ratings/
```

入力項目:

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `score` | 必須 | ユーザーが付ける 1 から 10 の点数 |
| `comment` | 任意 | 採点理由やメモ |

クライアントから送らせない項目:

| 項目 | 理由 |
| --- | --- |
| `grid` | URL の `grid_id` から取得するため |
| `user` | ログイン中ユーザーから取得するため |

バリデーション方針:

- `score` が 1 から 10 の範囲外ならエラーにする。
- `comment` は空でもよい。
- URL の `grid_id` に対応する `GridCell` が存在しない場合はエラーにする。
- ログインしていないユーザーは採点できない。
- 同じユーザーが同じグリッドを再採点した場合は、新しい `GridRating` を作らず既存データを更新する。

レスポンス方針:

- 作成または更新した採点結果は、`GridRatingResponseSerializer` の形で返す。
- 採点後の集計済みグリッド情報も返したい場合は、後続でレスポンス全体の形を検討する。

### GridRatingResponseSerializer

採点結果を返すための出力用 serializer です。

出力項目:

| 項目 | 内容 |
| --- | --- |
| `id` | 採点データの ID |
| `grid` | 採点対象の GridCell ID |
| `user` | 採点した User ID |
| `score` | 採点 |
| `comment` | 採点理由やメモ |
| `created_at` | 作成日時 |
| `updated_at` | 更新日時 |

設計方針:

- 最初は `user` を ID で返す。
- ユーザー名を返したくなったら、後続で `username` などの表示用項目を追加する。
- `grid` も最初は ID で返し、詳細なグリッド情報が必要な場合は `GridCellScoreSerializer` と組み合わせる。

### GridCellScoreSerializer

点数付きのグリッド情報を返すための serializer です。
採点後に更新された `GridCell` の集計値を返す用途を想定します。

出力項目:

| 項目 | 内容 |
| --- | --- |
| `id` | GridCell ID |
| `area` | 所属する MapArea ID |
| `row_index` | 上から何行目か |
| `col_index` | 左から何列目か |
| `north` | グリッド北端の緯度 |
| `south` | グリッド南端の緯度 |
| `east` | グリッド東端の経度 |
| `west` | グリッド西端の経度 |
| `initial_score` | 初期点数 |
| `average_user_score` | ユーザー採点の平均点 |
| `rating_count` | 採点数 |
| `calculated_score` | 表示用の最終点数 |
| `score_updated_at` | 集計点の最終更新日時 |

設計方針:

- 地図上で色分け表示しやすいように `calculated_score` を必ず含める。
- 採点後のレスポンスや、点数付きグリッド一覧 API で使う。
- `rating_count` が 0 の場合でも、初期値として `0` を返す。

### BulkGridRatingSerializer

複数のグリッドをまとめて同じ点数で採点するときの入力用 serializer です。

想定する API:

```text
POST /api/maps/grids/bulk-ratings/
```

入力項目:

| 項目 | 必須 | 内容 |
| --- | --- | --- |
| `grid_ids` | 必須 | 採点対象の GridCell ID の配列 |
| `score` | 必須 | まとめて付ける 1 から 10 の点数 |
| `comment` | 任意 | 採点理由やメモ |

バリデーション方針:

- `grid_ids` が空配列ならエラーにする。
- `grid_ids` に存在しない ID が含まれる場合はエラーにする。
- `grid_ids` に重複がある場合は、重複を取り除いて処理する方針にする。
- `score` が 1 から 10 の範囲外ならエラーにする。
- `comment` は空でもよい。
- ログインしていないユーザーは採点できない。
- 既に採点済みのグリッドは、新規作成ではなく既存の `GridRating` を更新する。

レスポンス方針:

- 更新された `GridCell` の一覧を `GridCellScoreSerializer` の形で返す案を基本にする。
- 個々の `GridRating` を返すかどうかは、view 設計時に決める。

### 入力用と出力用を分ける理由

入力用 serializer は、ユーザーから受け取る値を確認するためのものです。
たとえば `score` が 1 から 10 に入っているかを確認します。

出力用 serializer は、API の返事として何を見せるかを整えるためのものです。
たとえば採点結果だけ返すのか、採点後のグリッド点数まで返すのかを分けて考えられます。

`grid` と `user` をクライアントから送らせない理由は、不正な採点を防ぐためです。
もし `user` を自由に送れてしまうと、別ユーザーになりすまして採点できる危険があります。
そのため、`user` はログイン情報からサーバー側で決めます。
`grid` も URL の `grid_id` から決めることで、入力 JSON をシンプルにできます。

### Serializer の未決定事項

- 採点後のレスポンスを `GridRating` だけにするか、更新後の `GridCell` も含めるか。
- `BulkGridRatingSerializer` で一部の `grid_id` だけ不正だった場合に、全体をエラーにするか、正しいものだけ処理するか。
- `user` を ID だけで返すか、`username` も返すか。
- `comment` の最大文字数を決めるか。
- 再採点時に `created_at` と `updated_at` の意味をどう説明するか。

## View 設計案

この設計案は、まだ `maps/views.py` には反映しません。
採点 API の処理手順、レスポンス、エラー方針を先に整理するためのメモです。

view は、リクエストを受け取り、必要な model や serializer を使って処理し、レスポンスを返す場所です。
serializer が「入力や出力の形」を担当するのに対して、view は「どの順番で処理するか」を担当します。

### 単体採点 API

1 つの `GridCell` に対して、ログイン中ユーザーが点数を付ける API です。

想定する API:

```text
POST /api/maps/grids/{grid_id}/ratings/
```

使用する serializer:

| 用途 | serializer |
| --- | --- |
| 入力チェック | `GridRatingCreateSerializer` |
| 採点結果の出力 | `GridRatingResponseSerializer` |
| 更新後グリッド点数の出力 | `GridCellScoreSerializer` |

リクエスト例:

```json
{
  "score": 8,
  "comment": "水辺が近くて良さそう"
}
```

処理手順:

1. ログイン済みユーザーか確認する。
2. URL の `grid_id` から `GridCell` を取得する。
3. `GridRatingCreateSerializer` で `score` と `comment` を検証する。
4. `GridRating` を作成または更新する。
5. 同じユーザーが同じグリッドを採点済みなら、既存の `GridRating` を更新する。
6. 対象 `GridCell` の集計値を再計算する。
7. `GridRatingResponseSerializer` と `GridCellScoreSerializer` でレスポンスを作る。

レスポンス例:

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

ステータスコード方針:

| 状況 | ステータス | 内容 |
| --- | --- | --- |
| 初回採点を作成した | `201 Created` | 新しい `GridRating` を作成した |
| 既存採点を更新した | `200 OK` | 既存の `GridRating` を更新した |
| 未ログイン | `401 Unauthorized` | ログインが必要 |
| `grid_id` が存在しない | `404 Not Found` | 対象グリッドが存在しない |
| `score` が範囲外 | `400 Bad Request` | 入力値が不正 |
| `score` がない | `400 Bad Request` | 必須項目が不足 |

### 再採点の扱い

同じユーザーが同じ `GridCell` を再採点した場合は、新しい `GridRating` を作りません。
既存の `GridRating` の `score` と `comment` を更新します。

理由:

- `grid + user` の重複禁止制約と合う。
- 1 ユーザー 1 グリッドにつき現在の採点を 1 件だけ持てる。
- 平均点を計算するとき、同じユーザーの古い点数が重複して混ざるのを防げる。

### 集計処理との関係

採点 API は、`GridRating` の作成または更新後に `GridCell` の集計値を再計算する必要があります。

更新する値:

- `average_user_score`
- `rating_count`
- `calculated_score`
- `score_updated_at`

暫定の計算式:

```text
average_user_score = GridRating.score の平均
rating_count = GridRating の件数
calculated_score = (initial_score + average_user_score) / 2
```

ただし、集計処理の実装場所は次のタスクで決めます。
候補は `maps/services.py` に関数として分ける方法です。

### 一括採点 API

複数の `GridCell` に同じ点数をまとめて付ける API です。
単体採点 API より処理が複雑になるため、実装は後続タスクに分けます。

想定する API:

```text
POST /api/maps/grids/bulk-ratings/
```

使用する serializer:

| 用途 | serializer |
| --- | --- |
| 入力チェック | `BulkGridRatingSerializer` |
| 更新後グリッド点数の出力 | `GridCellScoreSerializer` |

処理手順案:

1. ログイン済みユーザーか確認する。
2. `BulkGridRatingSerializer` で `grid_ids`、`score`、`comment` を検証する。
3. 重複した `grid_ids` は serializer 側で取り除く。
4. 各 `GridCell` について `GridRating` を作成または更新する。
5. 各 `GridCell` の集計値を再計算する。
6. 更新後の `GridCell` 一覧を返す。

レスポンス方針:

- 更新された `GridCell` の一覧を返す。
- 個々の `GridRating` 一覧は、必要になったら追加する。

### 点数付きグリッド一覧 API

指定した `MapArea` に属する `GridCell` 一覧を、地図表示に使いやすい点数付きの形で返す API です。

想定する API:

```text
GET /api/maps/areas/{area_id}/grids/
```

使用する serializer:

| 用途 | serializer |
| --- | --- |
| グリッド点数の出力 | `GridCellScoreSerializer` |

リクエストボディ:

```text
なし
```

処理手順:

1. ログイン済みユーザーか確認する。
2. URL の `area_id` から `MapArea` を取得する。
3. 対象 `MapArea` に属する `GridCell` 一覧を取得する。
4. `row_index`、`col_index` の順に並べる。
5. `GridCellScoreSerializer` でレスポンスを作る。

レスポンス例:

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
      "score_updated_at": "2026-05-15T10:05:00+09:00"
    }
  ]
}
```

ステータスコード方針:

| 状況 | ステータス | 内容 |
| --- | --- | --- |
| 一覧を取得できた | `200 OK` | 対象 `MapArea` の `GridCell` 一覧を返す |
| 未ログイン | `401 Unauthorized` | ログインが必要 |
| `area_id` が存在しない | `404 Not Found` | 対象の地図範囲が存在しない |

グリッドが 0 件の場合:

```json
{
  "area": {
    "id": 1,
    "name": "Manual Test Area"
  },
  "grids": []
}
```

設計方針:

- 地図上でマスを描画しやすいように、各 `GridCell` の緯度経度、行番号、列番号、点数を返す。
- `GridCellScoreSerializer` を使い、採点 API のレスポンスとグリッド情報の形をそろえる。
- 採点数が 0 件のグリッドも返す。未採点の場所も地図上に表示する必要があるため。
- `calculated_score` は地図上の色分けに使う表示用スコアとして返す。
- 最初の実装ではページネーションなしで返す。グリッド数が増えてレスポンスが大きくなったら、後続でページネーションや範囲指定を検討する。
- この API では集計値を再計算しない。採点 API 側で更新済みの `GridCell` の値を読み取って返す。

初心者向け説明:

点数付きグリッド一覧 API は、フロントエンドが地図上にグリッドを並べるための API です。
採点 API は「点数を保存する」ための API ですが、この API は「保存済みの点数をまとめて見る」ための API です。

`row_index` と `col_index` は、グリッドを画面上で並べるための行番号・列番号です。
`north`、`south`、`east`、`west` は、地図上でその 1 マスがどの範囲を表すかを示します。
`calculated_score` は、色分けやランキング表示に使う最終点数です。

### View 設計の未決定事項

- 採点後レスポンスに `rating` と `grid` の両方を返す方針でよいか。
- 一括採点で一部だけ失敗した場合、全体をエラーにするか、成功分だけ保存するか。
- 集計処理を `maps/services.py` に置くか、model method にするか。
- 認証方式を Session 認証にするか、Token/JWT 認証にするか。
- 権限として、誰がどの `MapArea` や `GridCell` に採点できるかを制限するか。
- 点数付きグリッド一覧 API でグリッド数が多い場合、ページネーションや表示範囲指定を入れるか。

## 集計処理の設計案

この設計案は、まだ `maps/services.py` には反映しません。
採点 API の view を実装する前に、`GridRating` が作成または更新された後の `GridCell` 集計処理を整理するためのメモです。

### 集計処理の置き場所

候補は 3 つあります。

| 置き場所 | 良い点 | 注意点 |
| --- | --- | --- |
| `maps/services.py` | view から呼び出しやすく、単体採点と一括採点で共有しやすい | ファイルを新しく作る必要がある |
| `GridCell` の model method | `GridCell` に関係する処理だと分かりやすい | model が計算処理で大きくなりやすい |
| view の中に直接書く | 最初は動きが見えやすい | view が長くなり、同じ計算が重複しやすい |

推奨案:

```text
maps/services.py に関数として置く
```

理由:

- 単体採点 API と一括採点 API の両方から使える。
- view を短く保てる。
- 将来的に計算式を変更するとき、修正箇所を 1 つにまとめやすい。
- 初心者にとっても「API の流れ」と「点数計算」を分けて読める。

想定する関数名:

```text
update_grid_cell_score(grid_cell)
```

### 再計算する項目

`GridCell` の次の値を再計算します。

| 項目 | 意味 |
| --- | --- |
| `average_user_score` | 対象グリッドに付いたユーザー採点の平均 |
| `rating_count` | 対象グリッドに付いた採点数 |
| `calculated_score` | 地図表示で使う最終点数 |
| `score_updated_at` | 集計値を最後に更新した日時 |

### 計算式

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

採点が 0 件の場合に `calculated_score = initial_score` とする理由:

- ユーザー評価がまだなくても、地形情報などから付けた初期点数を表示に使える。
- `calculated_score` が 0 になってしまうと、未採点の場所が不自然に低評価に見える可能性がある。

採点が 0 件の場合に `score_updated_at = null` とする理由:

- まだユーザー採点による集計が行われていないことを表せる。
- 「最後に集計した日時」と「まだ集計していない状態」を区別できる。

### 単体採点時の処理手順

単体採点 API では、1 つの `GridCell` に対して処理します。

1. URL の `grid_id` から `GridCell` を取得する。
2. `GridRatingCreateSerializer` で入力を検証する。
3. `GridRating` を作成または更新する。
4. `update_grid_cell_score(grid_cell)` を呼び出す。
5. 更新された `GridCell` を保存する。
6. レスポンスで `rating` と `grid` を返す。

### 一括採点時の処理手順

一括採点 API では、複数の `GridCell` に対して同じ点数を付けます。

1. `BulkGridRatingSerializer` で `grid_ids`、`score`、`comment` を検証する。
2. 対象の `GridCell` 一覧を取得する。
3. 各 `GridCell` について `GridRating` を作成または更新する。
4. 各 `GridCell` について `update_grid_cell_score(grid_cell)` を呼び出す。
5. 更新された `GridCell` 一覧を返す。

### エラー時の扱い

| 状況 | 方針 |
| --- | --- |
| `score` が範囲外 | serializer で `400 Bad Request` |
| `grid_id` が存在しない | view で `404 Not Found` |
| `grid_ids` が空 | serializer で `400 Bad Request` |
| 一括採点に存在しない `grid_id` が含まれる | serializer で全体を `400 Bad Request` |
| 集計中に予期しないエラー | `500 Internal Server Error`。詳細はログで確認 |

一括採点で一部だけ成功させると状態が分かりにくくなるため、最初の実装では「1 件でも不正な `grid_id` があれば全体をエラー」にします。

### 同時更新について

複数ユーザーが同じ `GridCell` を同時に採点した場合、集計値の更新タイミングがぶつかる可能性があります。

学習用の最初の実装では、採点後に毎回 `GridRating` 全体から平均と件数を再計算する方式にします。
この方式なら、単純に件数を足し引きするよりも分かりやすく、再採点にも対応しやすいです。

将来的に本格運用を考える場合は、次を検討します。

- DB トランザクション
- `select_for_update`
- 非同期処理
- 集計値を DB に保存せず、API 応答時に毎回計算する方式

### 初心者向け説明

service は、view から呼び出す処理を分けて置く場所です。
今回なら「採点後に平均点や件数を計算する処理」を `maps/services.py` に置く想定です。

view に全部書かない理由は、view が読みにくくなるからです。
view は「リクエストを受け取ってレスポンスを返す流れ」に集中し、点数計算のような処理は service に分けると整理しやすくなります。

`average_user_score` は、ユーザーが付けた点数の平均です。
たとえば 8 点と 6 点が付いていれば平均は 7 点です。

`rating_count` は、そのグリッドに何件の採点があるかです。
平均点だけでなく件数もあると、1 人だけの高得点なのか、多くの人が高く評価しているのかを判断しやすくなります。

`calculated_score` は、地図上で色分け表示するときに使う最終点数です。
今は仮に `initial_score` と `average_user_score` の平均にします。

`score_updated_at` は、集計値を最後に更新した日時です。
採点後に再計算されたタイミングを確認できます。

採点後に再計算が必要な理由は、`GridRating` が増えたり更新されたりすると平均点や件数が変わるためです。
再計算しないと、地図上に古い点数が表示されてしまいます。

### 集計処理の未決定事項

- `calculated_score` の計算式を今後も `(initial_score + average_user_score) / 2` にするか。
- ユーザー採点を初期点数より強く反映するか。
- `score_updated_at` を採点 0 件のとき `null` にする方針で確定するか。
- 同時更新対策をどの段階で入れるか。
- 集計値を DB に保存する方式を続けるか、API 応答時に毎回計算する方式に変えるか。

## 想定する主な機能

1. 地図範囲を指定する
2. 指定範囲をグリッドに分割する
3. 各グリッドに初期点数を付ける
4. ユーザーが 1 つまたは複数のグリッドを採点する
5. 採点結果を集計する
6. 点数付きのグリッド一覧を返す
7. 周辺の高得点グリッドを検索する

## エンドポイント案

まだ実装しません。
まずは API の入口を小さく分けて設計します。

| メソッド | パス | 目的 | 認証 |
| --- | --- | --- | --- |
| `POST` | `/api/maps/areas/` | 地図範囲を登録する | 必要 |
| `GET` | `/api/maps/areas/` | 地図範囲一覧を取得する | 必要 |
| `POST` | `/api/maps/areas/{area_id}/grids/` | 地図範囲をグリッドに分割する | 必要 |
| `GET` | `/api/maps/areas/{area_id}/grids/` | 点数付きグリッド一覧を取得する | 必要 |
| `POST` | `/api/maps/grids/{grid_id}/ratings/` | 1 つのグリッドを採点する | 必要 |
| `POST` | `/api/maps/grids/bulk-ratings/` | 複数グリッドをまとめて採点する | 必要 |
| `GET` | `/api/maps/grids/search/` | 周辺の高得点グリッドを検索する | 必要 |

## リクエスト例

### 地図範囲を登録する

```json
{
  "name": "sample area",
  "north": 35.70,
  "south": 35.60,
  "east": 139.80,
  "west": 139.70
}
```

### グリッドを採点する

```json
{
  "score": 4,
  "comment": "水辺が近くて良さそう"
}
```

### 複数グリッドをまとめて採点する

```json
{
  "grid_ids": [1, 2, 3],
  "score": 5
}
```

## レスポンス例

### 点数付きグリッド一覧 API

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

## 未決定事項

- 地図データの取得元
- グリッド幅
- 点数の範囲
- 初期点数の計算方法
- 平均値以外の集計方法を使うか
- 匿名採点を許可するか
- ユーザーごとに同じグリッドを何回採点できるか
- 位置情報や履歴を保存するか
- フロントエンドでどの地図ライブラリを使うか
- 点数付きグリッド一覧 API にページネーションを入れるか
- 点数付きグリッド一覧 API で地図表示範囲による絞り込みを行うか

## 次に決めること

1. 最初に作る最小機能を決める
2. 地図範囲とグリッドのモデル案を作る
3. 採点データの保存方法を決める
4. API のレスポンス形式をさらに具体化する
5. テスト観点を整理する
