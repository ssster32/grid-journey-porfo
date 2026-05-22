# TASK.md 用プロンプト

## 現在のタスク

demo ページと README のユーザー向け表示を MapArea からメモグリッドに変更する

## 目的

ユーザーが作成する個人用の `MapArea` は、広域の地図というより「自分用に範囲を切り出してメモ・採点する単位」に近い。

そのため、ユーザー向け UI と README の説明では `MapArea` ではなく `メモグリッド` と表示する。

ただし、内部実装名・API 名・model 名は当面 `MapArea` のまま変更しない。

## 作業範囲

- demo ページのユーザー向け表示文言を `MapArea` から `メモグリッド` に変更
- README の手動確認手順・demo ページ説明のユーザー向け文言を `メモグリッド` に変更
- API_SPEC.md に必要があれば、UI 表示名の補足を短く追記
- demo ページ表示テストの文言確認を更新

## 変更してよいファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/tests.py`
- `README.md`
- `API_SPEC.md`
- `TASK.md`

## 変更しないファイル

- `maps/models.py`
- `maps/migrations/`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `maps/urls.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`

## 表示方針

### 変更する文言の例

demo ページでは、ユーザーに見える表示を次のように変更する。

| 変更前 | 変更後 |
| --- | --- |
| `MapArea 作成` | `メモグリッド作成` |
| `MapArea 一覧` | `メモグリッド一覧` |
| `MapArea を作成` | `メモグリッドを作成` |
| `MapArea を選択すると...` | `メモグリッドを選択すると...` |
| `MapArea がありません。` | `メモグリッドがありません。` |
| `MapArea 一覧を取得しています。` | `メモグリッド一覧を取得しています。` |
| `MapArea 一覧を取得しました。` | `メモグリッド一覧を取得しました。` |
| `MapArea #... を作成しました。` | `メモグリッド #... を作成しました。` |

### 変更しない文言

以下は内部実装や API の名前として残してよい。

- JavaScript の変数名
- API パス
- serializer / view / test class 名
- `MapArea` model 名
- README 内の API 名としての `MapArea`
- API_SPEC.md の内部実装名としての `MapArea`

README では、必要に応じて次のように補足する。

```text
画面上では「メモグリッド」と表示していますが、API 内部では従来どおり MapArea と呼びます。
```

## README 更新方針

README.md の以下の範囲を中心に変更する。

- `実装済み API の手動確認`
- `MapArea 作成 API と GridCell 自動生成`
- `確認用 demo ページ`

方針:

- ユーザー操作として読む部分は `メモグリッド` に寄せる
- API エンドポイント名や内部仕様の説明では `MapArea` を残す
- `MapArea` と `メモグリッド` の対応が分かる補足を短く入れる
- `GridCell` や `Score Map` の呼称は今回は変更しない

## API_SPEC 更新方針

すでに用語方針が記載されている場合は、必要最小限の追記にとどめる。

追記する場合の内容:

- UI 表示では、個人用 `MapArea` を `メモグリッド` と呼ぶ
- API や model の内部名は `MapArea` のまま
- このタスクでは API レスポンス形式は変更しない

## テスト方針

`maps/tests.py` の demo ページ表示テストを更新する。

確認すること:

- demo ページが `200 OK` で表示される
- `メモグリッド作成` が表示される
- `メモグリッド一覧` または `メモグリッド一覧を取得` が表示される
- `メモグリッドを作成` が表示される
- `GridCell を再取得` は引き続き表示される
- `GridCell を自動生成` は引き続き表示されない
- Score Map 関連の表示は壊れていない

## 確認方法

作業後に以下を実行する。

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/tests.py README.md API_SPEC.md
```

## 注意事項

- `models.py` と migration は変更しないでください。
- API パスや API レスポンス形式は変更しないでください。
- `MapArea` という内部実装名を一括リネームしないでください。
- JavaScript の変数名や関数名は、無理に変更しなくてよいです。
- `GridCell`、`Score Map`、認証、権限、採点ロジックは変更しないでください。
- 既存テストを削除して通す対応はしないでください。