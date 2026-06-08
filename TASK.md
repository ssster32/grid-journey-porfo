# TASK: grid-detail.js の API 通信処理を grid-detail-api.js に切り出す

## 目的

本サイト用のメモグリッド詳細画面で使っている `maps/static/maps/js/grid-detail.js` から、API 通信処理だけを `grid-detail-api.js` に切り出してください。

前回の整理で、`formatter / utility` 系の関数は以下へ切り出し済みです。

```text
maps/static/maps/js/grid-detail-utils.js
```

現在の読み込み順は以下の想定です。

```text
Leaflet JS
grid-detail-utils.js
grid-detail.js
```

今回はその次のリファクタリング段階として、`fetch()` を使う API 通信処理を `grid-detail-api.js` に分離します。

## 重要な方針

今回は **API 通信処理だけを切り出す** タスクです。

やること:

* `grid-detail-api.js` を新規追加する
* `grid-detail.js` 内の API 通信関数を、できる範囲で `grid-detail-api.js` に移す
* `grid-detail-api.js` は `window.GridDetailApi` として公開する
* `grid_detail.html` で `grid-detail-api.js` を `grid-detail.js` より先に読み込む
* `grid-detail.js` は `window.GridDetailApi` 経由で API 関数を呼ぶ
* 成功後の DOM 更新・state 更新・画面遷移は、基本的に `grid-detail.js` 側に残す
* 既存挙動を変えない

やらないこと:

* ES modules 化
* `import` / `export` の導入
* `type="module"` の導入
* Leaflet 処理の切り出し
* 選択状態管理の切り出し
* DOM 描画処理の切り出し
* 採点フォーム描画の変更
* 共有管理 UI の変更
* API 仕様変更
* 新機能追加

## 対象ファイル

主に以下を確認してください。

* `maps/static/maps/js/grid-detail.js`
* `maps/static/maps/js/grid-detail-utils.js`
* `maps/templates/maps/grid_detail.html`

必要に応じて以下も確認してよいです。

* `maps/static/maps/js/grid-list.js`
* `maps/static/maps/js/grid-create.js`
* `maps/static/maps/demo.js`
* `API_SPEC.md`

## 実装方針

### 1. 新規ファイルを追加する

以下のファイルを新規追加してください。

```text
maps/static/maps/js/grid-detail-api.js
```

このファイルでは、ES modules ではなく、既存の通常 script 読み込みに合わせて、`window.GridDetailApi` に API 関数をまとめて公開してください。

例:

```javascript
(() => {
  "use strict";

  async function fetchGridCells(areaId) {
    // ...
  }

  window.GridDetailApi = {
    fetchGridCells,
  };
})();
```

### 2. grid_detail.html で読み込み順を追加する

`maps/templates/maps/grid_detail.html` で、`grid-detail-api.js` を `grid-detail.js` より先に読み込んでください。

読み込み順の想定:

```text
Leaflet JS
grid-detail-utils.js
grid-detail-api.js
grid-detail.js
```

例:

```django
<script src="{% static 'maps/js/grid-detail-utils.js' %}"></script>
<script src="{% static 'maps/js/grid-detail-api.js' %}"></script>
<script src="{% static 'maps/js/grid-detail.js' %}"></script>
```

既存の `extra_js` や scripts block の構成に合わせてください。

重要:

* Leaflet の読み込み順を壊さないでください。
* `grid-detail.js` が実行される前に、`window.GridDetailUtils` と `window.GridDetailApi` が定義されている状態にしてください。

### 3. ES modules 化はしない

今回は安全優先の段階的リファクタリングです。

以下は導入しないでください。

```javascript
import ...
export ...
```

また、script タグに以下も追加しないでください。

```html
type="module"
```

理由:

* 読み込み順やスコープの変化で既存処理が壊れる可能性がある
* 今回は API 通信処理の分離だけが目的
* module 化は別タスクで検討する

## 切り出す API 通信処理

### 4. grid-detail.js 内の API 通信処理を確認する

`grid-detail.js` 内で、`fetch()` を使っている処理を確認してください。

切り出し候補:

* GridCell 一覧取得
* 単体採点
* 一括採点
* メモグリッド削除
* 共有相手一覧取得
* 共有相手追加
* 共有相手削除

現在の関数名は既存コードに合わせて確認してください。

想定される既存関数:

* `loadGridCells()`
* `submitRating()`
* `submitBulkRating()`
* `deleteCurrentArea()`
* `loadShares()`
* `addShare()`
* `deleteShare()`

