# Codex タスク: Map Preview 上の GridCell に calculated_score を表示する

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

demoページの Leaflet Map Preview 上に表示している各 GridCell について、セル中央付近に `calculated_score` を表示してください。

現在、Map Preview では GridCell 境界が `calculated_score` に応じて色分けされています。  
しかし、地図上では具体的な点数が見えないため、Score Map を見なくても Map Preview 上でスコア分布を確認しやすいようにします。

## レート制限節約の方針

今回はレート制限節約を優先してください。

- 変更範囲を必要最小限にしてください。
- バックエンドAPIは変更しないでください。
- model / serializer / view / service は変更しないでください。
- README.md / API_SPEC.md / memo.md は変更しないでください。
- Map Preview 上の点数表示追加に集中してください。
- GridCell選択・採点・共有・削除機能は変更しないでください。
- Map Preview のズーム調整処理は変更しないでください。
- 実装後の報告は短くしてください。

## 作業前に読むファイル

まず、次のファイルだけを確認してください。

- `AGENTS.md`
- `RULES.md`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`

必要がある場合のみ、次を確認してください。

- `maps/static/maps/demo.html`

今回は、以下のファイルは原則として読まなくてよいです。

- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `README.md`
- `API_SPEC.md`
- `memo.md`

## 今回の目的

Map Preview 上の各 GridCell に、表示用スコアである `calculated_score` を表示します。

期待する挙動:

```text
メモグリッドを選択
↓
Map Preview に GridCell 境界が表示される
↓
各 GridCell の中央付近に calculated_score が表示される
↓
採点後に GridCell 一覧が再取得される
↓
Map Preview 上の点数表示も更新後の calculated_score に変わる
```

## 現状

現在、`demo.js` では `updateMapGridBoundaries(grids)` 内で Map Preview 上の GridCell 境界を描画しているはずです。

現在のイメージ:

```javascript
const rectangle = window.L.rectangle(bounds, {
  color: style.color,
  weight: 1,
  opacity: 0.45,
  fillColor: style.fillColor,
  fillOpacity: style.fillOpacity,
  interactive: true,
  className: "map-preview-grid-boundary",
});
```

この rectangle は `state.mapGridRectanglesById` で管理されています。

また、Score Map 側では `formatNumber(grid.calculated_score)` を使って点数を表示しているはずです。

今回の修正では、Map Preview 側にも同じ `formatNumber()` を使って `calculated_score` を表示してください。

## 今回やること

- Map Preview 上の GridCell 中央付近に `calculated_score` ラベルを表示する
- ラベルには `formatNumber(grid.calculated_score)` を使う
- GridCell bounds から中央座標を求める helper を追加する
- Leaflet の `marker` + `divIcon` などを使ってラベルを表示する
- ラベルはクリックやドラッグ選択を邪魔しないようにする
- GridCell 境界のクリア時に、点数ラベルも同時にクリアする
- 採点後に `loadGrids()` で再描画されたとき、ラベルの値も更新されるようにする
- 既存の Map Preview 上のクリック選択を壊さない
- 既存の Shift + ドラッグ範囲選択を壊さない
- 既存の Score Map 表示を壊さない
- 必要に応じて `MapDemoViewTests` を更新する

## 今回やらないこと

- バックエンドAPIの変更
- `calculated_score` の計算式変更
- GridCell のデータ構造変更
- Score Map の表示変更
- Map Preview のズーム調整変更
- Leaflet 範囲選択処理の作り直し
- ラベルの自動間引き
- ズーム率に応じたラベル表示/非表示切り替え
- 文字色の高度な自動調整
- README.md の更新
- API_SPEC.md の更新
- memo.md の更新

## 変更してよいファイル

- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`

必要がある場合のみ、最小限で以下を変更して構いません。

- `maps/static/maps/demo.html`

## 変更しないファイル

- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `maps/urls.py`
- `README.md`
- `API_SPEC.md`
- `memo.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`

## 実装方針

### 1. state にラベル管理用の Map を追加する

Map Preview 上の GridCell rectangle と同じように、点数ラベルも GridCell ID ごとに管理してください。

追加例:

```javascript
mapGridScoreLabelsById: new Map(),
```

既存の `state.mapGridRectanglesById` の近くに追加すると分かりやすいです。

### 2. GridCell の中心座標を求める helper を追加する

GridCell の `north / south / east / west` から中心座標を計算してください。

実装例:

```javascript
function gridCellCenterLatLng(grid) {
  const north = Number(grid.north);
  const south = Number(grid.south);
  const east = Number(grid.east);
  const west = Number(grid.west);

  if (
    !Number.isFinite(north) ||
    !Number.isFinite(south) ||
    !Number.isFinite(east) ||
    !Number.isFinite(west) ||
    north <= south ||
    east <= west
  ) {
    return null;
  }

  return [(north + south) / 2, (east + west) / 2];
}
```

Leaflet の marker に渡すため、`[lat, lng]` の形式にしてください。

### 3. 点数ラベル用の divIcon を作成する helper を追加する

`calculated_score` を表示するための Leaflet `divIcon` を作成してください。

実装例:

```javascript
function mapGridScoreLabelIcon(score) {
  const formattedScore = formatNumber(score) || "0";

  return window.L.divIcon({
    className: "map-preview-score-label",
    html: `<span>${escapeHtml(formattedScore)}</span>`,
    iconSize: [32, 20],
    iconAnchor: [16, 10],
  });
}
```

既存の `formatNumber()` と `escapeHtml()` を使ってください。

### 4. updateMapGridBoundaries() で rectangle と一緒にラベルを追加する

`updateMapGridBoundaries(grids)` の `grids.forEach()` 内で、rectangle を作成した後に、同じ GridCell の中央へラベルを追加してください。

