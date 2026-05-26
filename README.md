# map-score-api

職業訓練校の共用 Mac で使うことを想定した Django REST Framework プロジェクトです。
Python パッケージはプロジェクト直下の `.venv` にだけ入れ、PC 本体の Python 環境はできるだけ汚さない構成にします。

## プロジェクトの目標

地図情報を取得してグリッド状に分割し、各グリッドに点数を付けられる API を作ります。
ユーザーが採点した点数を集計し、分割された地図上で一目でわかる形に反映することを目指します。

現時点では仕様未定の点が多いため、まずは `API_SPEC.md` と `TASK.md` を更新しながら、小さい単位で設計と実装を進めます。

## 前提

- Python 3.12 以上
- macOS のターミナル
- `pip` は必ず `.venv` のものを使う

現在の依存関係は Django 6 系を前提にしているため、Python 3.11 以下では動きません。

## 初回セットアップ

プロジェクト直下で実行します。

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install --upgrade pip
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt
```

仮想環境が有効な間は、プロンプトの先頭に `(.venv)` が表示されます。

## 起動

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

## 開発時のコマンド

```bash
# 仮想環境を有効化
source .venv/bin/activate

# 依存関係をインストール
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt

# マイグレーション
python manage.py migrate

# 開発サーバー
python manage.py runserver

# 仮想環境を終了
deactivate
```

## 実装済み API の手動確認

ここでは、ローカル開発用 DB に確認用ユーザーを作り、実装済み API を `curl` で確認します。

`curl` はターミナルから API にリクエストを送るためのコマンドです。
`-u testuser:test-password` は Basic 認証で、ユーザー名とパスワードを送る指定です。
Token 認証を使う場合は、先に token を発行し、`Authorization: Token <TOKEN>` ヘッダーを送ります。

画面上では、個人用の `MapArea` を「メモグリッド」と表示します。
API 内部の model 名やエンドポイント名は、従来どおり `MapArea` のままです。

### 1. 事前準備

プロジェクト直下で実行します。

```bash
source .venv/bin/activate
python manage.py migrate
```

確認用ユーザーを作成します。
すでに同じユーザーがある場合は再利用します。

```bash
python manage.py shell
```

`>>>` が表示されたら、次の Python コードを貼り付けて Enter を押します。

```python
from django.contrib.auth import get_user_model

User = get_user_model()
user, _ = User.objects.get_or_create(
    username="testuser",
    defaults={"email": "test@example.com"},
)
user.set_password("test-password")
user.save()
print("user:", user.username)
```

確認が終わったら、`exit()` で shell を終了します。

別のターミナルを開き、開発サーバーを起動します。

```bash
source .venv/bin/activate
python manage.py runserver
```

### 2. Token 認証の確認

このプロジェクトでは、Basic 認証と Session 認証に加えて、DRF の Token 認証も使えます。
Token 認証を追加した後は、Token 用テーブルを作るために `python manage.py migrate` が必要です。
上の事前準備で `migrate` 済みなら、ここで追加実行しなくても大丈夫です。

まず token を発行します。

```bash
curl -i \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/auth/token/ \
  -d '{"username": "testuser", "password": "test-password"}'
```

正常な username/password なら `200 OK` が返り、レスポンスに `token` が含まれます。
返ってきた token を、以降の `<TOKEN>` に置き換えてください。

Token 認証で MapArea 一覧 API を呼びます。

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  http://127.0.0.1:8000/api/maps/areas/
```

正常に認証できた場合は `200 OK` が返ります。
Basic 認証も当面残しているため、以降の手順は `-u testuser:test-password` のままでも確認できます。

### 3. MapArea 作成 API と GridCell 自動生成

メモグリッドを作成します。
API 内部では、メモグリッドは `MapArea` として保存されます。
現在の仕様では、メモグリッド作成後に GridCell も自動生成されます。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/areas/ \
  -d '{"name": "Manual Test Area", "description": "manual curl test", "north": 35.7, "south": 35.69, "east": 139.8, "west": 139.79, "grid_size_meters": 500, "source": "manual"}'
```

Token 認証で確認する場合は、次の形でも同じ API を呼べます。

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/areas/ \
  -d '{"name": "Manual Token Area", "description": "manual token test", "north": 35.7, "south": 35.69, "east": 139.8, "west": 139.79, "grid_size_meters": 500, "source": "manual"}'
```

正常に作成できた場合は `201 Created` が返ります。
レスポンスの `id` を、以降の `<AREA_ID>` に置き換えてください。

一般ユーザーは、緯度差または経度差が 20 分を超えるメモグリッドを作成できません。
管理者はこの制限の対象外です。
これは、広すぎる範囲で `GridCell` が大量生成されることを防ぐための制限です。

