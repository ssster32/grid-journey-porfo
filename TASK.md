# TASK: 画面上の英語・開発者向け表記を日本語に統一する

## 目的

本サイト画面上に残っている英語表記・開発者向け表記を、提出時に自然に見える日本語表記へ整える。

## 対象画面

- `/login/`
- `/maps/`
- `/maps/new/`
- `/maps/<area_id>/`

## 対象ファイル

主に以下を確認:

- `maps/templates/accounts/login.html`
- `maps/templates/maps/grid_list.html`
- `maps/templates/maps/grid_create.html`
- `maps/templates/maps/grid_detail.html`
- `maps/static/maps/js/grid-list.js`
- `maps/static/maps/js/grid-create.js`
- `maps/static/maps/js/grid-detail.js`

必要な場合のみ:

- `maps/static/maps/css/site.css`

## やること

- 画面上に表示される英語・開発者向け表記を探す
- 必要な範囲で自然な日本語に変更する
  - `Map Preview` → `地図プレビュー`
  - `username` → `ユーザー名`
  - `score` → `スコア` または `評価`
  - `comment` → `コメント`
- 詳細画面の `共有相手 username` は `共有相手のユーザー名` にする
- 既存機能・フォーム送信・API通信は変更しない

## やらないこと

- API 変更
- model / migration 変更
- form name / id / data属性の変更
- JSロジックの大幅変更
- 大規模デザイン変更
- demo.js / demo.css の変更
- `memo.md` 更新

## 注意

- 変更するのは「画面に表示される文言」を中心にすること
- 内部変数名やAPI項目名は、必要がなければ変更しないこと
- 既存の作成・一覧・詳細・採点・共有・削除を壊さないこと
- 翻訳しすぎて意味が分かりにくくならないようにすること
- 確認コマンドやテストコマンドは実行しないこと
- demo ページを壊さないこと

## 作業後に報告してほしいこと

- 変更したファイル
- 日本語化した主な表記
- あえて変更しなかった表記があればその理由
- 既存機能を変更していないこと
- 確認コマンドやテストコマンドを実行していないこと