実装イメージ:

```javascript
const centerLatLng = gridCellCenterLatLng(grid);
if (centerLatLng) {
  const label = window.L.marker(centerLatLng, {
    icon: mapGridScoreLabelIcon(grid.calculated_score),
    interactive: false,
    keyboard: false,
  });

  label.addTo(boundaryLayer);
  state.mapGridScoreLabelsById.set(gridId, label);
}
```

ラベルはクリックやドラッグ範囲選択を邪魔しないように、`interactive: false` にしてください。

### 5. clearMapGridBoundaries() でラベル管理もクリアする

`clearMapGridBoundaries()` では現在、GridCell rectangle 用の layer をクリアしているはずです。

`boundaryLayer.clearLayers()` で同じ layer 上のラベルも消える場合でも、管理用Mapは必ずクリアしてください。

修正イメージ:

```javascript
function clearMapGridBoundaries() {
  cancelLeafletDragSelection();
  if (state.gridBoundaryLayer) {
    state.gridBoundaryLayer.clearLayers();
  }
  state.mapGridRectanglesById.clear();
  state.mapGridScoreLabelsById.clear();
}
```

### 6. ラベルをクリック選択の対象にしない

ラベルは `interactive: false` にしてください。

また、CSS側でも念のため `pointer-events: none;` を指定してください。

```css
.map-preview-score-label {
  pointer-events: none;
}
```

これにより、Map Preview 上の GridCell rectangle クリック選択や Shift + ドラッグ範囲選択を邪魔しにくくなります。

### 7. ラベルの見た目を最小限整える

CSSでラベルの見た目を調整してください。

例:

```css
.map-preview-score-label {
  pointer-events: none;
  text-align: center;
}

.map-preview-score-label span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  min-height: 18px;
  padding: 1px 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(23, 111, 92, 0.35);
  color: #15362f;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}
```

既存のデザイン変数や色がある場合は、それに合わせてください。

### 8. 選択中ハイライトとの重なりに注意する

現在、選択中の GridCell rectangle は `bringToFront()` されているはずです。

点数ラベルを rectangle と同じ layer に追加すると、選択時の `bringToFront()` によってラベルより rectangle が前面に来る可能性があります。

最低限、ラベルが見えれば問題ありません。  
もし rectangle がラベルを隠す場合は、以下のどちらかで対応してください。

```text
- ラベルを rectangle の後に addTo する
- highlightSelectedMapGridBoundaries() の最後でラベルも bringToFront() する
```

必要であれば、以下のような helper を追加しても構いません。

```javascript
function bringMapGridScoreLabelsToFront() {
  state.mapGridScoreLabelsById.forEach((label) => {
    label.bringToFront();
  });
}
```

そして `highlightSelectedMapGridBoundaries()` の最後で呼び出してください。

ただし、過剰に複雑にしないでください。

### 9. 採点後の更新

採点後は既存処理で `loadGrids()` が呼ばれているはずです。

`loadGrids()` → `renderGrids()` → `updateMapGridBoundaries(grids)` の流れで再描画されるなら、点数ラベルも自然に更新されます。

今回、採点後の更新処理自体は変更しないでください。

## テスト方針

Django の view test では Leaflet の実際の描画までは確認できません。

そのため、`MapDemoViewTests` では静的確認で構いません。

既に `demo.js` と `demo.css` の中身を確認するテストがある場合は、以下を確認してください。

```text
mapGridScoreLabelsById
gridCellCenterLatLng
mapGridScoreLabelIcon
map-preview-score-label
```

CSS側については以下を確認してください。

```text
.map-preview-score-label
pointer-events: none
```

既存の `MapDemoViewTests` に追加する場合は、確認項目を増やしすぎないようにしてください。

## 手動確認方針

実装後、開発サーバーを起動してdemoページを確認してください。

```bash
source .venv/bin/activate
python manage.py runserver
```

ブラウザで開くURL:

```text
http://127.0.0.1:8000/api/maps/demo/
```

手動確認では、次を確認してください。

- demoページが表示される
- メモグリッドを作成または選択できる
- Map Preview に GridCell 境界が表示される
- 各 GridCell 中央付近に calculated_score が表示される
- 点数表示が Score Map 側の表示値と一致する
- 採点後、Map Preview 上の点数表示も更新される
- 点数ラベルが GridCell クリック選択を邪魔しない
- 点数ラベルが Shift + ドラッグ範囲選択を邪魔しない
- 選択中GridCellのハイライトが引き続き見える
- Map Preview のズーム初期表示が壊れていない
- Score Map 側の表示・選択・採点が壊れていない
- ブラウザコンソールに重大な JavaScript エラーが出ていない

## 確認方法

作業後、次を実行してください。

```bash
source .venv/bin/activate
node --check maps/static/maps/demo.js
python manage.py check
python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py
```

可能であれば、次も実行してください。

```bash
python manage.py test maps
```

## 注意事項

- 今回は Map Preview 上の点数表示追加に集中してください。
- バックエンドAPIは変更しないでください。
- `calculated_score` の計算式は変更しないでください。
- Score Map の表示は変更しないでください。
- Map Preview のズーム調整処理は変更しないでください。
- 点数ラベルはクリックやドラッグ選択を邪魔しないようにしてください。
- ラベルが多くて見づらい場合でも、今回は自動間引きやズーム率による表示切替までは行わないでください。
- 小さいGridCellでラベルが重なる場合の高度な調整は次回以降に残してください。
- README.md / API_SPEC.md / memo.md には触れないでください。
- レート制限節約のため、必要最小限のファイルだけを変更してください。
- 実装後の報告は、変更点と実行した確認コマンドだけを短くまとめてください。