次に、作成されたメモグリッドの GridCell 一覧を取得します。

```bash
curl -i -u testuser:test-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

正常に取得できた場合は `200 OK` が返ります。
`grids` に含まれる先頭 2 件の `id` を、以降の `<GRID1_ID>`、`<GRID2_ID>` に置き換えてください。

GridCell が返ることを確認することで、メモグリッド作成時の GridCell 自動生成も確認できます。

### 4. 単体採点 API

1 つのグリッドに点数を付けます。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/<GRID1_ID>/ratings/ \
  -d '{"score": 8, "comment": "水辺が近くて良さそう"}'
```

初回採点では `201 Created` が返ります。
同じコマンドをもう一度実行すると、新しい採点行は作らず既存採点を更新するため `200 OK` が返ります。

レスポンスには、作成または更新された `rating` と、再集計後の `grid` が含まれます。

### 5. 一括採点 API

複数のグリッドに同じ点数をまとめて付けます。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/bulk-ratings/ \
  -d '{"grid_ids": [<GRID1_ID>, <GRID2_ID>], "score": 5, "comment": "まとめて採点"}'
```

すべて新規採点なら `201 Created` が返ります。
既存採点が 1 件以上更新された場合は `200 OK` が返ります。

レスポンスには、再集計後の `grids` 一覧が含まれます。

### 6. GridCell 自動生成 API

指定した地図範囲から、グリッドを自動生成します。

通常の MapArea 作成 API では、MapArea 作成後に GridCell も自動生成されます。
この確認手順では、既に GridCell がある場合に自動生成 API が `400 Bad Request` を返すことを確認できます。

`<AREA_ID>` は、MapArea 作成 API で返った `id` に置き換えてください。

```bash
curl -i -u testuser:test-password \
  -X POST http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

MapArea 作成時点ですでに GridCell があるため、`400 Bad Request` が返ります。
これは、重複生成で既存の採点や集計値を壊さないための動きです。

### 7. 点数付きグリッド一覧 API

指定した地図範囲に属するグリッド一覧を、点数付きで取得します。

