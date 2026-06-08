# TASK: /maps/<area_id>/ の Leaflet Map Preview で Shift + ドラッグ範囲選択をできるようにする

## 目的

本サイト用のメモグリッド詳細画面にある Leaflet Map Preview で、Shift キーを押しながらドラッグした範囲に含まれる GridCell をまとめて選択できるようにしてください。

現在、以下は実装済みです。

- `/login/`
- `/maps/`
- `/maps/new/`
- `/maps/<area_id>/`
- Leaflet Map Preview
- MapArea 全体枠表示
- GridCell 境界表示
- GridCell の `calculated_score` に応じた色分け
- スコア色分け凡例
- GridCell の `calculated_score` ラベル表示
- 地図上 GridCell クリック選択
- Ctrl / Command クリックによる複数マス選択
- 一覧側と地図側の複数選択同期
- 選択中マス数表示
- 複数選択中のマス簡易一覧表示
- 単体採点フォーム
- 単体採点 API 呼び出し
- 一括採点フォーム
- 一括採点 API 呼び出し
- 採点後の GridCell 再取得
- 削除機能
- 共有相手管理
- 本サイト用 CSS
- 本サイト側 JS は Session 認証前提で、Basic 認証は使っていない

今回は、Leaflet Map Preview 上で **Shift + ドラッグによる範囲選択** を追加してください。

## 重要な方針

今回やることは、**Shift + ドラッグ範囲選択で複数 GridCell を選択状態に追加すること**です。

今回やること:

- Shift キーを押しながら Map Preview 上でドラッグすると、選択用の矩形を表示する
- ドラッグ中は通常の地図ドラッグ移動を抑止する
- ドラッグ終了時に、矩形範囲と交差する GridCell を判定する
- 範囲に含まれる GridCell を `selectedGridIds` に反映する
- 一覧側・地図側・選択中マス数・一括採点フォームを更新する
- 既存の通常クリック選択、Ctrl / Command クリック複数選択を壊さない

今回やらないこと:

- Shift + ドラッグで選択解除する機能
- Alt + ドラッグなど別モード
- 範囲選択後の自動採点
- 範囲選択専用モード切替 UI
- 複雑な矩形編集
- 地図外へのドラッグ対応の作り込み
- demo.js の変更

## 範囲選択の仕様

### 基本操作

- Shift キーを押しながら地図上でマウスドラッグする
- ドラッグ開始時に選択矩形の始点を記録する
- ドラッグ中に選択矩形を Leaflet rectangle として表示する
- ドラッグ終了時に選択矩形と交差する GridCell を選択する

### 選択の反映方針

今回は、範囲選択した GridCell を **既存の選択集合に追加** する方針にしてください。

つまり:

- 既に選択されているマスは維持する
- 範囲内のマスを `selectedGridIds` に追加する
- 範囲内に既に選択済みのマスがあっても解除しない

例:

```text
既に #1, #2 を選択中
Shift + ドラッグで #3, #4, #5 を囲む
結果: #1, #2, #3, #4, #5 が選択中
```

選択解除は、既存の選択解除ボタンや Ctrl / Command クリックによる解除に任せてください。

## 対象ファイル

主に以下を確認してください。

- `maps/static/maps/js/grid-detail.js`
- `maps/templates/maps/grid_detail.html`
- `maps/static/maps/css/site.css`
- `maps/static/maps/demo.js`

必要に応じて以下も確認してよいです。

- `maps/static/maps/demo.css`
- `API_SPEC.md`

## 実装内容

### 1. 既存の Leaflet Map Preview 状態管理を確認する

`grid-detail.js` に、Leaflet map 関連の state があるはずです。

確認対象:

- Leaflet map インスタンス
- MapArea rectangle
- GridCell rectangle layer
- GridCell rectangle の Map
- スコアラベル layer
- `selectedGridIds`
- 選択状態を再描画する関数
- GridCell bounds を作る関数

今回の範囲選択は、既存の `selectedGridIds` と選択再描画処理を使って実装してください。

新しい選択 state を別に作らないでください。

### 2. 範囲選択用 state を追加する

