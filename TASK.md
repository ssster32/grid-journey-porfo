# Codex タスク: Score Map 上でドラッグ範囲選択できるようにする

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

確認用 `demo` ページの Score Map を改善し、Score Map 上でドラッグした範囲内の GridCell をまとめて選択できるようにしてください。

現在は Score Map のマスをクリックすることで複数選択できます。  
今回の目的は、GridCell 数が多い場合でも、1マスずつクリックせずに範囲選択できるようにすることです。

## 作業前に必ず読むファイル

作業前に、次のファイルを確認してください。

- `AGENTS.md`
- `RULES.md`
- `README.md`
- `TASK.md`
- `API_SPEC.md`
- `memo.md`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`

特に、以下を確認してください。

- Score Map 周りの HTML 構造
- `.score-map-wrap`
- `.score-map-stage`
- `.score-map-background`
- `.score-map-grid-layer`
- `.score-cell`
- `state.selectedGridIds`
- `selectedGrids()`
- `toggleGridSelection(gridId)`
- `clearSelectedGrids()`
- `removeSelectedGrid(gridId)`
- `renderSelectedGrids()`
- `highlightSelectedScoreCells()`
- `renderScoreMap(grids)`
- 全体表示 / 詳細表示の切り替え処理
- 既存の複数選択採点処理
- `MapDemoViewTests`

## 今回の目的

Score Map 上でドラッグした矩形範囲に含まれる GridCell をまとめて選択できるようにします。

具体的には、次の操作をできるようにしてください。

1. Score Map 上でドラッグ開始する
2. ドラッグ中に選択範囲が見える
3. ドラッグ終了時に、範囲内の GridCell がまとめて選択される
4. 既に選択済みの GridCell は選択状態を維持する
5. 選択中 GridCell 一覧・選択数・採点パネルが更新される
6. 既存のクリック選択・クリック解除も引き続き使える

## 今回やること

- Score Map 上でドラッグ範囲選択できるようにする
- ドラッグ中の選択範囲を視覚的に表示する
- ドラッグ終了時に、範囲内の `.score-cell` を判定して `state.selectedGridIds` に追加する
- 全体表示 / 詳細表示のどちらでも範囲選択できるようにする
- 詳細表示でスクロールしている場合でも、できるだけ自然に範囲判定できるようにする
- 既存のクリック選択・クリック解除を壊さない
- 既存の複数選択採点を壊さない
- 既存の全体表示 / 詳細表示切り替えを壊さない
- `MapDemoViewTests` に表示確認を追加する
- `README.md` の demo ページ確認手順を必要最小限更新する
- `memo.md` に作業内容と確認結果を追記する

## 今回やらないこと

- Shift クリック選択
- Ctrl / Cmd クリック専用操作
- ドラッグ中のリアルタイム選択確定
- 選択済み GridCell のドラッグ解除
- 範囲外を自動スクロールしながら選択する機能
- タッチ端末向けの本格的な範囲選択
- 地図タイル表示
- Leaflet / Mapbox などの外部地図ライブラリ導入
- GridCell の緯度経度から絶対配置する方式への変更
- GridCell 生成ロジックの変更
- 採点 API の変更
- 一括採点 API の変更
- 依存関係の追加

## 変更してよいファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`
- `README.md`
- `memo.md`

必要があれば、以下も最小限変更して構いません。

- `API_SPEC.md`

## 変更しないファイル

原則として、今回のタスクではバックエンド実装側は変更しないでください。

- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/urls.py`
- `maps/services.py`
- `maps/migrations/`
- `maps/admin.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`

## UI 要件

Score Map 上でドラッグ中に、選択範囲が分かる矩形を表示してください。

表示例:

```html
<div class="score-selection-rect" aria-hidden="true"></div>
```

この要素は、Score Map の stage または grid layer 上に重ねて表示してください。

推奨構造:

```html
<div class="score-map-wrap">
  <div class="score-map-stage">
    <div class="score-map-background" aria-hidden="true"></div>
    <div id="score-map" class="score-map score-map-grid-layer" aria-live="polite">
      ...
    </div>
    <div id="score-selection-rect" class="score-selection-rect" aria-hidden="true" hidden></div>
  </div>
