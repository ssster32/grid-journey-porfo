# 現在のタスク

点数付きグリッド一覧 API を小さく実装してください。

# 目的

`GET /api/maps/areas/{area_id}/grids/` で、指定した `MapArea` に属する `GridCell` 一覧を点数付きで取得できるようにします。

この API は、地図画面でグリッドを表示し、`calculated_score` をもとに色分けするための元データを返します。

# 作業範囲

- `maps/views.py` に点数付きグリッド一覧 API の view を実装する
- `maps/urls.py` に URL を追加する
- `GridCellScoreSerializer` を使ってレスポンスを作る
- URL の `area_id` から `MapArea` を取得する
- 指定した `MapArea` に属する `GridCell` 一覧を取得する
- `row_index`, `col_index` の順に並べる
- レスポンスで `area` と `grids` を返す
- 必要なら view のテストを追加する
- `.venv/bin/python manage.py test maps` を実行する
- `.venv/bin/python manage.py check` を実行する

# 今回はやらないこと

- 採点 API は変更しない
- 一括採点 API は変更しない
- 地図取得処理は作らない
- グリッド自動生成処理は作らない
- model は変更しない
- serializer は原則変更しない
- migration は作らない
- 外部地図 API は使わない
- ページネーションは入れない
- 地図表示範囲による絞り込みは入れない
- この API 内では集計値を再計算しない

# API 仕様

## エンドポイント

```text
GET /api/maps/areas/{area_id}/grids/
```

# 認証
ログイン必須。
未ログインの場合は 401 Unauthorized を返す想定。

# リクエストボディ
なし。

# レスポンス例
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
# グリッドが 0 件の場合
```json
{
  "area": {
    "id": 1,
    "name": "Manual Test Area"
  },
  "grids": []
}
```
# ステータスコード方針
- 一覧を取得できた: 200 OK
- 未ログイン: 401 Unauthorized
- area_id が存在しない: 404 Not Found
# 注意点
- 権限はまず IsAuthenticated を使う
- 認証方式は新しく追加しない
- 既存の単体採点 API / 一括採点 API と同じ認証設定にそろえる
- area_id は URL から受け取る
- MapArea が存在しない場合は 404 Not Found
- GridCell は row_index, col_index の順に並べる
- 採点数が 0 件のグリッドも返す
- calculated_score は保存済みの値を返す
- この API では update_grid_cell_score() を呼び出さない
- API_SPEC.md と実装内容がズレないようにする
# テスト観点
- ログイン済みユーザーが指定 MapArea のグリッド一覧を取得できる
- レスポンスに area と grids が含まれる
- grids は row_index, col_index の順に並ぶ
- グリッドが 0 件の場合は空配列を返す
- 未ログインでは 401 Unauthorized
- 存在しない area_id では 404 Not Found
- 別の MapArea の GridCell は含まれない
