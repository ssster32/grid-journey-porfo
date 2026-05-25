# Codex タスク: Score Map に全体表示 / 詳細表示を追加し、レイヤー構造を整理する

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

確認用 `demo` ページの Score Map が、GridCell 数や地図範囲によって表示枠からはみ出して隠れないようにしてください。

今回は CSS Grid ベースの描画を維持したまま、次の対応を行います。

- Score Map に `全体表示` / `詳細表示` の切り替えを追加する
- `全体表示` では、Score Map 全体が表示枠内に収まるようにする
- `詳細表示` では、1マスの見やすさを優先し、必要に応じてスクロールできるようにする
- 将来の地図画像・地図タイル重ね合わせを考慮し、HTML / CSS 上の構造を `stage / background / grid-layer` として扱いやすく整理する

ただし、今回は **GridCell の緯度経度から `left / top / width / height` を計算して絶対配置する方式は実装しません**。  
その方式は次回以降の検討に残してください。

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
- `.score-map-section`
- `.score-map-wrap`
- `.score-map-stage`
- `.score-map-background`
- `.score-map`
- `.score-cell`
- `renderScoreMap(grids)`
- `renderGrids(grids)`
- `applyScoreMapAspectRatio()`
- `applyScoreMapBackgroundImage()`
- Score Map の複数選択処理
- 選択中 GridCell の採点パネル
- `MapDemoViewTests`

## 今回の目的

現在の Score Map は、GridCell 数が多い場合や、大きめのメモグリッドを作成した場合に、グリッドが表示範囲からはみ出して隠れることがあります。

原因として、現在の CSS では次のような状態になっています。

- Score Map の親要素に高さ制限がある
- `.score-map-stage` が `overflow: hidden` になっている
- `.score-cell` に最低サイズがある
- 横方向スクロールはあるが、縦方向には十分対応できていない
- 地図背景とグリッド部分が、将来の地図重ね合わせに向けて少し整理しづらい

今回の目的は、現在の CSS Grid ベースの実装を維持しながら、表示モードを分けることです。

## 表示モード

### 1. 全体表示

Score Map 全体を表示枠内に収めるモードです。

目的:

- 地図全体のスコア分布を見る
- 将来の地図背景と重ねたときに、全体の対応関係を確認しやすくする
- GridCell が多くても、表示枠から切れて見えなくならないようにする

特徴:

- Score Map 全体が表示枠内に収まる
- GridCell 数が多いほど、1マスは小さくなる
- 1マスのクリックしやすさより、全体把握を優先する
- 背景画像がある場合は、背景画像とグリッドが同じ表示枠内に収まる

### 2. 詳細表示

1マスの見やすさ・選択しやすさを優先するモードです。

目的:

- GridCell をクリックしやすくする
- Score や GridCell ID を読みやすくする
- 複数選択や採点操作をしやすくする

特徴:

- 1マスあたりの最低サイズを確保する
- GridCell 数が多い場合は、縦横スクロールで表示する
- はみ出した部分が `overflow: hidden` で消えないようにする
- 全体が一度に見えない場合があってもよい

## 今回やること

- Score Map に表示モード切り替え UI を追加する
- 初期表示は `全体表示` にする
- `全体表示` では Score Map 全体が枠内に収まるようにする
- `詳細表示` では 1マスの最低サイズを確保し、縦横スクロールできるようにする
- `.score-map-stage` / `.score-map-background` / グリッド表示部分を、将来のレイヤー構造として扱いやすく整理する
- 必要であれば `.score-map` を `.score-map-grid-layer` として明確化する
- 既存の Score Map 複数選択を維持する
- 既存の個別入力まとめ採点を維持する
- 既存の同じ値での一括採点を維持する
- 既存の共有相手管理を壊さない
- `MapDemoViewTests` に表示確認を追加する
- `README.md` の demo ページ確認手順を必要最小限更新する
- `memo.md` に作業内容と確認結果を追記する

## 今回やらないこと

- GridCell の緯度経度から `left / top / width / height` を計算して絶対配置する方式への変更
- Leaflet の導入
- Mapbox の導入
- Google Maps API の導入
- OpenStreetMap タイルの表示
- 外部地図ライブラリの導入
- 地図投影の厳密な計算
- GridCell 生成ロジックの変更
- `grid_size_meters` の仕様変更
- `MapArea` model の変更
- `GridCell` model の変更
- migration の作成
- 採点APIの変更
- 一括採点APIの変更
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

Score Map のヘッダー付近に、表示モードを選択できる UI を追加してください。

表示文言は、ユーザー向けに分かりやすくするため、次のようなものを使ってください。

```text
表示モード
全体表示
詳細表示
```

radio button か select のどちらでも構いません。  
既存 UI の雰囲気に合わせてください。

推奨は radio button です。

例:

