# TASK.md 用プロンプト

## 現在のタスク

MapAreaShare model を追加し、共有メモグリッドのデータ構造だけ実装する

## 目的

将来的に、ユーザー同士で `メモグリッド` を共有できるようにするため、まずは「どの MapArea を、どのユーザーに共有しているか」を保存するデータ構造を追加する。

今回はデータ構造だけを追加し、API の挙動変更は行わない。

## 作業範囲

- `MapAreaShare` model の追加
- `admin.py` への必要最小限の登録
- migration の作成
- model テストの追加
- API_SPEC.md の実装済みメモ更新が必要であれば最小限追記

## 変更してよいファイル

- `maps/models.py`
- `maps/admin.py`
- `maps/tests.py`
- `maps/migrations/`
- `API_SPEC.md`
- `TASK.md`

## 変更しないファイル

- `maps/views.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/urls.py`
- `config/settings.py`
- `config/urls.py`
- `README.md`
- `requirements.txt`

## 仕様

### 追加する model

`MapAreaShare` を追加する。

役割:

- どの `MapArea` が
- どのユーザーに
- 共有されているか

を表す。

想定フィールド:

```python
class MapAreaShare(models.Model):
    area = models.ForeignKey(
        MapArea,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_map_areas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

### 制約

同じ `area` と `user` の組み合わせは重複できない。

```python
models.UniqueConstraint(
    fields=["area", "user"],
    name="unique_map_area_share_per_user",
)
```

### 並び順

まずは扱いやすさのため、次のような ordering にする。

```python
ordering = ["area", "user", "id"]
```

### 文字列表現

`__str__` は、管理画面で見て分かる程度でよい。

例:

```python
def __str__(self):
    return f"{self.area} shared with {self.user}"
```

## admin.py 方針

`MapAreaShare` を Django admin に登録する。

必要最小限でよい。

例:

```python
@admin.register(MapAreaShare)
class MapAreaShareAdmin(admin.ModelAdmin):
    list_display = ["id", "area", "user", "created_at"]
    search_fields = ["area__name", "user__username"]
    list_filter = ["created_at"]
```

既存の admin 設定がある場合は、それに合わせる。

## テスト方針

`maps/tests.py` に model テストを追加する。

確認すること:

- `MapAreaShare` を作成できる
- `area` と `user` が保存される
- `created_at` が自動で入る
- `area.shares` から共有情報を取得できる
- `user.shared_map_areas` から共有情報を取得できる
- 同じ `area` と `user` の組み合わせを重複作成できない
- `MapArea` を削除すると、関連する `MapAreaShare` も削除される
- 共有先ユーザーを削除すると、関連する `MapAreaShare` も削除される

重複制約のテストでは `IntegrityError` を確認する。

## API_SPEC 更新方針

必要であれば、共有メモグリッド設計メモに次を追記する。

- `MapAreaShare` model は実装済み
- ただし、一覧 API・詳細 API・採点 API の権限にはまだ反映していない
- この時点では、共有情報を保存するデータ構造だけがある

## 今回は実装しないこと

- 共有メモグリッドを一覧 API に含めること
- 詳細 API の閲覧権限に共有メモグリッドを含めること
- GridCell 一覧 API の閲覧権限に共有メモグリッドを含めること
- 採点 API の権限に共有メモグリッドを含めること
- 共有相手を追加・削除する API
- demo ページでの共有メモグリッド表示
- ワールドグリッド用の `is_public` 実装

## 確認方法

作業後に以下を実行する。

```bash
.venv/bin/python manage.py makemigrations maps
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff --check -- maps/models.py maps/admin.py maps/tests.py maps/migrations API_SPEC.md
```

migration の中身も確認し、`MapAreaShare` model 追加と unique 制約だけになっていることを確認する。

## 注意事項

- このタスクでは API の挙動を変更しないでください。
- `maps/views.py`、`maps/serializers.py`、`maps/services.py`、`maps/urls.py` は変更しないでください。
- 既存 model のフィールド変更はしないでください。
- 既存 migration を手作業で変更しないでください。
- migration は `makemigrations` で作成してください。
- 既存テストを削除して通す対応はしないでください。