# 現在のタスク

MapArea 詳細 API を実装してください。

# 目的

`GET /api/maps/areas/{area_id}/` で、指定した `MapArea` 1 件の詳細を取得できるようにします。

設計、実装、テスト、API_SPEC 更新までまとめて行ってください。

# 担当役割

Backend Developer

# 進め方

このタスクでは、次を 1 回で行ってください。

- `API_SPEC.md` に MapArea 詳細 API の仕様を追記する
- `maps/views.py` に詳細取得処理を追加する
- `maps/urls.py` に `GET /api/maps/areas/{area_id}/` の URL を追加する
- 必要に応じて既存の `MapAreaSerializer` を使う
- `maps/tests.py` に必要なテストを追加する
- `.venv/bin/python manage.py test maps` を実行する
- `.venv/bin/python manage.py check` を実行する
- `git diff --check` を実行する

# 何を作るか

```text
GET /api/maps/areas/{area_id}/
```
指定した MapArea 1 件の詳細を返す API を作ります。

# 今回やらないこと
- models.py は変更しない
- migration は作らない
- MapArea 更新 API は作らない
- MapArea 削除 API は作らない
- GridCell 自動生成はしない
- 外部地図 API は使わない
- 認証方式は変更しない
- 依存関係は追加しない
- ユーザー別の閲覧制限はまだ入れない

# 最低限の仕様
## エンドポイント
```text
GET /api/maps/areas/{area_id}/
```

## 認証
ログイン必須。

既存 API と同じく、view には次を設定してください。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

## URL パラメータ
|--|--|
|項目|内容|
|area_id|取得対象の MapArea ID|

## リクエスト
リクエストボディはありません。

## 成功時レスポンス
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

## ステータスコード
- 成功: 200 OK
- 未ログイン: 401 Unauthorized
- 存在しない area_id: 404 Not Found

# テスト観点
maps/tests.py に、少なくとも次のテストを追加してください。

- ログイン済みユーザーが MapArea 詳細を取得できる
- レスポンスに id, name, description, north, south, east, west, grid_size_meters, source, created_by, created_at, updated_at が含まれる
- 未ログインでは 401 Unauthorized
- 存在しない area_id では 404 Not Found
- 認証方式は既存 API と同じ設定にする
# 完了報告
短めでよいです。

- 変更内容
- 確認結果
- 未対応
- 次にやるとよいこと