```html
<div class="score-map-view-mode" aria-label="Score Map 表示モード">
  <span>表示モード</span>
  <label>
    <input type="radio" name="score-map-view-mode" value="fit" checked>
    全体表示
  </label>
  <label>
    <input type="radio" name="score-map-view-mode" value="detail">
    詳細表示
  </label>
</div>
```

id や class 名は、既存コードに合わせて調整して構いません。

## HTML 構造方針

現在の Score Map 周りの構造を、将来の地図重ね合わせを考慮して整理してください。

推奨する考え方:

```html
<div class="score-map-wrap">
  <div class="score-map-stage">
    <div class="score-map-background" aria-hidden="true"></div>
    <div id="score-map" class="score-map score-map-grid-layer" aria-live="polite">
      ...
    </div>
  </div>
</div>
```

重要なのは、次の役割が読み取れることです。

- `score-map-wrap`: スクロールや外側の表示制御
- `score-map-stage`: 地図・グリッド全体の表示枠
- `score-map-background`: 背景画像や将来の地図背景レイヤー
- `score-map-grid-layer`: GridCell を重ねるレイヤー

既存の `id="score-map"` は JavaScript から参照しているため、変更する場合は必ず JavaScript も合わせて修正してください。

可能であれば、`id="score-map"` は維持してください。

## CSS 方針

### 共通

- Score Map が表示枠から切れて見えなくなる状態を避ける
- `.score-map-stage` の `overflow: hidden` によって GridCell が消えないようにする
- 背景画像とグリッドが同じ stage 内に重なる構造を維持する
- 既存のスコア色分けを維持する
- 既存の選択中マス `.is-selected` の表示を維持する
- モバイル幅でも大きく崩れないようにする

### 全体表示

全体表示では、Score Map 全体を表示枠内に収めてください。

実装イメージ:

```css
.score-map-stage.is-fit {
  width: 100%;
  max-height: none;
  overflow: hidden;
}

.score-map-stage.is-fit .score-map-grid-layer {
  grid-template-columns: repeat(var(--score-map-cols, 1), minmax(0, 1fr));
  grid-template-rows: repeat(var(--score-map-rows, 1), minmax(0, 1fr));
}

.score-map-stage.is-fit .score-cell {
  min-height: 0;
  padding: 4px;
}
```

上記はあくまで例です。
既存CSSに合わせて安全に調整してください。

全体表示では、GridCell 数が多い場合に文字が読みにくくなっても構いません。
その場合でも、クリック・選択できる状態は維持してください。

必要であれば、全体表示では `.score-meta` の表示を小さくする、または一部を非表示にして構いません。

### 詳細表示

詳細表示では、1マスの最低サイズを確保し、必要な場合は縦横スクロールできるようにしてください。

実装イメージ:

```css
.score-map-wrap.is-detail {
  overflow: auto;
}

.score-map-stage.is-detail {
  width: max-content;
  height: max-content;
  max-height: none;
  overflow: visible;
}

.score-map-stage.is-detail .score-map-grid-layer {
  grid-template-columns: repeat(var(--score-map-cols, 1), 96px);
  grid-template-rows: repeat(var(--score-map-rows, 1), 92px);
}
```

上記はあくまで例です。
既存CSSに合わせて安全に調整してください。

詳細表示では、Score Map 全体が一度に見えなくても構いません。
ただし、縦横スクロールで全ての GridCell を確認・選択できるようにしてください。

## JavaScript 方針

表示モードを state で管理してください。

例:

```javascript
const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  selectedGridId: null,
  selectedGrid: null,
  selectedGridIds: new Set(),
  scoreMapViewMode: "fit",
  areasById: new Map(),
  gridsById: new Map(),
};
```

既存の state 構成に合わせて、より自然な名前があればそちらを優先してください。

追加する関数名は、既存の命名に合わせてください。
迷う場合は、次のような名前にしてください。

```javascript
readScoreMapViewMode()
applyScoreMapViewMode()
```

表示モード変更時には、Score Map の外側要素に class を付け替えてください。

例:

```javascript
function applyScoreMapViewMode() {
  const mode = state.scoreMapViewMode;
  const wrap = elements.scoreMap.closest(".score-map-wrap");
  const stage = elements.scoreMap.closest(".score-map-stage");

  wrap.classList.toggle("is-fit", mode === "fit");
  wrap.classList.toggle("is-detail", mode === "detail");
  stage.classList.toggle("is-fit", mode === "fit");
  stage.classList.toggle("is-detail", mode === "detail");
}
```

実際のDOM構造に合わせて調整してください。

## 既存機能との関係

今回の変更後も、次の機能は壊さないでください。

- メモグリッド作成
- メモグリッド一覧取得
- メモグリッド選択
- GridCell 一覧取得
- Score Map 表示
- Score Map 背景画像 URL 指定
- Score Map 複数選択
- 選択済みマスのクリック解除
- 選択中 GridCell 一覧表示
- 個別に入力し、まとめて採点
- 選択グリッドを全て同じ値で採点
- 選択をすべて解除
- 共有相手一覧取得
- 共有相手追加
- 共有解除

