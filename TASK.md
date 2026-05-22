# Codex タスク: 共有メモグリッドの共有相手管理 API を実装する

## 担当ロール

今回は **Backend Developer** と **Tester** として作業してください。

`API_SPEC.md` に設計済みの、共有メモグリッドの共有相手一覧・追加・削除 API を実装し、テストを追加してください。

## 作業前に必ず読むファイル

作業前に、次のファイルを確認してください。

- `AGENTS.md`
- `RULES.md`
- `README.md`
- `TASK.md`
- `API_SPEC.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`

特に、以下を確認してください。

- `MapArea` の `created_by`
- `MapAreaShare` model
- 既存の MapArea 一覧 API / 詳細 API / GridCell 一覧 API の共有対応
- 採点 API の共有メモグリッド対応
- 既存の認証方式
- 既存の URL 設計・命名規則
- 既存テストの書き方

## 今回の目的

共有メモグリッドについて、作成者が共有相手を管理できるようにします。

具体的には、次の API を追加します。

- 共有相手一覧 API
- 共有相手追加 API
- 共有相手削除 API

共有されたユーザーは、共有メモグリッドの閲覧・採点はできます。
ただし、共有相手の一覧取得・追加・削除はできません。

## 今回やること

- `MapAreaShare` を返す serializer を追加する
- 共有相手追加用 serializer を追加する
- 共有相手一覧 API を実装する
- 共有相手追加 API を実装する
- 共有相手削除 API を実装する
- URL を追加する
- 権限チェックを実装する
- テストを追加する
- 必要であれば `API_SPEC.md` を実装内容に合わせて微修正する

## 対象 API

### 1. 共有相手一覧 API

```text
GET /api/maps/areas/{area_id}/shares/
```

指定した `MapArea` の共有相手一覧を取得します。

作成者本人だけが取得できます。

### 2. 共有相手追加 API

```text
POST /api/maps/areas/{area_id}/shares/
```

指定した `MapArea` に共有相手を追加します。

作成者本人だけが追加できます。

リクエストは `username` 指定にしてください。

```json
{
  "username": "otheruser"
}
```

### 3. 共有相手削除 API

```text
DELETE /api/maps/areas/{area_id}/shares/{share_id}/
```

指定した `MapArea` から共有相手を削除します。

作成者本人だけが削除できます。

削除成功時は `204 No Content` を返してください。

## 変更してよいファイル

- `maps/serializers.py`
- `maps/views.py`
- `maps/urls.py`
- `maps/tests.py`
- `API_SPEC.md`

## 変更しないファイル

- `maps/models.py`
- `maps/migrations/`
- `maps/admin.py`
- `maps/services.py`
- `config/settings.py`
- `config/urls.py`
- `README.md`
- `requirements.txt`

今回のタスクでは、model と migration は変更しないでください。
`MapAreaShare` model は既に存在する前提です。

## 権限方針

共有相手管理 API はログイン必須です。

操作できるのは、`MapArea.created_by == request.user` の場合だけです。

| ユーザー | 一覧 | 追加 | 削除 |
| --- | --- | --- | --- |
| 作成者 | 可 | 可 | 可 |
| 共有されたユーザー | 不可 | 不可 | 不可 |
| 共有されていないユーザー | 不可 | 不可 | 不可 |

共有されたユーザーは、共有メモグリッドの閲覧・採点はできます。
ただし、共有相手管理はできません。

`created_by=None` の `MapArea` は、通常ユーザーが共有相手管理できない扱いにしてください。

権限がない場合は、他ユーザーの `MapArea` が存在することを推測しにくくするため、`404 Not Found` を返してください。

実装では、共有相手管理用に次のような取得処理を使う想定です。

```python
area = get_object_or_404(
    MapArea.objects.filter(created_by=request.user),
    id=area_id,
)
```

## レスポンス仕様

### 共有相手一覧 API

成功時:

```json
{
  "area": {
    "id": 1,
    "name": "東京駅周辺"
  },
  "shares": [
    {
      "id": 1,
      "user": {
        "id": 4,
        "username": "otheruser"
      },
      "created_at": "2026-05-22T10:00:00+09:00"
    }
  ]
}
```

共有相手が 0 件の場合:

```json
{
  "area": {
    "id": 1,
    "name": "東京駅周辺"
  },
  "shares": []
}
```

### 共有相手追加 API

成功時:

```json
{
  "share": {
    "id": 1,
    "area": 1,
    "user": {
      "id": 4,
      "username": "otheruser"
    },
    "created_at": "2026-05-22T10:00:00+09:00"
  }
}
```