</div>
```

既存構造に合わせて調整して構いません。

## CSS 要件

ドラッグ中の選択範囲が分かるように、半透明の矩形を表示してください。

例:

```css
.score-selection-rect {
  position: absolute;
  z-index: 3;
  border: 2px solid rgba(23, 111, 92, 0.9);
  background: rgba(23, 111, 92, 0.16);
  pointer-events: none;
}
```

注意:

- `.score-cell` のクリック操作を邪魔しないように `pointer-events: none` を付けてください。
- 背景画像や Score Map より前面に出るようにしてください。
- 選択中マス `.is-selected` の表示を壊さないでください。
- 全体表示 / 詳細表示のどちらでも見えるようにしてください。

## JavaScript 方針

### state 追加

ドラッグ選択用の state を追加してください。

例:

```javascript
const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  selectedGridId: null,
  selectedGrid: null,
  selectedGridIds: new Set(),
  scoreMapViewMode: "fit",
  isDraggingSelection: false,
  dragStartPoint: null,
  dragCurrentPoint: null,
  suppressNextCellClick: false,
  areasById: new Map(),
  gridsById: new Map(),
};
```

既存コードに合わせて、より自然な名前があればそちらを優先してください。

### 追加する関数

関数名は既存の命名に合わせてください。

迷う場合は、次のような名前にしてください。

```javascript
stagePointFromEvent(event)
startDragSelection(event)
updateDragSelection(event)
finishDragSelection(event)
cancelDragSelection()
renderSelectionRect()
hideSelectionRect()
selectionRectFromPoints(startPoint, endPoint)
selectGridsInRect(rect)
cellRectIntersectsSelection(cellRect, selectionRect)
```

## 実装方針

### 1. Pointer Events を使う

ドラッグ選択には、できれば `pointerdown` / `pointermove` / `pointerup` / `pointercancel` を使ってください。

理由:

- mouse 操作に対応しやすい
- 将来 touch / pen にも拡張しやすい
- `setPointerCapture()` を使いやすい

ただし、既存環境との相性が悪い場合は mouse event でも構いません。

### 2. ドラッグ開始条件

Score Map の stage または grid layer 上でドラッグ開始できるようにしてください。

ただし、次の場合はドラッグ選択を開始しないでください。

- Score Map に GridCell が表示されていない
- メモグリッド未選択
- 右クリック
- 入力欄やボタンなどのフォーム要素上
- 既存の採点パネル上

### 3. クリック選択との競合を避ける

既存では `.score-cell` をクリックすると選択状態を切り替えます。

ドラッグ選択を追加すると、`pointerup` 後に `click` が発火して、意図せず1マスだけ選択解除される可能性があります。

そのため、ドラッグ距離が一定以上の場合は、次の click を抑制してください。

例:

```javascript
const DRAG_SELECT_THRESHOLD = 5;
```

- 移動距離が 5px 未満 → 通常クリックとして扱う
- 移動距離が 5px 以上 → ドラッグ選択として扱い、次の click を抑制する

既存の `elements.scoreMap.addEventListener("click", ...)` 側で、`state.suppressNextCellClick` を見て処理を止める形にしてください。

### 4. 座標計算

選択矩形は、`.score-map-stage` 基準の座標で計算してください。

`getBoundingClientRect()` を使い、スクロール状態も考慮してください。

基本方針:

```javascript
function stagePointFromEvent(event) {
  const stageRect = elements.scoreMapStage.getBoundingClientRect();
  return {
    x: event.clientX - stageRect.left,
    y: event.clientY - stageRect.top,
  };
}
```

詳細表示で `.score-map-wrap` がスクロールしている場合、必要に応じて `scrollLeft` / `scrollTop` を足してください。

例:

```javascript
x: event.clientX - stageRect.left + elements.scoreMapWrap.scrollLeft
y: event.clientY - stageRect.top + elements.scoreMapWrap.scrollTop
```

実際の DOM 構造と CSS に合わせて、安全に調整してください。

### 5. 選択矩形の表示

ドラッグ開始時に `.score-selection-rect` を表示し、ドラッグ中に位置・サイズを更新してください。

矩形は、開始点と現在点から次を計算します。

```javascript
left = Math.min(start.x, current.x)
top = Math.min(start.y, current.y)
width = Math.abs(current.x - start.x)
height = Math.abs(current.y - start.y)
```

`style.left` / `style.top` / `style.width` / `style.height` に反映してください。

### 6. 範囲内 GridCell の判定

ドラッグ終了時に、すべての `.score-cell[data-grid-id]` を調べ、選択矩形と重なっているものを選択してください。

判定は、完全に内側でなくても構いません。  
少しでも矩形と交差していれば選択する方式でよいです。

例:

```javascript
function cellRectIntersectsSelection(cellRect, selectionRect) {
  return !(
    cellRect.right < selectionRect.left ||
    cellRect.left > selectionRect.right ||
    cellRect.bottom < selectionRect.top ||
    cellRect.top > selectionRect.bottom
  );
}
```

座標系は必ず揃えてください。

### 7. 選択方式

ドラッグ範囲選択では、範囲内の GridCell を `state.selectedGridIds` に追加してください。

既存選択は維持してください。

つまり、ドラッグ選択は **追加選択** として扱います。

- 既に選択済みの GridCell → 選択されたまま
- 未選択の GridCell → 選択に追加
- 範囲外の GridCell → 状態を変えない

選択解除は、既存のクリック解除・選択解除ボタン・選択をすべて解除ボタンを使います。

### 8. 選択後の更新

ドラッグ終了後は、次を呼んで UI を更新してください。

```javascript
renderSelectedGrids();
highlightSelectedScoreCells();
```

必要であれば、直近選択 GridCell として `state.selectedGridId` / `state.selectedGrid` も更新してください。

おすすめは、ドラッグで追加された最後の GridCell を直近選択として扱うことです。

### 9. キャンセル処理

次の場合は、選択矩形を消してください。

- `pointercancel`
- `Escape` キー
- メモグリッド切り替え
- GridCell 再読み込み
- ドラッグ中に何らかのエラーが起きた場合

## 既存機能との関係

今回の変更後も、次の機能は壊さないでください。

- メモグリッド作成
- メモグリッド一覧取得
- メモグリッド選択
- GridCell 一覧取得
- Score Map 表示
- 全体表示 / 詳細表示切り替え
- Map image URL による背景画像表示
- Score Map のクリック選択
- 選択済みマスのクリック解除
- 選択中 GridCell 一覧表示
- 選択をすべて解除
- 個別に入力し、まとめて採点
- 選択グリッドを全て同じ値で採点
- 共有相手一覧取得
- 共有相手追加
- 共有解除

## 全体表示 / 詳細表示での扱い

### 全体表示

- GridCell が小さい場合でも、ドラッグ範囲内に含まれるマスを選択できるようにしてください。
- 1マスが小さくてクリックしづらい場合でも、範囲選択でまとめて選べることを重視してください。

### 詳細表示

- `.score-map-wrap` がスクロールしている状態でも、表示されている範囲でドラッグ選択できるようにしてください。
- 今回は、ドラッグ中に端へ近づいたら自動スクロールする機能は不要です。
- スクロールしながら範囲選択したい場合は、次回以降の検討に残してください。

## テスト方針

最低限、`MapDemoViewTests` に demo ページの表示確認を追加してください。

既存の `test_demo_page_returns_200` に追加するか、別テストに分けてください。

確認したい文言例:

- `ドラッグ`
- `範囲選択`

確認したいHTML要素・class例:

- `score-selection-rect`
- `score-map-grid-layer`

文言を UI に出さない場合は、HTML 要素・class の確認だけでも構いません。

JavaScript のブラウザ実行テストまでは必須にしません。
このプロジェクトでは、まず demo ページが表示され、必要な UI が含まれることを Django のテストで確認してください。

ただし、`demo.js` の構文チェックは必ず行ってください。

## README 更新方針

必要であれば、`README.md` の確認用 demo ページ手順に、Score Map のドラッグ範囲選択について短く追記してください。

追記する場合は、次の内容を含めてください。

- Score Map 上でドラッグすると、範囲内の GridCell をまとめて選択できる
- クリック選択・クリック解除も引き続き使える
- 選択後は、既存の個別入力まとめ採点・同じ値での一括採点を使える

README は長くなりすぎないようにしてください。

## memo.md 更新方針

`memo.md` は引き継ぎ用メモファイルです。

作業後、今回の実装内容・確認結果・次にやるとよさそうなことを簡潔に追記してください。

追記例:

```markdown
## YYYY-MM-DD Score Map ドラッグ範囲選択対応