特に、表示モードを切り替えても、選択中 GridCell の状態は維持してください。

## grid_size_meters の扱い

`grid_size_meters` は、表示サイズではなく、データ上のグリッドの粗さを決める値です。

今回の変更では、`grid_size_meters` の仕様は変更しないでください。

整理すると、次の役割です。

- `grid_size_meters`: MapArea を何mごとの GridCell に分割するかを決める
- `GridCell.row_index / col_index`: CSS Grid 上での配置に使う
- `Score Map の表示サイズ`: UI上の表示モードや表示枠に応じて変わる

全体表示では、同じ `grid_size_meters` で生成された GridCell を、表示枠内に収まるように縮小表示します。

詳細表示では、同じ GridCell を、選択・確認しやすいサイズで表示し、必要に応じてスクロールします。

## 将来の地図表示に向けた注意

今回は CSS Grid ベースのまま実装してください。

将来的には、GridCell の `north / south / east / west` と MapArea の範囲から、各 GridCell の `left / top / width / height` を割合で計算し、絶対配置する方式を検討する可能性があります。

ただし、今回はその実装は行わないでください。

今回の範囲は、あくまで以下です。

```text
CSS Grid ベースのまま、
全体表示 / 詳細表示を追加し、
stage / background / grid-layer のレイヤー構造を整理する
```

## テスト方針

最低限、`MapDemoViewTests` に demo ページの表示確認を追加してください。

既存の `test_demo_page_returns_200` に追加するか、別テストに分けてください。

確認したい文言例:

- `表示モード`
- `全体表示`
- `詳細表示`

確認したいHTML要素・class例:

- `score-map-view-mode`
- `score-map-view-mode-fit`
- `score-map-view-mode-detail`
- `score-map-grid-layer`

実際の id / class 名は実装に合わせて構いません。
ただし、テストで確認しやすい名前にしてください。

JavaScript のブラウザ実行テストまでは必須にしません。
このプロジェクトでは、まず demo ページが表示され、必要な UI が含まれることを Django のテストで確認してください。

ただし、`demo.js` の構文チェックは必ず行ってください。

## README 更新方針

必要であれば、`README.md` の確認用 demo ページ手順に、Score Map の表示モードについて短く追記してください。

追記する場合は、次の内容を含めてください。

- `全体表示` は Score Map 全体を表示枠内に収める
- `詳細表示` は 1マスの見やすさを優先し、必要に応じてスクロールする
- `grid_size_meters` は表示サイズではなく、GridCell 生成時の粒度を決める値である

README は長くなりすぎないようにしてください。

## memo.md 更新方針

`memo.md` は引き継ぎ用メモファイルです。

作業後、今回の実装内容・確認結果・次にやるとよさそうなことを簡潔に追記してください。

追記例:

```markdown
## YYYY-MM-DD Score Map 表示モード対応

- Score Map に `全体表示` / `詳細表示` を追加した。
- 全体表示では、CSS Grid ベースのまま Score Map 全体が表示枠内に収まるようにした。
- 詳細表示では、1マスの最低サイズを確保し、縦横スクロールで全 GridCell を確認できるようにした。
- Score Map 周りを `stage / background / grid-layer` として扱いやすい構造に整理した。
- GridCell の緯度経度から絶対配置する方式は、次回以降の検討に残した。
- 確認: `node --check maps/static/maps/demo.js`
- 確認: `python manage.py test maps`
- 次: 必要に応じて、GridCell の north/south/east/west を使った割合配置方式を検討する。
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
- `全体表示` で Score Map 全体が表示枠内に収まる
- `詳細表示` で 1マスが見やすく表示される
- GridCell 数が多い場合でも、詳細表示で縦横スクロールできる
- GridCell が `overflow: hidden` によって途中で消えない
- 表示モードを切り替えても、選択中 GridCell が維持される
- Score Map の複数選択ができる
- 選択解除ができる
- 個別入力まとめ採点ができる
- 同じ値での一括採点ができる
- 背景画像 URL 指定が引き続き動く
- 共有相手管理が壊れていない
- モバイル幅でも大きく崩れない

## 注意事項

- 既存の demo ページの機能を壊さないでください。
- 今回は CSS Grid ベースを維持してください。
- GridCell の緯度経度から絶対配置する方式は実装しないでください。
- 外部地図ライブラリは導入しないでください。
- `grid_size_meters` の意味や仕様を変更しないでください。
- Score Map の見た目は、既存のスコア色分けを維持してください。
- 選択中マスの見た目は、既存の色分けの邪魔にならないようにしてください。
- 依存関係は追加しないでください。
- 大きな設計変更はしないでください。
- 初心者が後から読んでも分かるように、複雑な処理には短いコメントを付けてください。