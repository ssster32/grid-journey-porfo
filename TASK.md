# 現在のタスク

demo ページに MapArea 作成と GridCell 自動生成ボタンを追加してください。

# 目的

現在の確認用 demo ページでは、既存 API を使って次の操作ができます。

```text
MapArea 一覧取得
→ MapArea 選択
→ GridCell 一覧取得
→ 単体採点
→ 点数再集計
```

今回は demo ページから、確認用データ作成の一部もできるようにします。

追加する操作は次の 2 つです。

```text
MapArea 作成
GridCell 自動生成
```

これにより、ブラウザだけで次の流れを確認しやすくします。

```text
MapArea 作成
→ GridCell 自動生成
→ GridCell 一覧取得
→ 単体採点
→ 点数再集計
```

本格的な地図 UI ではなく、API 動作確認用の demo ページとして実装してください。

# 担当役割

Backend Developer / Documentation Writer / Tester

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
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`

# 編集してよいファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`
- `README.md`

必要な場合のみ:

- `maps/tests.py`
- `TASK.md`

# 変更しないファイル

指示がない限り、次は変更しないでください。

- `maps/models.py`
- `maps/migrations/`
- `maps/services.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/urls.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`
- `API_SPEC.md`

# 対象画面

```text
GET /api/maps/demo/
```

既存の確認用 demo ページに機能を追加してください。

# 追加する機能

## 1. MapArea 作成フォーム

demo ページ上に、MapArea 作成用のフォームを追加してください。

呼び出す API:

```text
POST /api/maps/areas/
```

最低限入力できる項目:

- `name`
- `description`
- `north`
- `south`
- `east`
- `west`
- `grid_size_meters`
- `source`

初期値は手動確認しやすい値を入れておいて構いません。

例:

```json
{
  "name": "Demo Area",
  "description": "created from demo page",
  "north": 35.7,
  "south": 35.69,
  "east": 139.8,
  "west": 139.79,
  "grid_size_meters": 500,
  "source": "demo"
}
```

期待する UI:

- 入力フォーム
- `MapArea を作成` ボタン
- 作成成功時に成功メッセージを表示
- 作成成功後、MapArea 一覧を再取得する
- 作成した MapArea を選択できる

## 2. GridCell 自動生成ボタン

選択中の MapArea に対して、GridCell 自動生成 API を実行できるボタンを追加してください。

呼び出す API:

```text
POST /api/maps/areas/{area_id}/grids/
```

期待する UI:

- MapArea を選択しているときだけ押せる
- `GridCell を自動生成` ボタン
- 成功時に成功メッセージを表示
- 成功後、GridCell 一覧を再取得する
- 既に GridCell がある場合は `400 Bad Request` のエラー内容を画面に表示する

# 既存機能との関係

既存の次の機能は壊さないでください。

- username/password 入力
- Basic 認証を使った API 呼び出し
- MapArea 一覧取得
- MapArea 選択
- GridCell 一覧取得
- 単体採点
- 採点後の GridCell 一覧再取得
- エラーや成功メッセージ表示

# UI の見た目

本格的なデザインは不要です。
ただし、確認しやすいように最低限整えてください。

方針:

- 1 ページ構成のままにする
- MapArea 作成フォームは認証・MapArea 一覧の近くに置く
- GridCell 自動生成ボタンは選択中 MapArea の情報の近くに置く
- テーブル表示は現状のままでよい
- エラーや成功メッセージを画面に表示する
- 外部ライブラリは追加しない

# README.md に追記・修正する内容

README の demo ページ確認手順を更新してください。

最低限、次を含めてください。

- demo ページで MapArea を作成できること
- 作成した MapArea を選択できること
- GridCell 自動生成ボタンを押せること
- 生成後に GridCell 一覧が表示されること
- そのまま score 入力と採点ができること
- 既に GridCell がある MapArea で再生成すると `400 Bad Request` になること
- JavaScript で Basic 認証情報を扱うため、本番向けではないこと

# テスト

基本的には既存の demo ページ表示テストを壊さなければ十分です。

ただし、HTML に追加した主要文言を確認したい場合は、`maps/tests.py` の demo ページテストに次のような確認を追加しても構いません。

例:

```python
self.assertContains(response, "MapArea を作成")
self.assertContains(response, "GridCell を自動生成")
```

# 今回やらないこと

- `models.py` の変更
- migration の作成
- 認証方式の変更
- Token 認証 / JWT 認証
- ユーザー登録 UI
- 本格ログイン UI
- MapArea 更新フォーム
- MapArea 削除ボタン
- 一括採点 UI
- Leaflet / Google Maps などの地図ライブラリ導入
- React / Vue などのフロントエンドフレームワーク導入
- 外部 API 連携
- 地図画像表示
- calculated_score による色分けグリッド表示
- 共有 MapArea の `is_public` 実装

# 注意点

- 既存 API の挙動を変えないでください。
- 既存テストを壊さないでください。
- 外部ライブラリは追加しないでください。
- 共用 PC 前提なので、グローバル環境に依存しないでください。
- demo ページは確認用であることが分かるようにしてください。
- JavaScript で Basic 認証情報を扱うため、本番向けではないことを README に短く書いてください。
- GridCell 自動生成 API は、作成者本人だけ実行できる現在の権限仕様を変えないでください。
- 既に GridCell がある MapArea への再生成はエラーとして扱ってください。

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
git diff -- maps/static/maps/demo.html maps/static/maps/demo.css maps/static/maps/demo.js README.md
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.css maps/static/maps/demo.js README.md
```

`maps/tests.py` を変更した場合は、次も確認してください。

```bash
git diff -- maps/tests.py
git diff --check -- maps/tests.py
```

可能であれば、開発サーバーを起動してブラウザでも確認してください。

```bash
.venv/bin/python manage.py runserver
```

ブラウザで開く URL:

```text
http://127.0.0.1:8000/api/maps/demo/
```

# 完了報告

短めでよいので、次を報告してください。

- 担当した役割
- 変更したファイル
- demo ページに追加した機能
- demo ページで確認できる流れ
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業