ただし、これらを丸ごと移すのではなく、**fetch してレスポンスを返す部分だけ**を切り出す方針にしてください。

### 5. grid-detail-api.js に作る関数

以下のような API 専用関数を `grid-detail-api.js` に作ってください。

実際の関数名は既存コードに合わせて構いません。

```javascript
async function fetchGridCells(areaId) {
  // GET /api/maps/areas/<area_id>/grids/
}

async function submitRating(gridId, payload) {
  // POST /api/maps/grids/<grid_id>/ratings/
}

async function submitBulkRating(payload) {
  // POST /api/maps/grids/bulk-ratings/
}

async function deleteArea(areaId) {
  // DELETE /api/maps/areas/<area_id>/
}

async function fetchShares(areaId) {
  // GET /api/maps/areas/<area_id>/shares/
}

async function addShare(areaId, payload) {
  // POST /api/maps/areas/<area_id>/shares/
}

async function deleteShare(areaId, shareId) {
  // DELETE /api/maps/areas/<area_id>/shares/<share_id>/
}
```

`window.GridDetailApi` では、これらを公開してください。

例:

```javascript
window.GridDetailApi = {
  fetchGridCells,
  submitRating,
  submitBulkRating,
  deleteArea,
  fetchShares,
  addShare,
  deleteShare,
};
```

### 6. grid-detail-api.js の責務

`grid-detail-api.js` の責務は、API を呼んで結果を返すことです。

含めてよい処理:

* `fetch()`
* URL の組み立て
* method 指定
* `credentials: "same-origin"`
* `Content-Type: "application/json"`
* `X-CSRFToken`
* body の JSON 化
* `readResponse()` を使ったレスポンス読み取り
* HTTP エラー時に例外を投げる、または既存の方針に合わせて返す

含めない処理:

* DOM 更新
* メッセージ表示
* `renderGrids()`
* `renderSelectionState()`
* `loadGridCells()` の再実行判断
* `window.location.href` による画面遷移
* ボタン disabled の切り替え
* form の値読み取り
* selectedGridIds の更新
* Leaflet の再描画

つまり、API の成功後に何をするかは、基本的に `grid-detail.js` 側に残してください。

### 7. grid-detail-utils.js を利用する

`grid-detail-api.js` では、前回追加した `window.GridDetailUtils` を利用して構いません。

利用候補:

* `getCookie`
* `readResponse`
* `errorText`

ただし、`grid-detail-api.js` が読み込まれる前に `grid-detail-utils.js` が読み込まれる必要があります。

`grid-detail-api.js` の先頭で、必要なら最低限のガードを入れてください。

例:

```javascript
const utils = window.GridDetailUtils;
if (!utils) {
  console.error("GridDetailUtils is not loaded.");
  return;
}
```

既存プロジェクトの書き方に合わせてください。

### 8. CSRF 対応を維持する

POST / DELETE では、既存と同じように CSRF token を付けてください。

対象:

* 単体採点
* 一括採点
* メモグリッド削除
* 共有相手追加
* 共有相手削除

例:

```javascript
headers: {
  "Content-Type": "application/json",
  "X-CSRFToken": utils.getCookie("csrftoken"),
}
```

DELETE の場合、既存コードが `Content-Type` を付けていないなら、無理に追加しなくて構いません。

重要:

* Basic 認証は追加しない
* `Authorization: Basic ...` は追加しない
* `credentials: "same-origin"` は維持する

### 9. grid-detail.js 側の呼び出しを置き換える

`grid-detail.js` では、直接 `fetch()` していた箇所を `window.GridDetailApi` 経由に置き換えてください。

例:

```javascript
const api = window.GridDetailApi;

const grids = await api.fetchGridCells(areaId);
```

ただし、成功後の処理は `grid-detail.js` に残してください。

例:

* GridCell 取得成功後:

  * `state.gridsById` を更新
  * `renderGrids()` を呼ぶ
  * 地図境界・ラベルを再描画する
  * 選択状態を維持する

* 単体採点成功後:

  * 成功メッセージ表示
  * `loadGridCells()` 再実行

* 一括採点成功後:

  * 成功メッセージ表示
  * `loadGridCells()` 再実行

* 削除成功後:

  * `/maps/` へ遷移

* 共有相手追加・削除成功後:

  * `loadShares()` 再実行

これらは今回 `grid-detail-api.js` に移さないでください。

### 10. エラー表示の挙動を変えない

API 呼び出しを切り出した後も、エラー表示文言や表示場所は変えないでください。

以下が変わらないようにしてください。

