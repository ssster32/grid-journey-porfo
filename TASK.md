# Codex タスク: Map Preview上でShift+ドラッグ範囲選択時に勝手にズームする現象を修正する

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

demoページの Leaflet Map Preview 上で、Shift + ドラッグによるGridCell範囲選択を行う際に、地図が勝手にズームしてしまう現象を修正してください。

調査結果では、原因は Leaflet 標準機能の `boxZoom` が有効なままになっているためである可能性が高いです。

Leaflet には、Shift + ドラッグした範囲へズームする標準機能があります。  
今回のdemoでは、Shift + ドラッグをGridCellの範囲選択として使っているため、Leaflet標準のbox zoomと独自の範囲選択処理が衝突している可能性があります。

## レート制限節約の方針

今回はレート制限節約を優先してください。

- 変更範囲を最小限にしてください。
- バックエンドAPIは変更しないでください。
- model / serializer / view / service は変更しないでください。
- README.md / API_SPEC.md / memo.md は変更しないでください。
- Leaflet範囲選択の大規模な作り直しはしないでください。
- まずは `boxZoom: false` の追加を第一候補として修正してください。
- 実装後の報告は短くしてください。

## 作業前に読むファイル

まず、次のファイルだけを確認してください。

- `AGENTS.md`
- `RULES.md`
- `maps/static/maps/demo.js`
- `maps/tests.py`

必要がある場合のみ、次を確認してください。

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`

今回は、以下のファイルは原則として読まなくてよいです。

- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `README.md`
- `API_SPEC.md`
- `memo.md`

## 今回の目的

Leaflet Map Preview 上で、Shift + ドラッグによるGridCell範囲選択を行ったとき、地図がLeaflet標準のbox zoomで勝手にズームしないようにします。

期待する挙動:

```text
Shift + Map Preview 上でドラッグ
↓
GridCell範囲選択用の矩形が表示される
↓
ドラッグ終了時に範囲内のGridCellが選択される
↓
地図のズームレベルは勝手に変わらない
```

Shiftを押していない通常ドラッグでは、これまで通り地図を移動できる状態を維持してください。

## 今回やること

- Leaflet Map Preview 初期化時に、Leaflet標準のbox zoomを無効化する
- Shift + ドラッグ範囲選択時に、地図が勝手にズームしないことを確認する
- 既存のMap Preview表示を壊さない
- 既存のLeaflet GridCellクリック選択を壊さない
- 既存のLeaflet Shift + ドラッグ範囲選択を壊さない
- 既存のScore Mapクリック選択・ドラッグ範囲選択を壊さない
- 必要に応じて、MapDemoViewTestsに静的確認を追加する

## 今回やらないこと

- Leaflet範囲選択処理の全面的な作り直し
- Leaflet上での通常ドラッグ範囲選択
- Leaflet上での直接採点UI
- Score Mapの削除
- Map Previewの設計変更
- バックエンドAPIの変更
- README.md の更新
- API_SPEC.md の更新
- memo.md の更新

## 変更してよいファイル

- `maps/static/maps/demo.js`
- `maps/tests.py`

必要がある場合のみ、最小限で以下を変更して構いません。

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`

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

## 調査結果メモ

Leaflet Map Preview は、現在 `initMapPreview()` 付近で以下のように作成されている可能性があります。

```javascript
state.leafletMap = window.L.map(elements.mapPreview, {
  scrollWheelZoom: false,
}).setView([35.69, 139.7], 11);
```

この設定では、`boxZoom` が明示的に無効化されていません。

Leafletの標準では、Shift + ドラッグで範囲ズームする `boxZoom` が有効です。  
今回のdemoでは、Shift + ドラッグを独自のGridCell範囲選択に使っているため、Leaflet標準のbox zoomが同時に動いてしまう可能性があります。

また、現在のShift + ドラッグ選択処理では、通常の地図移動用draggingは止めているはずです。

```javascript
setLeafletDraggingEnabled(false);
```

ただし、これは通常の地図移動を止めているだけで、Leaflet標準の `boxZoom` までは止めていない可能性があります。

そのため、第一候補として、Leaflet map作成時に `boxZoom: false` を追加してください。

