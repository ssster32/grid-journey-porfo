# 現在のタスク

GridCell を表形式または簡易グリッド状に表示し、`calculated_score` に応じて色を変えてください。

# 目的

現在の demo ページでは、GridCell 一覧をテーブルで確認できます。

今回は、`calculated_score` を視覚的に確認しやすくするため、GridCell の表示を改善します。

本格的な地図表示ではなく、確認用 demo ページ上で次のことが分かれば十分です。

```text
どの GridCell がどの位置にあるか
どの GridCell の calculated_score が高いか低いか
採点後に色が変わるか
```

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

既存の確認用 demo ページに表示改善を追加してください。

# 実装方針

GridCell 一覧について、次のどちらかの方針で実装してください。

## 推奨: 簡易グリッド状表示を追加する

現在のテーブル表示は残したまま、上部または下部に簡易グリッド状の表示を追加してください。

GridCell の `row_index` と `col_index` を使って、CSS Grid でマス目状に表示します。

期待する表示:

```text
row_index / col_index に対応したマス目
各マスに GridCell ID と calculated_score を表示
calculated_score に応じて背景色が変わる
```

## 代替: 表形式のまま色を付ける

簡易グリッド状表示が大きくなりすぎる場合は、既存テーブルの行または `calculated_score` セルに色を付けても構いません。

ただし、できれば簡易グリッド状表示を優先してください。

# 色分けルール

`calculated_score` に応じて、分かりやすく色を変えてください。

例:

| calculated_score | 表示イメージ |
| --- | --- |
| 0 以上 3 未満 | 低スコア色 |
| 3 以上 6 未満 | 中スコア色 |
| 6 以上 8 未満 | 高スコア色 |
| 8 以上 | 最高スコア色 |

具体的な色は任せます。
ただし、文字が読みにくくならないようにしてください。

色分けは JavaScript の関数にまとめてください。

例:

```javascript
function scoreClass(score) {
  if (score >= 8) {
    return "score-very-high";
  }
  if (score >= 6) {
    return "score-high";
  }
  if (score >= 3) {
    return "score-middle";
  }
  return "score-low";
}
```

# demo ページの機能要件

既存の次の機能は壊さないでください。

- username/password 入力
- MapArea 作成
- MapArea 一覧取得
- MapArea 選択
- GridCell 自動生成
- GridCell 一覧取得
- 単体採点
- 採点後の GridCell 一覧再取得
- エラーや成功メッセージ表示

採点後に GridCell 一覧を再取得したとき、色分け表示も更新されるようにしてください。

# UI の見た目

本格的な地図 UI は不要です。
ただし、確認しやすいように最低限整えてください。

方針:

- 既存の 1 ページ構成を維持
- 簡易グリッドはテーブルの前に置くのがおすすめ
- 各マスは小さくてもよいが、`id` と `calculated_score` は見えるようにする
- マスが多い場合は横スクロールしてよい
- 外部ライブラリは追加しない
- Leaflet / Google Maps は使わない

# README.md に追記・修正する内容

README の demo ページ確認手順を短く更新してください。

最低限、次を含めてください。

- GridCell が簡易グリッド状または色付き表示で確認できること
- `calculated_score` に応じて色が変わること
- 採点後に再取得され、色も更新されること

# テスト

基本的には既存の demo ページ表示テストを壊さなければ十分です。

ただし、HTML に追加した主要文言を確認したい場合は、`maps/tests.py` の demo ページテストに次のような確認を追加しても構いません。

例:

```python
self.assertContains(response, "Score Map")
```

JavaScript の詳細な表示ロジックは、Django の通常テストでは確認しにくいため、次の確認を行ってください。

```bash
node --check maps/static/maps/demo.js
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
- 実際の地図座標に合わせた正確な描画
- 共有 MapArea の `is_public` 実装

# 注意点

- 既存 API の挙動を変えないでください。
- 既存テストを壊さないでください。
- 外部ライブラリは追加しないでください。
- 共用 PC 前提なので、グローバル環境に依存しないでください。
- demo ページは確認用であることが分かるようにしてください。
- calculated_score が 0 の GridCell も見えるようにしてください。
- score が数値でない場合や null の場合でも表示が崩れないようにしてください。
- row_index / col_index が欠けている場合でも、ページ全体が壊れないようにしてください。

# 確認方法

作業後に次を実行してください。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
node --check maps/static/maps/demo.js
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
- demo ページに追加した表示
- 色分けルール
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業