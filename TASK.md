# TASK: /maps/<area_id>/ の単体採点フォームから採点APIを呼び、採点後にマス一覧を再取得する

## 目的

本サイト用のメモグリッド詳細画面で、選択中のマスに表示している単体採点フォームから、実際に採点 API を呼び出せるようにしてください。

現在、以下は実装済みです。

- `/login/`
- Django 標準 `LoginView`
- `/maps/`
- `/maps/` のログイン必須化
- `/maps/` でメモグリッド一覧を API から取得して表示
- `/maps/<area_id>/`
- `MapAreaPageDetailView`
- `maps/templates/maps/grid_detail.html`
- `maps/static/maps/js/grid-detail.js`
- 詳細画面で `GET /api/maps/areas/<area_id>/grids/` を呼び、マス数と簡易一覧を表示
- マス一覧から任意のマスを選択
- 選択中のマス詳細を表示
- 選択中のマスに `is-selected` class を付ける
- 選択中マス詳細の近くに単体採点フォームの空 UI を表示
- 本サイト側 JS は Session 認証前提で、Basic 認証は使っていない

今回は、単体採点フォームを `POST /api/maps/grids/<grid_id>/ratings/` に接続し、採点成功後にマス一覧を再取得して表示を更新してください。

## 重要な方針

本サイト画面では、demo ページのような Basic 認証欄は使いません。

現在の本サイト画面は Django のログイン状態を使う方針です。  
そのため、採点 API を呼ぶときも、ログイン済みの Session 認証を前提にしてください。

以下は本サイト側に追加しないでください。

- username 入力欄
- password 入力欄
- `btoa(username:password)`
- `Authorization: Basic ...`

今回の採点 API 呼び出しは `POST` なので、Session 認証で呼ぶ場合は CSRF 対応が必要になる可能性が高いです。

Django の CSRF cookie から token を取得し、`X-CSRFToken` ヘッダーを付ける実装を検討してください。

例:

```javascript
fetch(`/api/maps/grids/${gridId}/ratings/`, {
  method: "POST",
  credentials: "same-origin",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": csrfToken,
  },
  body: JSON.stringify({
    score,
    comment,
  }),
});
```

既存プロジェクトの構成上、別の適切な CSRF 取得方法がある場合は、それに合わせてください。

## 対象ファイル

主に以下を確認してください。

- `maps/templates/maps/grid_detail.html`
- `maps/static/maps/js/grid-detail.js`
- `maps/templates/base.html`
- `API_SPEC.md`

必要に応じて以下も確認してよいです。

- `maps/views.py`
- `maps/page_urls.py`
- `maps/urls.py`
- `maps/serializers.py`
- `maps/static/maps/demo.js`

## 実装内容

### 1. 採点フォームの disabled を解除する

現在、選択中マスに表示される採点フォームの送信ボタンは disabled または未実装扱いになっているはずです。

今回、マス選択時に表示される採点フォームから実際に送信できるようにしてください。

ただし、マス未選択時はフォームを表示しない、または送信できない状態を維持してください。

### 2. score / comment を読み取る

採点フォームから以下を読み取ってください。

- `score`
  - 必須
  - 1〜10 の整数
- `comment`
  - 任意
  - 空文字でも可

画面側でも最低限、`score` が 1〜10 の整数か確認してください。

不正な場合は API を呼ばず、フォーム付近にエラーメッセージを表示してください。

表示例:

```text
score は 1 から 10 の整数で入力してください。
```

### 3. CSRF token を取得する処理を追加する

`POST` API 呼び出し用に、CSRF token を取得する処理を追加してください。

候補:

```javascript
function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmedCookie = cookie.trim();
    if (trimmedCookie.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmedCookie.slice(name.length + 1));
    }
  }
  return "";
}
```

そして、

```javascript
const csrfToken = getCookie("csrftoken");
```

のように取得してください。

既に共通の CSRF 取得処理がある場合は、重複して作らず再利用してください。

### 4. 採点 API を呼び出す

選択中のマス ID を使って、以下の API を呼び出してください。

```text
POST /api/maps/grids/<grid_id>/ratings/
```

リクエスト body:

```json
{
  "score": 8,
  "comment": "メモ"
}
```

`comment` は空文字でも送信して構いません。

API 呼び出しでは、Session 認証前提として `credentials: "same-origin"` を使ってください。

Basic 認証ヘッダーは付けないでください。

### 5. 送信中・成功・失敗メッセージを表示する

採点フォーム付近に、送信状態を表示してください。

表示例:

送信中:

```text
採点を送信しています。
```

成功:

```text
採点しました。
```

失敗:

```text
採点に失敗しました。
```

