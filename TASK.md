# TASK: サイト名・サービス名を Grid Journey に統一する

## 目的

提出用に、サイト名およびサービス名を `Grid Journey` に統一する。

画面上のタイトル、ヘッダー、ログイン画面、一覧画面、作成画面、詳細画面などで、サービス名が分かる表示に整える。

## 対象ファイル

主に確認・変更:

* `maps/templates/base.html`
* `maps/templates/accounts/login.html`
* `maps/templates/maps/grid_list.html`
* `maps/templates/maps/grid_create.html`
* `maps/templates/maps/grid_detail.html`

必要な場合のみ確認・変更:

* `maps/static/maps/css/site.css`
* `maps/static/maps/js/grid-list.js`
* `maps/static/maps/js/grid-create.js`
* `maps/static/maps/js/grid-detail.js`
* `API_SPEC.md`

## やること

* サイト名・サービス名として `Grid Journey` を表示する
* `<title>` に入っているサイト名・サービス名を `Grid Journey` に揃える
* ヘッダーやナビゲーションにサイト名が表示されている場合、`Grid Journey` にする
* ログイン画面にサービス名として `Grid Journey` を表示する
* 一覧画面・作成画面・詳細画面のタイトルや説明文で、サービス名が必要な箇所は `Grid Journey` に揃える
* 既存の「メモグリッド」という機能名は、必要な箇所ではそのまま残す
* 内部的な model 名、API 名、変数名は変更しない

## 表示方針

サービス名と機能名は分けて扱う。

```text
サービス名:
Grid Journey

機能名:
メモグリッド
グリッド
マス
スコア
```

表示例:

```text
Grid Journey
メモグリッド一覧
```

```text
Grid Journey
新しいメモグリッドを作成
```

```text
名称未設定 | Grid Journey
```

## 置き換え方針

* `ポートフォリオ`、`作品ショーケース`、仮のサイト名、古いサービス名のような表示が残っていれば `Grid Journey` に置き換える
* ただし、説明文の中で「ポートフォリオ作品として」など開発文脈の意味で使っている箇所がある場合は、無理に置き換えない
* `メモグリッド` は機能名なので、全部 `Grid Journey` に置き換えない
* `MapArea`、`GridCell`、`GridRating` などの内部名は変更しない
* URL、APIエンドポイント、serializer名、view名、JS関数名、CSS class名は変更しない

## 具体的な確認箇所

### base.html

* ヘッダー・ナビゲーションのブランド名
* `<title>` の共通部分
* ログアウト・一覧・作成などのリンク表示

### login.html

* ログイン画面のタイトル
* 見出し
* 補助説明文
* サービス名が表示される箇所

### grid_list.html / grid-list.js

* 一覧画面の `<title>`
* 見出し
* 空状態の案内文
* 取得失敗時の案内文
* 必要なら `Grid Journey` のサービス名を自然に表示する

### grid_create.html / grid-create.js

* 作成画面の `<title>`
* 見出し
* 補助説明文
* 作成ボタン周辺の補助文
* `Grid Journey` を入れると不自然な箇所は無理に入れない

### grid_detail.html / grid-detail.js

* 詳細画面の `<title>`
* 見出し・補助説明文
* 詳細画面ではメモグリッド名を主役にし、サービス名は `<title>` やヘッダー側で分かればよい

## やらないこと

* model / migration の変更
* DB値の変更
* APIエンドポイントの変更
* serializer名、view名、URL名、JS関数名、CSS class名の変更
* 作成処理の変更
* 一覧取得処理の変更
* 詳細画面の地図・採点処理の変更
* 作成画面のMap Preview、クロスヘア、ズーム操作ボタン、地図中央座標表示の変更
* 下部固定作成ボタンの挙動変更
* 自動設定時の注意文の表示条件変更
* demo.js / demo.css の変更
* `memo.md` 更新

## 注意

* 表示名の統一が目的
* 内部実装名は変えない
* 機能名としての `メモグリッド` は残してよい
* サービス名を入れすぎて画面がくどくならないようにする
* 既存の日本語UIの自然さを優先する
* 画面タイトルやヘッダーで `Grid Journey` が分かる状態にする
* 既存のログイン、一覧、作成、詳細、共有、削除、採点機能を壊さない
* 確認コマンドやテストコマンドは実行しないこと

## 作業後に報告してほしいこと

* 変更したファイル
* `Grid Journey` に統一した表示箇所
* `メモグリッド` を機能名として残した箇所
* `<title>` を変更した箇所
* ヘッダー・ログイン画面・一覧画面・作成画面・詳細画面での変更内容
* 内部名、API、model、migration を変更していないこと
* 作成処理、一覧取得、詳細画面の地図・採点処理を変更していないこと
* demo.js / demo.css、memo.md を変更していないこと
* 確認コマンドやテストコマンドを実行していないこと