`grid-detail.js` の state に、範囲選択用の情報を追加してください。

例:

```javascript
selectionDrag: {
  isDragging: false,
  startLatLng: null,
  rectangle: null,
}
```

既存の state 構造に合わせて構いません。

管理したい情報:

- Shift + ドラッグ中か
- ドラッグ開始地点
- 表示中の選択矩形
- 必要ならドラッグ開始時の map dragging 状態

### 3. Shift + mousedown で範囲選択を開始する

Leaflet map に `mousedown` イベントを追加してください。

挙動:

- `event.originalEvent.shiftKey` が true の場合だけ範囲選択を開始する
- 通常の mousedown では何もしない
- 範囲選択開始時に、Leaflet map の通常ドラッグ移動を一時的に無効化する
- 開始地点の latlng を保存する
- 選択矩形用の `L.rectangle()` を作成する

例:

```javascript
state.map.on("mousedown", (event) => {
  if (!event.originalEvent?.shiftKey) {
    return;
  }

  startDragSelection(event.latlng);
});
```

### 4. ドラッグ中に選択矩形を更新する

Leaflet map に `mousemove` イベントを追加し、範囲選択中だけ矩形範囲を更新してください。

挙動:

- `selectionDrag.isDragging` が true のときだけ処理する
- 開始地点と現在地点から bounds を作る
- 選択矩形 rectangle の bounds を更新する

例:

```javascript
function boundsFromLatLngs(a, b) {
  return window.L.latLngBounds(a, b);
}
```

選択矩形は、GridCell 境界や MapArea 枠と見分けがつくようにしてください。

例:

```javascript
{
  color: "#2563eb",
  weight: 2,
  dashArray: "4 4",
  fillOpacity: 0.08,
  interactive: false,
}
```

### 5. mouseup で範囲選択を確定する

Leaflet map に `mouseup` イベントを追加し、範囲選択中だけ確定処理を行ってください。

挙動:

- 現在の選択矩形 bounds を取得する
- その bounds と交差する GridCell を判定する
- 対象 GridCell ID を `selectedGridIds` に追加する
- 選択状態を再描画する
- 選択矩形を削除する
- Leaflet map の通常ドラッグ移動を再度有効化する

### 6. GridCell と選択矩形の交差判定を実装する

GridCell の bounds と選択矩形 bounds が交差するか判定してください。

Leaflet の bounds を使える場合は、以下のような方針で構いません。

```javascript
const gridBounds = window.L.latLngBounds(gridCellBounds(grid));
const selectionBounds = state.selectionDrag.rectangle.getBounds();

if (selectionBounds.intersects(gridBounds)) {
  // 選択対象
}
```

既存の `gridCellBounds(grid)` が配列を返している場合は、Leaflet bounds に変換して使ってください。

無効な GridCell bounds は無視してください。

### 7. 選択確定後に既存の選択再描画処理を呼ぶ

範囲選択後は、既存の選択状態再描画処理を使ってください。

更新対象:

- `selectedGridIds`
- `selectedGridId`
- 選択中マス数
- 選択中マス簡易一覧
- 一覧側の `is-selected`
- 地図側 rectangle の選択強調
- 単体採点フォーム
- 一括採点フォーム

新しく似たような描画処理を別に作らず、既存の `renderSelectionState()` や同等関数を呼んでください。

### 8. selectedGridId の扱い

範囲選択後に `selectedGridId` をどうするか整理してください。

おすすめ方針:

- 範囲選択で1件以上追加された場合、最後に追加された GridCell ID を `selectedGridId` にする
- ただし、複数選択中なので単体採点フォームは表示せず、一括採点フォーム側が表示される

既存の複数選択方針に合わせてください。

### 9. ドラッグ中の地図移動を抑止する

Shift + ドラッグ中は、Leaflet の通常の地図ドラッグ移動が起きないようにしてください。

候補:

```javascript
state.map.dragging.disable();
```

範囲選択終了時には必ず戻してください。

```javascript
state.map.dragging.enable();
```

エラーや中断時にも戻るように、終了処理を関数化してください。

### 10. mouseup が map 外で発生する場合への最低限対応

