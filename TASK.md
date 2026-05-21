# 現在のタスク

採点 API と一括採点 API に `created_by` ベースの権限チェックを追加してください。

# 目的

現在の採点 API は、ログイン済みであれば `GridCell` の ID を指定して採点できます。

しかし、`GridCell` は `MapArea` に紐づいており、`MapArea` には作成者を表す `created_by` があります。
そのため、他ユーザーが作成した `MapArea` に属する `GridCell` には採点できないようにします。

今回の目的は、次の流れをユーザー本人のデータ範囲で安全に動かせる状態にすることです。

```text
MapArea 作成
→ GridCell 自動生成
→ 点数付きグリッド一覧取得
→ 採点
→ 点数再集計
```

# 担当役割

Backend Developer / Tester / API Designer

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
- `maps/tests.py`

必要な場合のみ:

- `README.md`
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

# 対象 API

```text
POST /api/maps/grids/{grid_id}/ratings/
POST /api/maps/grids/bulk-ratings/
```

# 追加する権限チェック

`GridCell.area.created_by` と `request.user` を比較してください。

| 状況 | 結果 |
| --- | --- |
| 未ログイン | `401 Unauthorized` |
| `GridCell.area.created_by == request.user` | 採点許可 |
| `GridCell.area.created_by != request.user` | `404 Not Found` |
| `GridCell.area.created_by is None` | `404 Not Found` |
| `grid_id` が存在しない | `404 Not Found` |

# エラー方針

他ユーザーの `GridCell` や `created_by is None` の `GridCell` は、存在しないものとして扱ってください。

そのため、`403 Forbidden` ではなく `404 Not Found` を返します。

理由:

- MapArea 詳細 API、点数付きグリッド一覧 API の閲覧制限と方針を揃えるため
- 他ユーザーのデータが存在することをレスポンスから推測しにくくするため

# 実装方針

## 単体採点 API

現在のように `id` だけで `GridCell` を取得せず、`area__created_by=request.user` も条件に含めてください。

例:

```python
grid = get_object_or_404(
    GridCell,
    id=grid_id,
    area__created_by=request.user,
)
```

期待する挙動:

- 自分の `MapArea` に属する `GridCell` なら採点できる
- 他ユーザーの `MapArea` に属する `GridCell` は `404 Not Found`
- `created_by is None` の `MapArea` に属する `GridCell` は `404 Not Found`
- 存在しない `grid_id` は `404 Not Found`
- 採点成功時はこれまで通り `GridRating` を作成または更新する
- 採点成功後はこれまで通り `update_grid_cell_score(grid)` を呼ぶ

## 一括採点 API

`grid_ids` に含まれるすべての `GridCell` が、ログイン中ユーザーの `MapArea` に属している場合だけ採点してください。

例:

```python
grids = GridCell.objects.filter(
    id__in=grid_ids,
    area__created_by=request.user,
)
```

注意点:

- 存在しない ID が含まれる場合は、これまで通り入力不正として扱う
- 他ユーザーの `GridCell` が含まれる場合も、存在しない ID と同じように扱う
- `created_by is None` の `GridCell` が含まれる場合も、存在しない ID と同じように扱う
- 一部だけ採点して成功、という動きにはしない
- 1 件でも採点不可の ID が含まれていたら、全体を失敗させる

期待する挙動:

- 全 ID が自分の `MapArea` に属する場合だけ採点できる
- 他ユーザーの `GridCell` が 1 件でも含まれたら `400 Bad Request`
- `created_by is None` の `GridCell` が 1 件でも含まれたら `400 Bad Request`
- 存在しない ID が 1 件でも含まれたら `400 Bad Request`
- 成功時はこれまで通り、各 `GridCell` の点数を再集計する

# API_SPEC.md に追記する内容

採点 API と一括採点 API の権限仕様を追記してください。

最低限、次を明記してください。

- 採点できるのは、自分が作成した `MapArea` に属する `GridCell` だけ
- 他ユーザーの `GridCell` は採点できない
- `created_by is None` の `MapArea` に属する `GridCell` は採点できない
- 単体採点 API では権限なしを `404 Not Found` にする
- 一括採点 API では、権限なし ID が 1 件でも含まれたら全体を `400 Bad Request` にする
- 一括採点 API では、一部だけ採点して成功にはしない

# テスト追加

`maps/tests.py` にテストを追加してください。
既存のテストクラスに追加して構いません。

## 単体採点 API のテスト

最低限ほしいテスト:

1. 自分の `MapArea` に属する `GridCell` は採点できる
2. 他ユーザーの `MapArea` に属する `GridCell` は `404 Not Found`
3. `created_by is None` の `MapArea` に属する `GridCell` は `404 Not Found`
4. 存在しない `grid_id` は `404 Not Found`
5. 権限がない場合は `GridRating` が作成されない
6. 権限がない場合は `GridCell` の集計値が変わらない

## 一括採点 API のテスト

最低限ほしいテスト:

1. 自分の `MapArea` に属する `GridCell` だけなら採点できる
2. 他ユーザーの `GridCell` が 1 件でも含まれたら `400 Bad Request`
3. `created_by is None` の `GridCell` が 1 件でも含まれたら `400 Bad Request`
4. 存在しない ID が 1 件でも含まれたら `400 Bad Request`
5. 権限がない ID が含まれる場合は、採点可能な `GridCell` にも `GridRating` が作成されない
6. 権限がない ID が含まれる場合は、どの `GridCell` の集計値も変わらない

# 注意点

- 今回は `models.py` を変更しないでください。
- migration は作成しないでください。
- `created_by` を必須に変更しないでください。
- 認証方式は変更しないでください。
- serializer の責務を大きく変えないでください。
- `update_grid_cell_score()` の計算ロジックは変更しないでください。
- GridCell 自動生成 API の `403 Forbidden` 方針は変更しないでください。
- MapArea 一覧・詳細・点数付きグリッド一覧 API の閲覧制限は変更しないでください。

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff -- API_SPEC.md maps/views.py maps/tests.py
git diff --check -- API_SPEC.md maps/views.py maps/tests.py
```

README を更新した場合は、次も確認してください。

```bash
git diff -- README.md
git diff --check -- README.md
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