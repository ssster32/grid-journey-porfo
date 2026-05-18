# 現在のタスク

MapArea 一覧・詳細・点数付きグリッド一覧に `created_by` ベースの閲覧制限を実装し、テストを追加してください。

# 目的

現在の MapArea 一覧 API、MapArea 詳細 API、点数付きグリッド一覧 API は、ログイン済みであれば他ユーザーが作成した `MapArea` も取得できる状態です。

今回は、`MapArea.created_by` とログイン中ユーザー `request.user` を使って、作成者本人だけが自分の `MapArea` と紐づく `GridCell` を閲覧できるようにします。

作業範囲は、実装 + テスト追加です。
`API_SPEC.md` の設計は既に追記済みなので、必要な微修正があれば行ってください。

# 担当役割

Backend Developer / Tester

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

- `maps/views.py`
- `maps/tests.py`

必要な場合のみ:

- `API_SPEC.md`
- `TASK.md`

# 変更しないファイル

指示がない限り、次は変更しないでください。

- `maps/models.py`
- `maps/migrations/`
- `maps/services.py`
- `maps/urls.py`
- `maps/serializers.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`
- `README.md`

# 対象 API

```text
GET /api/maps/areas/
GET /api/maps/areas/{area_id}/
GET /api/maps/areas/{area_id}/grids/
```

# 追加する閲覧制限

`MapArea.created_by` と `request.user` を比較してください。

| 状況 | 結果 |
| --- | --- |
| 未ログイン | `401 Unauthorized` |
| `MapArea.created_by == request.user` | 閲覧許可 |
| `MapArea.created_by != request.user` | `404 Not Found` |
| `MapArea.created_by is None` | `404 Not Found` |

# 実装方針

## MapArea 一覧 API

現在のように全件取得せず、ログイン中ユーザーが作成した `MapArea` のみ返してください。

```python
areas = MapArea.objects.filter(created_by=request.user)
```

期待する挙動:

- 自分の `MapArea` だけ `areas` に含まれる
- 他ユーザーの `MapArea` は含まれない
- `created_by is None` の `MapArea` は含まれない
- 自分の `MapArea` が 0 件なら `areas: []`

## MapArea 詳細 API

`id` だけで取得せず、`created_by=request.user` も条件に含めてください。

```python
area = get_object_or_404(MapArea, id=area_id, created_by=request.user)
```

期待する挙動:

- 自分の `MapArea` なら `200 OK`
- 他ユーザーの `MapArea` なら `404 Not Found`
- `created_by is None` の `MapArea` なら `404 Not Found`
- 存在しない `area_id` なら `404 Not Found`

## 点数付きグリッド一覧 API

`area_id` から `MapArea` を取得するときに、`created_by=request.user` も条件に含めてください。

```python
area = get_object_or_404(MapArea, id=area_id, created_by=request.user)
grids = area.grid_cells.order_by("row_index", "col_index")
```

期待する挙動:

- 自分の `MapArea` の `GridCell` なら取得できる
- 他ユーザーの `MapArea` なら `404 Not Found`
- `created_by is None` の `MapArea` なら `404 Not Found`
- 存在しない `area_id` なら `404 Not Found`

# テスト追加

`maps/tests.py` にテストを追加してください。
既存のテストクラスに追加して構いません。

## MapArea 一覧 API のテスト

最低限ほしいテスト:

1. 自分の `MapArea` だけ一覧に含まれる
2. 他ユーザーの `MapArea` は一覧に含まれない
3. `created_by is None` の `MapArea` は一覧に含まれない
4. 自分の `MapArea` が 0 件なら `areas: []`

## MapArea 詳細 API のテスト

最低限ほしいテスト:

1. 自分の `MapArea` は `200 OK`
2. 他ユーザーの `MapArea` は `404 Not Found`
3. `created_by is None` の `MapArea` は `404 Not Found`
4. 存在しない `area_id` は `404 Not Found`

## 点数付きグリッド一覧 API のテスト

最低限ほしいテスト:

1. 自分の `MapArea` の `GridCell` は取得できる
2. 他ユーザーの `MapArea` は `404 Not Found`
3. `created_by is None` の `MapArea` は `404 Not Found`
4. 存在しない `area_id` は `404 Not Found`

# 注意点

- 他ユーザーの `MapArea` は `403 Forbidden` ではなく `404 Not Found` にしてください。
- 一覧 API では他ユーザーの `MapArea` をレスポンスに含めないだけで、エラーにはしません。
- `created_by is None` の `MapArea` は、通常のユーザーからは見えない扱いにしてください。
- GridCell 自動生成 API の `403 Forbidden` 方針は変更しないでください。
- 今回は閲覧 API のみ対象です。作成 API、採点 API、一括採点 API、自動生成 API の権限は変更しません。

# 今回やらないこと

- `models.py` の変更
- migration の作成
- `created_by` を必須に変更すること
- `generate_grid_cells_for_area` service の変更
- serializer の変更
- URL の変更
- 認証方式の変更
- 依存関係の追加
- README の手動確認手順追加
- 管理者だけ全件閲覧できる特別ルール
- 共有用の MapArea や公開 MapArea の設計

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff -- maps/views.py maps/tests.py
git diff --check -- maps/views.py maps/tests.py
```

# 完了報告

短めでよいので、次を報告してください。

- 担当した役割
- 変更したファイル
- 変更内容
- Django / DRF 実装上の補足
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業