失敗時は、可能なら HTTP ステータスや API から返ったエラー内容も開発中に分かる範囲で表示してください。

### 6. 採点成功後にマス一覧を再取得する

採点 API が成功したら、詳細画面で使っている GridCell 一覧を再取得してください。

既存の処理で `GET /api/maps/areas/<area_id>/grids/` を呼んでいる関数がある場合は、それを再利用してください。

採点後に再取得する目的:

- `average_user_score`
- `rating_count`
- `calculated_score`
- `score_updated_at`

などの表示を更新するためです。

### 7. 選択中のマス詳細も更新する

マス一覧を再取得した後、選択中のマス ID がまだ存在する場合は、その新しいデータで選択中マス詳細を更新してください。

例:

```text
採点前: 表示スコア 2.0
採点後: 表示スコア 5.0
```

のように、再取得後の値が反映されるようにしてください。

選択中のマス ID が再取得後の一覧に存在しない場合は、選択状態を解除し、以下のような表示にしてください。

```text
選択中のマスを再取得後に見つけられませんでした。
```

### 8. 採点フォームも再描画する

採点後にマス一覧・選択中マス詳細を更新したあと、採点フォームも選択中マスに合わせて表示してください。

フォームの値は、採点後に初期値へ戻しても、入力値を維持しても構いません。  
実装が簡単な方を選んでください。

ただし、成功メッセージはユーザーが分かるように残してください。

### 9. 0件時・取得失敗時は採点できないようにする

GridCell が0件の場合や、GridCell 一覧取得に失敗した場合は、採点フォームを表示しない、または送信できない状態にしてください。

既存の表示:

```text
表示できるマスがありません。
```

```text
マス一覧を取得できなかったため、マスを選択できません。
```

に合わせ、採点フォーム側でも以下のような表示にしてください。

```text
表示できるマスがないため、採点フォームは表示できません。
```

```text
マス一覧を取得できなかったため、採点フォームは表示できません。
```

### 10. 画面上の呼称をユーザー向けにする

画面上では以下の呼称を優先してください。

- `GridCell` → `マス`
- `GridRating` → `採点`
- `MapArea` → `メモグリッド`

内部変数名は既存コードに合わせて構いません。

## 今回は実装しないこと

以下は今回やらないでください。

- 複数マス採点
- 一括採点 API 呼び出し
- 複数マス選択
- Leaflet 地図表示
- 地図上の GridCell 境界表示
- 地図上のマス選択
- Shift + ドラッグ範囲選択
- 自動採点理由の詳細表示
- 共有相手管理
- 削除機能
- メモグリッド作成画面
- `/maps/new/` の実装
- demo.js の変更
- demo.css の大規模移植
- Basic 認証欄の追加
- Token 認証の画面対応
- ログイン画面の作り込み
- ユーザー登録機能
- パスワード再設定
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
- demo.js を本サイト用に直接改変しないでください。
- Basic 認証処理を本サイト側 JS に追加しないでください。
- CSRF 対応を入れる場合も、既存のログイン画面・demo ページ・API の挙動を壊さないでください。
- 既に未コミット差分がある場合は、今回の作業対象以外を変更しないでください。
- `TASK.md` は、ユーザーが貼り付けた内容以外に勝手に更新しないでください。
- `memo.md` は明示指示がないため更新しないでください。

## 作業後に報告してほしいこと

作業後、以下を説明してください。

- 追加・変更したファイル
- 変更した JS の主な内容
- 採点フォームの送信方法
- CSRF 対応の方法
- API 呼び出し方法
- Basic 認証を使っていないこと
- 採点成功後の再取得処理
- 選択中マス詳細の更新方法
- 0件時・取得失敗時の採点フォーム表示
- 今回は未実装のこと
- 次にやるとよい作業

## 確認観点

コマンドは実行しなくてよいですが、実装後にユーザーが確認しやすいように、以下の確認観点を説明してください。

- ログイン後に `/maps/` を開く
- 一覧から任意のメモグリッド詳細へ移動する
- 任意のマスを選択する
- score に 1〜10 の整数を入力する
- comment を任意で入力する
- 採点する
- 採点成功メッセージが表示される
- マス一覧が再取得される
- 選択中マス詳細の `平均スコア` / `採点数` / `表示スコア` / `スコア更新日時` が更新される
- score が範囲外の場合、API を呼ばずにエラー表示される
- 0件時に採点フォームが壊れない
- API取得失敗時に採点フォームが壊れない
- 未ログインで `/maps/<area_id>/` にアクセスすると `/login/` に誘導される
- 共有されていない他ユーザーの `/maps/<area_id>/` は 404 になる
- demo ページが壊れていない