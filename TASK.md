# 現在のタスク

GridCell 自動生成 API を設計・実装してください。

# 目的

実装済みの `generate_grid_cells_for_area(map_area)` service を使って、指定した `MapArea` から `GridCell` を自動生成できる API を追加します。

今回は API 設計、view 実装、URL 追加、テスト追加、`API_SPEC.md` 更新まで行います。
`models.py` と migration は変更しません。

# 担当役割

API Designer / Backend Developer / Tester

# 作業前に確認するファイル

- `memo.md`
- `AGENTS.md`
- `README.md`
- `RULES.md`
- `TASK.md`
- `API_SPEC.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `maps/models.py`
- `maps/services.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`

# 編集してよいファイル

- `API_SPEC.md`
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`

必要な場合のみ:

- `maps/serializers.py`
- `README.md`
- `TASK.md`

# 変更しないファイル

指示がない限り、次は変更しないでください。

- `maps/models.py`
- `maps/migrations/`
- `maps/services.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`

# 追加する API

```text
POST /api/maps/areas/{area_id}/grids/
```

# 目的

指定した `MapArea` から `GridCell` を自動生成します。

# 認証

既存 API と同じくログイン必須にしてください。

```python
authentication_classes = [BasicAuthentication, SessionAuthentication]
permission_classes = [IsAuthenticated]
```

# 処理の流れ

1. URL の `area_id` から `MapArea` を取得する
2. `area_id` が存在しない場合は `404 Not Found`
3. `generate_grid_cells_for_area(area)` を呼び出す
4. 生成した `GridCell` 一覧を返す
5. 既に `GridCell` がある場合など service が `ValueError` を出した場合は `400 Bad Request`

# リクエスト

リクエストボディはありません。

# レスポンス

成功時は次の形にしてください。

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

`GridCell` の出力には、既存の `GridCellScoreSerializer` を使ってください。

# ステータスコード

| 状況 | ステータス |
| --- | --- |
| 生成成功 | `201 Created` |
| 未ログイン | `401 Unauthorized` |
| `area_id` が存在しない | `404 Not Found` |
| 既に `GridCell` がある | `400 Bad Request` |
| service の入力チェックで不正値 | `400 Bad Request` |

# エラー形式

`ValueError` の場合は、まずは次のようなシンプルな形式で返してください。

```json
{
  "detail": "この MapArea には既に GridCell があります。"
}
```

# URL 名

URL 名は次のようにしてください。

```python
name="grid-cell-generate"
```

# テスト追加

`maps/tests.py` に API テストを追加してください。

最低限ほしいテスト:

1. ログイン済みユーザーは `MapArea` から `GridCell` を生成できる
2. 成功時は `201 Created`
3. レスポンスに `area` と `grids` が含まれる
4. 生成された `grids` は `row_index`, `col_index` 順に返る
5. 未ログインでは `401 Unauthorized`
6. 存在しない `area_id` では `404 Not Found`
7. 既に `GridCell` がある場合は `400 Bad Request`
8. 既に `GridCell` がある場合、新しい `GridCell` は増えない

# API_SPEC.md 更新

`API_SPEC.md` に GridCell 自動生成 API を実装済み API として追記してください。

更新内容:

- 「現在の実装状況」の実装済み API に追加
- 未実装 API 候補から削除または状態を更新
- `POST /api/maps/areas/{area_id}/grids/` の仕様を追加
- 認証、リクエスト、レスポンス、ステータスコード、エラー形式を書く
- 「設計中: GridCell 自動生成 service」は、必要なら「実装済み service」に表現を調整する

# 今回やらないこと

- `models.py` の変更
- migration の作成
- `generate_grid_cells_for_area` service の大きな変更
- serializer の大きな再設計
- 認証方式の変更
- 権限設計の変更
- 依存関係の追加
- 外部地図 API の利用
- 正確な地球測地計算
- 地形情報や観光情報からの `initial_score` 計算
- README の長い手動確認手順追加

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff -- API_SPEC.md maps/views.py maps/urls.py maps/tests.py
git diff --check -- API_SPEC.md maps/views.py maps/urls.py maps/tests.py
```

# 完了報告

短めでよいので、次を報告してください。

- 担当した役割
- 変更したファイル
- 変更内容
- 初心者向け補足
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業