### 共有相手削除 API

成功時は本文なしで `204 No Content` を返してください。

## ステータスコード方針

| 状況 | ステータス |
| --- | --- |
| 共有相手一覧取得成功 | `200 OK` |
| 共有相手追加成功 | `201 Created` |
| 共有相手削除成功 | `204 No Content` |
| 未ログイン | `401 Unauthorized` |
| `area_id` が存在しない | `404 Not Found` |
| 作成者以外が操作しようとした | `404 Not Found` |
| `created_by=None` の `MapArea` を指定した | `404 Not Found` |
| `username` がない | `400 Bad Request` |
| `username` が文字列ではない | `400 Bad Request` |
| 存在しないユーザーを指定した | `400 Bad Request` |
| 作成者自身を指定した | `400 Bad Request` |
| 既に共有済みのユーザーを指定した | `400 Bad Request` |
| `share_id` が存在しない | `404 Not Found` |
| `share_id` が指定 `area_id` に属していない | `404 Not Found` |

## 実装方針

- 既存の APIView ベースの実装に合わせてください。
- 認証は既存の `API_AUTHENTICATION_CLASSES` を使ってください。
- 権限は `permission_classes = [IsAuthenticated]` を使ってください。
- 共有相手管理専用の helper を追加しても構いません。
- レスポンスに `email` は含めないでください。
- 共有相手追加は `username` でユーザーを検索してください。
- 作成者自身を共有相手に追加できないようにしてください。
- 重複共有は `400 Bad Request` にしてください。
- 削除 API は `area_id` と `share_id` の両方で対象を絞ってください。

## テスト方針

最低限、以下を `maps/tests.py` に追加してください。

### 共有相手一覧 API

- 作成者は共有相手一覧を取得できる
- 共有相手が 0 件なら空配列を返す
- 共有されたユーザーは共有相手一覧を取得できない
- 共有されていない他ユーザーは取得できない
- 未ログインは拒否される
- 存在しない `area_id` は拒否される
- `created_by=None` の `MapArea` は通常ユーザーが管理できない

### 共有相手追加 API

- 作成者は共有相手を追加できる
- 追加後、そのユーザーが MapArea 一覧・詳細・GridCell 一覧・採点 API を使える
- 存在しないユーザーは追加できない
- 既に共有済みのユーザーは重複追加できない
- 作成者自身は共有相手に追加できない
- 共有されたユーザーは追加できない
- 共有されていない他ユーザーは追加できない
- 未ログインは拒否される
- `created_by=None` の `MapArea` は通常ユーザーが管理できない

### 共有相手削除 API

- 作成者は共有相手を削除できる
- 削除後、そのユーザーは MapArea 一覧・詳細・GridCell 一覧・採点 API を使えなくなる
- 存在しない共有関係は削除できない
- 指定 `area_id` に属さない `share_id` は削除できない
- 共有されたユーザーは削除できない
- 共有されていない他ユーザーは削除できない
- 未ログインは拒否される
- `created_by=None` の `MapArea` は通常ユーザーが管理できない

## API_SPEC 更新方針

`API_SPEC.md` の設計内容と実装がずれた場合だけ、実装に合わせて微修正してください。

設計どおり実装できた場合、大きな追記は不要です。

## 今回は実装しないこと

- `MapAreaShare` model の変更
- migration の作成
- admin の変更
- demo ページの変更
- README の手動確認手順追加
- ワールドグリッド対応
- `is_public` の実装
- ユーザー検索 API の実装
- 管理者向け特別権限の実装

## 確認方法

作業後、次を実行してください。

```bash
source .venv/bin/activate
python manage.py check
python manage.py test maps
git diff --check -- maps/serializers.py maps/views.py maps/urls.py maps/tests.py API_SPEC.md
```

## 注意事項

- 既存の命名、構成、書き方を優先してください。
- 大きな仕様変更はしないでください。
- `MapArea` という内部名は維持してください。
- ユーザー向け説明では `メモグリッド` / `共有メモグリッド` という呼称を使ってください。
- `ワールドグリッド` は今回扱わないでください。
- `is_public` は今回扱わないでください。
- 共有されたユーザーは閲覧・採点のみ可能です。
- 共有されたユーザーに共有相手管理を許可しないでください。
- 認証・権限を省略しないでください。
- 秘密情報や個人情報を不要にレスポンスへ含めないでください。
- `email` は返さないでください。
- 依存関係は追加しないでください。