## 実装方針

### 1. Leaflet map作成時に boxZoom を無効化する

`initMapPreview()` など、Leaflet mapを作成している箇所を確認してください。

修正例:

```javascript
state.leafletMap = window.L.map(elements.mapPreview, {
  scrollWheelZoom: false,
  boxZoom: false,
}).setView([35.69, 139.7], 11);
```

既存のオプションが他にもある場合は、それを維持したうえで `boxZoom: false` を追加してください。

### 2. 既存のShift + ドラッグ範囲選択処理は維持する

以下のような既存処理は、基本的に大きく変えないでください。

```javascript
state.leafletMap.on("mousedown", startLeafletDragSelection);
state.leafletMap.on("mousemove", updateLeafletDragSelection);
state.leafletMap.on("mouseup", finishLeafletDragSelection);
```

また、通常の地図移動を一時停止する既存処理も、必要であれば維持してください。

```javascript
setLeafletDraggingEnabled(false);
```

今回の主目的は、Leaflet標準のbox zoomとの衝突を止めることです。

### 3. 必要なら初期化後にも boxZoom を disable する

`boxZoom: false` で十分なはずですが、既存コードの構造上うまく効かない場合のみ、初期化後に明示的に無効化してください。

例:

```javascript
if (state.leafletMap.boxZoom) {
  state.leafletMap.boxZoom.disable();
}
```

ただし、まずは `L.map()` のoptionで `boxZoom: false` を指定する方法を優先してください。

### 4. fitBounds() / applyExtraMapPreviewZoom() は原則変更しない

`updateMapPreview()` 内にある `fitBounds()` や `applyExtraMapPreviewZoom()` は、メモグリッド選択時や初期表示時のズーム調整用です。

今回の現象はShift + ドラッグ中の勝手なズームなので、これらを直接原因として扱うより、まずはbox zoomを止める方針にしてください。

明らかに必要がある場合を除き、`fitBounds()` や `applyExtraMapPreviewZoom()` の挙動は変更しないでください。

## テスト方針

Djangoのview testでは実際のLeaflet操作までは確認できません。

そのため、`MapDemoViewTests` では必要に応じて、以下のような静的確認を追加してください。

```text
boxZoom
boxZoom: false
```

既存のテストがHTMLのみを確認しており、JS内の文字列確認がない場合は、無理にテストを追加しなくても構いません。

既に `demo.js` の内容を確認するテストがある場合は、`boxZoom` に関する確認を追加してください。

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
- Map PreviewにMapArea範囲とGridCell境界が表示される
- Map Preview上のGridCellクリック選択が引き続き動く
- Shift + ドラッグで範囲選択矩形が表示される
- Shift + ドラッグ終了時、範囲内のGridCellがまとめて選択される
- Shift + ドラッグしても、Leaflet標準の範囲ズームが発生しない
- Shift + ドラッグ後、地図のズームレベルが勝手に変わらない
- Shiftなしの通常ドラッグでは、これまで通り地図移動できる
- Score Map側のクリック選択・ドラッグ範囲選択が壊れていない
- 採点後、Score MapとMap Previewの色分けが更新される
- ブラウザコンソールに重大なJavaScriptエラーが出ていない

## 確認方法

作業後、次を実行してください。

```bash
source .venv/bin/activate
node --check maps/static/maps/demo.js
python manage.py check
python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.js maps/tests.py
```

可能であれば、次も実行してください。

```bash
python manage.py test maps
```

## 注意事項

- 今回はLeaflet標準のbox zoom無効化に集中してください。
- 範囲選択処理を大きく作り直さないでください。
- `fitBounds()` や `applyExtraMapPreviewZoom()` は原則変更しないでください。
- Shiftなしの通常ドラッグによる地図移動は維持してください。
- Shift + ドラッグによるGridCell範囲選択は維持してください。
- Score Map側のドラッグ範囲選択は壊さないでください。
- README.md / API_SPEC.md / memo.md は変更しないでください。
- バックエンドAPIは変更しないでください。
- レート制限節約のため、必要最小限のファイルだけを変更してください。
- 実装後の報告は、変更点と実行した確認コマンドだけを短くまとめてください。