- Score Map 上でドラッグした範囲内の GridCell をまとめて選択できるようにした。
- ドラッグ中は選択範囲を矩形で表示する。
- ドラッグ範囲選択は追加選択として扱い、既存の選択済み GridCell は維持する。
- クリック選択・クリック解除、選択中 GridCell 一覧、複数選択採点は引き続き動作する。
- 確認: `node --check maps/static/maps/demo.js`
- 確認: `python manage.py test maps`
- 次: 必要に応じて Shift クリック選択、範囲外への自動スクロール、矩形選択解除を検討する。
```

実際に実行したコマンドだけを書いてください。
実行できなかったコマンドは、実行できなかった理由を書いてください。

## 確認方法

作業後、次を実行してください。

```bash
source .venv/bin/activate
node --check maps/static/maps/demo.js
python manage.py check
python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
```

可能であれば、次も実行してください。

```bash
python manage.py test maps
```

手動確認する場合は、開発サーバーを起動してください。

```bash
source .venv/bin/activate
python manage.py runserver
```

ブラウザで次を開いて確認してください。

```text
http://127.0.0.1:8000/api/maps/demo/
```

手動確認では、次を確認してください。

- メモグリッド一覧を取得できる
- メモグリッドを選択できる
- GridCell 一覧が表示される
- Score Map が表示される
- Score Map のマスをクリック選択できる
- 選択済みマスをクリック解除できる
- Score Map 上でドラッグすると選択矩形が表示される
- ドラッグ終了時に、範囲内の GridCell がまとめて選択される
- 既に選択済みの GridCell は、ドラッグ後も選択状態を維持する
- 選択数が更新される
- 選択中 GridCell 一覧が更新される
- `選択をすべて解除` が動く
- 全体表示でもドラッグ選択できる
- 詳細表示でもドラッグ選択できる
- 詳細表示でスクロールしても、表示中の GridCell をドラッグ選択できる
- 個別入力まとめ採点ができる
- 同じ値での一括採点ができる
- 表示モードを切り替えても選択状態が維持される
- 背景画像 URL 指定が引き続き動く
- 共有相手管理が壊れていない

## 注意事項

- 既存の demo ページの機能を壊さないでください。
- 今回は CSS Grid ベースを維持してください。
- GridCell の緯度経度から絶対配置する方式は実装しないでください。
- 外部地図ライブラリは導入しないでください。
- ドラッグ選択は、既存選択への追加選択として扱ってください。
- ドラッグ範囲外の GridCell は選択状態を変えないでください。
- クリック選択・クリック解除の挙動を壊さないでください。
- Score Map の見た目は、既存のスコア色分けを維持してください。
- 選択中マスの見た目は、既存の色分けの邪魔にならないようにしてください。
- 依存関係は追加しないでください。
- 大きな設計変更はしないでください。
- 初心者が後から読んでも分かるように、複雑な処理には短いコメントを付けてください。