可能であれば、範囲選択中の `mouseup` を `document` 側でも拾えるようにしてください。

ただし、実装が大きくなりすぎる場合は、Leaflet map 上の `mouseup` だけでも構いません。

最低限、通常利用で選択矩形が残り続けないようにしてください。

### 11. 範囲選択の案内文を追加する

Map Preview セクション付近に、Shift + ドラッグ操作の簡単な案内文を追加してください。

例:

```text
Shift + ドラッグで範囲内のマスをまとめて選択できます。
```

`grid_detail.html` に追加して構いません。

### 12. CSS を最低限追加する

選択矩形自体は Leaflet rectangle の style で指定できます。

必要であれば `site.css` に案内文用の class を追加してください。

大規模な CSS 変更は不要です。

### 13. 既存機能を壊さない

今回の追加後も、以下がこれまで通り動くようにしてください。

- 通常クリックによる単体選択
- Ctrl / Command クリックによる複数選択
- 選択解除ボタン
- 一覧側と地図側の選択同期
- 単体採点
- 一括採点
- 採点後の GridCell 再取得
- GridCell 色分け
- スコアラベル
- スコア凡例
- 削除
- 共有相手管理
- 作成画面
- 一覧画面

## 今回は実装しないこと

以下は今回やらないでください。

- Shift + ドラッグで選択解除する機能
- Alt / Option など別キーでの選択解除
- 範囲選択専用モード切替 UI
- ドラッグ範囲の編集
- 範囲選択後の自動採点
- hover tooltip
- ラベルクリック
- 凡例クリックで表示切替
- 作成画面の地図プレビュー
- 地図上で中心座標を選ぶ機能
- Leaflet 関連の大規模共通化
- API仕様変更
- model 変更
- migration 作成
- 既存 API の挙動変更
- demo.js の変更
- demo.css の大規模移植
- Basic 認証欄の追加
- Token 認証の画面対応
- demo ページ削除
- `memo.md` の更新

## 注意

- 確認コマンドやテストコマンドは実行しないでください。
- コマンド実行結果の報告は不要です。
- 既存 API の URL や挙動を変えないでください。
- demo ページを壊さないでください。
- demo.js を本サイト用に直接改変しないでください。
- demo.css を本サイト用に大規模コピーしないでください。
- Leaflet 関連コードは、今回必要な最小限にしてください。
- Basic 認証処理を本サイト側 JS に追加しないでください。
- 既に未コミット差分がある場合は、今回の作業対象以外を変更しないでください。
- `TASK.md` は、ユーザーが貼り付けた内容以外に勝手に更新しないでください。
- `memo.md` は明示指示がないため更新しないでください。

## 作業後に報告してほしいこと

作業後、以下を説明してください。

- 追加・変更したファイル
- Shift + ドラッグ範囲選択の実装方法
- 範囲選択用 state の構成
- 選択矩形の描画方法
- GridCell との交差判定方法
- `selectedGridIds` への反映方法
- 地図ドラッグ移動を抑止・復帰する方法
- 既存の通常クリック選択・Ctrl / Command 選択との関係
- 今回は未実装のこと
- 既存の地図表示・選択・採点処理を壊していないこと

## 確認観点

コマンドは実行しなくてよいですが、実装後にユーザーが確認しやすいように、以下の確認観点を説明してください。

- ログイン後に `/maps/` を開く
- 任意のメモグリッド詳細へ移動する
- Shift + ドラッグで選択矩形が表示される
- ドラッグ中に地図が移動しない
- ドラッグ範囲と交差した GridCell が複数選択される
- 既存の選択済みマスは維持される
- 一覧側と地図側の両方で選択状態が反映される
- 選択中マス数が更新される
- 一括採点フォームの対象件数が更新される
- 通常クリックによる単体選択がこれまで通り動く
- Ctrl / Command クリックによる複数選択がこれまで通り動く
- 選択解除ボタンがこれまで通り動く
- 単体採点・一括採点がこれまで通り動く
- スコア色分け・スコアラベル・凡例がこれまで通り表示される
- 削除、共有相手管理、作成画面がこれまで通り動く
- `/api/maps/demo/` が壊れていない