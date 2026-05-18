# 現在のタスク

MapArea 一覧 API を実装してください。

# 目的

`GET /api/maps/areas/` で、ログイン中ユーザーが作成済みの MapArea 一覧を取得できるようにします。

# 進め方

このタスクでは、次を 1 回で行ってください。

- API_SPEC.md に仕様を簡潔に追記する
- serializer / view / url を実装する
- tests.py に必要なテストを追加する
- API_SPEC.md を実装済みとして更新する
- `.venv/bin/python manage.py test maps` を実行する
- `.venv/bin/python manage.py check` を実行する

# 今回はやらないこと

- models.py は変更しない
- migration は作らない
- MapArea 詳細 API は作らない
- MapArea 更新 API は作らない
- MapArea 削除 API は作らない
- GridCell 自動生成はしない
- 認証方式は変更しない
- 依存関係は追加しない

# 仕様

```text
GET /api/maps/areas/
```

認証: ログイン必須

レスポンス例:
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

# ステータスコード
- 成功: 200 OK
- 未ログイン: 401 Unauthorized

# テスト観点
- ログイン済みユーザーが MapArea 一覧を取得できる
- レスポンスに areas が含まれる
- MapArea が 0 件なら areas は空配列
- 未ログインでは 401 Unauthorized
- 一覧の並び順は model の ordering に従う

# 完了報告
短めでよいです。

- 変更内容
- 確認結果
- 未対応
- 次にやるとよいこと