* GridCell 一覧取得失敗
* 単体採点失敗
* 一括採点失敗
* 削除失敗
* 共有相手一覧取得失敗
* 共有相手追加失敗
* 共有相手削除失敗

`grid-detail-api.js` では、既存の `readResponse()` / `errorText()` と同じ方針でエラー情報を返すか、throw してください。

`grid-detail.js` 側で既存の catch 処理・メッセージ表示を維持してください。

### 11. form 読み取りや validation は移さない

以下は `grid-detail.js` に残してください。

* 単体採点フォームの score / comment 読み取り
* 一括採点フォームの score / comment / grid_ids 組み立て
* score の 1〜10 整数チェック
* 共有相手 username 入力チェック
* 削除確認ダイアログ
* ボタン disabled 切り替え
* 送信中 / 成功 / 失敗メッセージ表示

理由:

* これらは API 通信そのものではなく、画面側の操作・表示責務だからです。

## 今回切り出さないもの

以下は今回切り出さないでください。

* `loadGridCells()` 全体
* `submitRating()` 全体
* `submitBulkRating()` 全体
* `loadShares()` 全体
* `addShare()` 全体
* `deleteShare()` 全体
* `deleteCurrentArea()` 全体

ただし、これらの内部の `fetch()` 部分は `GridDetailApi` に置き換えてください。

関数名自体は `grid-detail.js` に残して構いません。

## 既存機能を壊さないこと

今回の追加後も、以下がこれまで通り動くようにしてください。

* GridCell 一覧取得
* 地図表示
* GridCell 色分け
* スコアラベル
* 通常クリックによる単体選択
* Ctrl / Command クリック複数選択
* Shift + ドラッグ範囲選択
* Escape キャンセル
* 個別解除
* 全選択解除
* 単体採点
* 一括採点
* 自動採点理由表示
* メモグリッド削除
* 共有相手管理
* 作成画面
* 一覧画面

## 今回は実装しないこと

以下は今回やらないでください。

* ES modules 化
* `import` / `export` 導入
* `type="module"` 導入
* API仕様変更
* URL変更
* payload 形式変更
* エラー文言変更
* UI変更
* CSS変更
* Leaflet処理の分離
* 選択状態管理の分離
* DOM描画処理の分離
* 採点フォーム描画の分離
* 共有管理 UI の分離
* 削除 UI の分離
* 新機能追加
* model 変更
* migration 作成
* demo.js の変更
* demo.css の変更
* demo ページ削除
* Basic 認証欄の追加
* Token 認証の画面対応
* README / API_SPEC 更新
* `memo.md` の更新

## 注意

* 確認コマンドやテストコマンドは実行しないでください。
* コマンド実行結果の報告は不要です。
* 既存機能の挙動を変えないでください。
* demo ページを壊さないでください。
* demo.js を変更しないでください。
* demo.css を変更しないでください。
* 既に未コミット差分がある場合は、今回の作業対象以外を変更しないでください。
* `TASK.md` は、ユーザーが貼り付けた内容以外に勝手に更新しないでください。
* `memo.md` は明示指示がないため更新しないでください。

## 作業後に報告してほしいこと

作業後、以下を説明してください。

* 追加・変更したファイル
* 新規追加した `grid-detail-api.js`
* `grid_detail.html` での script 読み込み順
* `window.GridDetailApi` で公開している関数
* `grid-detail.js` 側で置き換えた API 呼び出し
* 成功後の DOM 更新や state 更新は `grid-detail.js` に残していること
* CSRF 対応の方法
* Basic 認証を使っていないこと
* ES modules 化していないこと
* 挙動変更をしていないこと
* 今回は未実装のこと
* 次にやるとよい整理タスク

## 確認観点

コマンドは実行しなくてよいですが、実装後にユーザーが確認しやすいように、以下の確認観点を説明してください。

* ログイン後に `/maps/` を開く
* 任意のメモグリッド詳細へ移動する
* GridCell 一覧がこれまで通り表示される
* 地図表示、色分け、スコアラベルがこれまで通り動く
* 通常クリック、Ctrl / Command クリック、Shift + ドラッグ範囲選択、Escape キャンセルがこれまで通り動く
* 単体採点がこれまで通り送信できる
* 一括採点がこれまで通り送信できる
* 採点後に GridCell 一覧・地図色・スコアラベルが更新される
* メモグリッド削除がこれまで通り動く
* 共有相手一覧取得、追加、解除がこれまで通り動く
* API エラー表示がこれまで通り表示される
* `/api/maps/demo/` が壊れていない
