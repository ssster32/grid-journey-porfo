# TASK: Django標準の仕組みで新規ユーザー登録画面を追加する

## 目的

現在はログイン済みユーザー向けのメモグリッド機能はあるが、新規ユーザー登録画面がない。

提出用に、初めて利用する人が自分でアカウントを作成できるようにするため、Django標準の仕組みを使って新規ユーザー登録画面を追加する。

サービス名は `Grid Journey` とする。

## 方針

Django標準の認証機能を使う。

* `django.contrib.auth.forms.UserCreationForm`
* `django.views.generic.CreateView`
* Django標準の `User` モデル

独自のユーザーモデルや複雑な認証機能は追加しない。

## 対象ファイル

主に確認・変更:

* `maps/views.py`
* `maps/urls.py`
* `maps/templates/accounts/login.html`
* 新規テンプレート:

  * `maps/templates/accounts/signup.html`

必要な場合のみ確認・変更:

* `maps/templates/base.html`
* `maps/static/maps/css/site.css`
* `API_SPEC.md`
* `memo.md`

## やること

* 新規ユーザー登録用の view を追加する
* URL を追加する

  * 例: `/signup/`
* 新規ユーザー登録テンプレートを追加する
* ログイン画面から新規登録画面へ移動できるリンクを追加する
* 新規登録画面からログイン画面へ戻れるリンクを追加する
* 登録成功後はログイン画面へ遷移する
* 登録成功時に、可能なら「登録が完了しました。ログインしてください。」のようなメッセージを表示する
* 既存のログイン処理を壊さない
* 既存の `/maps/` ログイン必須挙動を壊さない

## URL案

```text
/signup/
```

## 画面表示案

### 新規登録画面

```text
Grid Journey
新規アカウント作成

ユーザー名
パスワード
パスワード確認

アカウントを作成
すでにアカウントをお持ちの方はログイン
```

### ログイン画面へのリンク追加

ログイン画面に以下のような導線を追加する。

```text
アカウントをお持ちでない方は新規登録
```

## 注意

* 独自ユーザーモデルは作らない
* model / migration は追加しない
* 既存ユーザーや既存データを変更しない
* ログイン画面の既存処理を壊さない
* `/maps/`、`/maps/new/`、`/maps/<area_id>/` のログイン必須処理を壊さない
* 登録直後に自動ログインさせる必要はない

  * 今回は登録後ログイン画面へ遷移でよい
* パスワードバリデーションは Django 標準のものを使う
* フォームエラーは画面上に表示する
* サービス名は `Grid Journey` に揃える
* 既存の見た目に合わせる
* demo.js / demo.css は変更しない
* API、地図、採点、共有、削除、作成画面の Map Preview は変更しない
* 確認コマンドやテストコマンドは実行しないこと

## 実装メモ

* `UserCreationForm` を使う
* `CreateView` を使う場合は `success_url` をログイン画面にする
* 必要なら `reverse_lazy()` を使う
* 登録成功メッセージを出す場合は Django messages framework を使う
* 既存の `LoginView` とテンプレート構成に合わせる
* `signup.html` は `login.html` と同じデザイン系統にする
* CSS が必要なら `site.css` に最小限追加する

## 作業後に報告してほしいこと

* 変更したファイル
* 追加したURL
* 使用したDjango標準機能
* 登録成功後の遷移先
* ログイン画面に追加した導線
* 新規登録画面に追加した導線
* フォームエラー表示の有無
* model / migration を変更していないこと
* 既存ログイン処理を変更していないこと
* `/maps/` などのログイン必須挙動を変更していないこと
* demo.js / demo.css、API、地図、採点、共有、削除、Map Preview を変更していないこと
* 確認コマンドやテストコマンドを実行していないこと
