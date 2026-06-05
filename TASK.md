# TASK: 本サイト用ログイン画面の土台を作成する

## 目的

本サイト用画面として、ログイン画面の土台を追加してください。

前回の作業で、本サイト用の以下が追加済みです。

- `/maps/`
- `MapAreaPageListView`
- `maps/page_urls.py`
- `maps/templates/base.html`
- `maps/templates/maps/grid_list.html`

今回は、demo ページのように Basic 認証情報を各画面に置くのではなく、本サイト用のログイン画面を追加するための最小実装を行います。

## 実装方針

今回は「ログイン画面の土台」を作るだけです。

Django 標準の認証 view を使える場合は、それを優先してください。

想定URL:

```text
/login/
```

想定テンプレート:

```text
maps/templates/accounts/login.html
```

ただし、既存プロジェクトの構成上、`accounts/` アプリや既存テンプレート配置がある場合は、そちらに合わせてください。

## やってほしいこと

### 1. ログイン画面テンプレートを作成する

以下のようなテンプレートを作成してください。

```text
maps/templates/accounts/login.html
```

内容:

- `base.html` を継承する
- 見出しは `ログイン`
- username 入力欄
- password 入力欄
- ログインボタン
- ログイン失敗時のエラー表示
- `/maps/` へ戻るリンク、またはトップへ戻るリンク

デザインは最低限でよいです。
CSS の本格調整は今回しないでください。

### 2. ログインURLを追加する

`/login/` でログイン画面を表示できるようにしてください。

Django 標準の `LoginView` を使える場合は、以下のような方針で実装してください。

```python
from django.contrib.auth.views import LoginView

path(
    "login/",
    LoginView.as_view(template_name="accounts/login.html"),
    name="login",
)
```

ただし、既存の `config/urls.py` や URL 構成に合わせて、より自然な場所に追加してください。

### 3. ログイン後の遷移先を設定する

ログイン成功後は、ひとまず `/maps/` に移動する方針にしてください。

方法は既存構成に合わせてください。

候補:

- `settings.py` に `LOGIN_REDIRECT_URL = "/maps/"` を追加
- `LoginView.as_view(..., next_page="/maps/")` を使う
- 既に設定がある場合はそれを尊重する

既存設定がある場合は、無理に上書きしないでください。

### 4. base.html のヘッダーにログインリンクを追加する

`base.html` に最低限のログイン導線を追加してください。

例:

- 未ログインなら `ログイン`
- ログイン済みなら `ログイン中: username`

ログアウト機能は今回は実装しなくてよいです。

ログイン状態の判定は、Django テンプレート上で可能なら以下のようにしてください。

```django
{% if user.is_authenticated %}
  ログイン中: {{ user.username }}
{% else %}
  <a href="{% url 'login' %}">ログイン</a>
{% endif %}
```

ただし、既存の `base.html` の構成に合わせて調整してください。

### 5. 今回は /maps/ をログイン必須にしない

今回はログイン画面の土台追加が目的です。

`/maps/` の `MapAreaPageListView` に `LoginRequiredMixin` を付けるかどうかは、次回以降のタスクで検討します。

今回は `/maps/` をログイン必須にしなくてよいです。

## 今回は実装しないこと

以下は今回やらないでください。

- メモグリッド一覧のAPI連携
- `/maps/` のログイン必須化
- ログアウト機能
- ユーザー登録機能
- パスワード再設定
- Token 認証の画面対応
- demo.js の変更
- demo.css の移植
- Leaflet 表示
- 採点処理
- 共有相手管理
- model 変更
- migration 作成
- 既存 API の挙動変更
- demo ページ削除
- `memo.md` の更新

## 注意

- 確認コマンドやテストコマンドは実行しないでください。
- コマンド実行結果の報告は不要です。
- 既存 API の URL や挙動を変えないでください。
- demo ページを壊さないでください。
- 既に未コミット差分がある場合は、今回の作業対象以外を変更しないでください。

## 作業後に報告してほしいこと

作業後、以下を説明してください。

- 追加・変更したファイル
- 追加した URL
- 使用した view
- ログイン成功後の遷移先
- 今回は未実装のこと
- 次にやるとよい作業