```bash
curl -i -u testuser:test-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

正常に取得できた場合は `200 OK` が返ります。
レスポンスには `area` と `grids` が含まれます。

`grids` には、各グリッドの位置情報と点数が含まれます。
地図画面では `calculated_score` を使って色分け表示する想定です。

```json
{
  "area": {
    "id": 1,
    "name": "Manual Test Area"
  },
  "grids": [
    {
      "id": 1,
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

この API は保存済みの集計値を読むだけです。
新しく採点したい場合は、単体採点 API または一括採点 API を使います。

### 8. メモグリッド閲覧制限の確認

メモグリッドは作成者本人だけが一覧・詳細・グリッド一覧で閲覧できます。
API 内部では `MapArea` として扱います。
別ユーザーで同じ `area_id` を指定すると、詳細とグリッド一覧は `404 Not Found` になります。

まず別ユーザーを作成します。

```bash
python manage.py shell
```

`>>>` が表示されたら、次の Python コードを貼り付けます。

```python
from django.contrib.auth import get_user_model

User = get_user_model()
other_user, _ = User.objects.get_or_create(username="otheruser")
other_user.set_password("other-password")
other_user.save()
print("user:", other_user.username)
```

確認が終わったら、`exit()` で shell を終了します。

`<AREA_ID>` は、MapArea 作成 API で返った `id` に置き換えてください。

```bash
curl -i -u otheruser:other-password \
  http://127.0.0.1:8000/api/maps/areas/
```

`otheruser` が作成したメモグリッドがなければ、`200 OK` で `areas: []` が返ります。
`testuser` が作成したメモグリッドは含まれません。

```bash
curl -i -u otheruser:other-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/
```

`testuser` が作成したメモグリッドを `otheruser` で取得しようとしているため、`404 Not Found` が返ります。

```bash
curl -i -u otheruser:other-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

グリッド一覧も同じく、`404 Not Found` が返ります。

### 9. 共有相手管理 API の確認

作成者は、共有相手を追加・一覧取得・削除できます。
`<AREA_ID>` は共有したいメモグリッドの `id` に置き換えてください。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/shares/ \
  -d '{"username": "otheruser"}'
```

正常なら `201 Created` が返ります。
レスポンスの `share.id` を、以降の `<SHARE_ID>` に置き換えてください。

```bash
curl -i -u testuser:test-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/shares/
```

正常なら `200 OK` が返り、`shares` に `otheruser` が含まれます。

共有後は、`otheruser` でも詳細・GridCell 一覧・採点ができます。

```bash
curl -i -u otheruser:other-password \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

共有を解除します。

```bash
curl -i -u testuser:test-password \
  -X DELETE http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/shares/<SHARE_ID>/
```

正常なら `204 No Content` が返ります。
共有解除後は、`otheruser` で同じメモグリッドを取得すると `404 Not Found` が返ります。

### 10. 他ユーザーでは採点できないことの確認

`<GRID1_ID>` と `<GRID2_ID>` は、GridCell 一覧 API の `grids` に含まれる `id` に置き換えてください。

```bash
curl -i -u otheruser:other-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/<GRID1_ID>/ratings/ \
  -d '{"score": 8, "comment": "他ユーザーで採点"}'
```

`testuser` が作成したメモグリッドに属する `GridCell` を `otheruser` で採点しようとしているため、`404 Not Found` が返ります。

```bash
curl -i -u otheruser:other-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/bulk-ratings/ \
  -d '{"grid_ids": [<GRID1_ID>, <GRID2_ID>], "score": 5, "comment": "他ユーザーで一括採点"}'
```

一括採点でも同じく、他ユーザーの `GridCell` が含まれるため `400 Bad Request` が返ります。
この場合、一部だけ採点されることはありません。

### 11. エラー確認

ログイン情報を付けずに送ると、ログイン必須のため `401 Unauthorized` になります。

```bash
curl -i \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/<GRID1_ID>/ratings/ \
  -d '{"score": 8}'
```

点数が 1 から 10 の範囲外の場合は `400 Bad Request` になります。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/<GRID1_ID>/ratings/ \
  -d '{"score": 11}'
```

存在しない `grid_id` を一括採点に含めた場合も `400 Bad Request` になります。

```bash
curl -i -u testuser:test-password \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/bulk-ratings/ \
  -d '{"grid_ids": [<GRID1_ID>, 999999], "score": 5}'
```

存在しない `area_id` で点数付きグリッド一覧 API を呼ぶと、`404 Not Found` になります。

```bash
curl -i -u testuser:test-password \
  http://127.0.0.1:8000/api/maps/areas/999999/grids/
```

## 確認用 demo ページ

curl ではなくブラウザで簡単に確認したい場合は、確認用 demo ページを使えます。
このページは開発確認用です。JavaScript で Basic 認証情報を扱うため、本番向けのログイン画面ではありません。

まず、事前準備の手順で確認用ユーザーを作成しておきます。
既存のメモグリッドや `GridCell` がなくても、demo ページから作成できます。
API 内部では、メモグリッドを `MapArea` と呼びます。
その後、開発サーバーを起動します。

```bash
source .venv/bin/activate
python manage.py runserver
```

ブラウザで次を開きます。

```text
http://127.0.0.1:8000/api/maps/demo/
```

画面の username/password には、事前準備で作成した次の値を入力します。

```text
username: testuser
password: test-password
```

確認する流れ:

1. `メモグリッド作成` フォームで、中心緯度・中心経度・1マスの大きさ・縦横のマス数を確認する。
   例: `center_lat=35.695`, `center_lng=139.795`, `grid_size_meters=500`, `rows=6`, `cols=8`
2. 必要に応じて値を調整し、`メモグリッドを作成` を押す。
   `north / south / east / west` は入力せず、サーバー側で自動計算されます。
3. 作成したメモグリッドが一覧に表示され、選択状態になることを確認する。
4. `GridCell` が `rows * cols` 件作成されることを確認する。
   上記の例なら `6 * 8 = 48` 件です。
5. `Map Preview` に、選択中メモグリッドの範囲が四角で表示されることを確認する。
6. `Map Preview` 上に、`GridCell` 境界が薄い線で表示され、`calculated_score` に応じて薄く色分けされることを確認する。
7. メモグリッド作成後に自動生成された `GridCell` が、`Score Map` に表示されることを確認する。
8. 必要に応じて `GridCell を再取得` を押し、表示を更新できることを確認する。
9. `全体表示` で Score Map 全体が表示枠内に収まることを確認する。
10. `詳細表示` に切り替え、1マスを見やすいサイズで確認でき、必要に応じてスクロールできることを確認する。
11. Score Map の複数のマスをクリックし、`選択数` が増えることを確認する。
12. 選択済みのマスをもう一度クリックし、選択解除できることを確認する。
13. Score Map 上でドラッグし、範囲内の GridCell をまとめて選択できることを確認する。
14. `個別に入力し、まとめて採点` を選び、選択中 GridCell ごとに 1 から 10 の score を入力する。
15. `まとめて採点する` を押し、採点後に `Score Map` のスコア表示が更新されることを確認する。
16. 再度複数のマスを選択し、`選択グリッドを全て同じ値で採点` を選ぶ。
17. 共通 score に 1 から 10 の整数を入力し、`同じ値で採点する` を押して Score Map が更新されることを確認する。
18. `選択をすべて解除` で選択状態をリセットできることを確認する。
19. 作成者ユーザーで、`共有相手 username` に `otheruser` を入力して `共有相手を追加` を押す。
20. `共有相手一覧を取得` を押し、共有相手一覧に `otheruser` が表示されることを確認する。
21. 必要に応じて `otheruser` でログインし直し、共有メモグリッドを閲覧・採点できることを確認する。
22. 作成者ユーザーに戻り、`共有を解除` を押して共有相手一覧から消えることを確認する。

`Map Preview` は Leaflet と OpenStreetMap タイルを使う、開発確認用の地図表示です。
本番利用する場合は、地図タイル提供元の利用条件を確認してください。
現在は選択中メモグリッドの範囲と `GridCell` 境界を表示し、`GridCell` は `calculated_score` に応じて色分けします。
色分けの基準は `Score Map` と同じです。
採点後に GridCell 一覧が再読み込みされると、Map Preview 側の色分けも更新されます。
Map Preview は現時点では表示専用で、`GridCell` の選択や採点操作は `Score Map` で行います。
選択中メモグリッドの範囲が小さい場合、Map Preview は範囲を確認しやすくするため少し寄って表示します。
これは表示上のズーム調整であり、`grid_size_meters` や GridCell 生成ロジックは変わりません。
`Score Map` は、将来の地図背景に重ねる想定で、一枚の地図状の四角として表示します。
`全体表示` は Score Map 全体を表示枠内に収める表示です。
`詳細表示` は 1マスの見やすさを優先し、必要に応じて縦横スクロールして確認する表示です。
Score Map 上でドラッグすると、範囲内の GridCell をまとめて選択できます。
クリック選択・クリック解除も引き続き使え、選択後は個別入力まとめ採点や同じ値での一括採点を使えます。
`Map image URL` に画像 URL を入力すると、Score Map の背景として表示できます。
例えば `maps/static/maps/demo-map.png` に確認用画像を置いた場合は、`/static/maps/demo-map.png` と入力します。
画像アップロードや外部地図 API 連携は行わず、ブラウザで読み込める画像 URL を表示に使うだけです。
地図画像を使う場合は、利用条件や著作権を確認してください。
`calculated_score` は大きく表示します。
`GridCell ID` と `row_index` / `col_index` は、現在は確認用に小さく表示しています。
表示領域の縦横比は、メモグリッドとして扱う `MapArea` の `east - west` と `north - south` から概算します。
ただし、正確な地図投影ではなく、row/col による簡易グリッド配置は維持しています。
`grid_size_meters` は表示サイズではなく、GridCell 生成時の粒度を決める値です。
demo ページでは、中心座標・`grid_size_meters`・`rows`・`cols` からメモグリッドの範囲を作成します。

demo ページでは、メモグリッド作成時に GridCell が自動生成される前提のため、GridCell 自動生成 API を直接実行するボタンは表示していません。

## 依存関係を追加したいとき

必ず `.venv` を有効化してからインストールします。

```bash
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install パッケージ名
python -m pip freeze > requirements.txt
```

`pip install` だけを直接使うと、別の Python に入ってしまうことがあります。
このプロジェクトでは `python -m pip ...` の形を推奨します。

## Git に入れないもの

以下は PC ごとに作られるため、Git 管理しません。

- `.venv/`
- `db.sqlite3`
- `.env`
- `__pycache__/`
- `.pip-cache/`
- `.DS_Store`

## 環境変数

通常の開発では設定不要です。
端末ごとに値を変えたい場合は `.env.example` を参考に `.env` を作成し、ターミナルで読み込んでから Django を起動します。

```bash
cp .env.example .env
set -a
source .env
set +a
python manage.py runserver
```

## Codex で作業するとき

Codex には次の手順をセットアップとして伝えると安定します。

```bash
python3 -m venv .venv
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install --upgrade pip
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt
python manage.py migrate
```

テストや管理コマンドを依頼するときも、`.venv` を使う前提で次の形にすると PC 本体の環境に依存しにくくなります。

```bash
source .venv/bin/activate
python manage.py check
```

## 設計メモ

- `TASK.md`: 現在の目標変更と作業メモ
- `API_SPEC.md`: 地図採点 API の仕様案
- `AGENTS.md`: Codex に依頼するときの役割分担ルール
