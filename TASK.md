# Codex タスク: demoページのMapArea作成フォームを中心座標方式に変更する

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

demoページの MapArea 作成フォームを、従来の `north / south / east / west` 入力方式から、中心座標方式に変更してください。

現在、MapArea 作成 API は中心座標方式に一本化されています。  
作成リクエストでは、以下を送る必要があります。

```text
center_lat
center_lng
grid_size_meters
rows
cols
```

`north / south / east / west` は、作成後にサーバー側で計算される保存値・レスポンス値です。  
demoページの作成フォームでは、今後 `north / south / east / west` を直接入力させないでください。

## レート制限節約の方針

今回はレート制限節約を優先してください。

- 変更範囲を必要最小限にしてください。
- バックエンド API は変更しないでください。
- model / serializer / view / service は原則変更しないでください。
- README.md / API_SPEC.md / memo.md は変更しないでください。
- 必要なファイルだけ読んでください。
- 大きな設計変更はしないでください。
- 実装後の報告は短くしてください。

## 作業前に読むファイル

まず、次のファイルを確認してください。

- `AGENTS.md`
- `RULES.md`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`

必要がある場合のみ、次を確認してください。

- `maps/serializers.py`
- `maps/views.py`
- `API_SPEC.md`

今回は、以下のファイルは原則として読まなくてよいです。

- `maps/models.py`
- `maps/services.py`
- `README.md`
- `memo.md`

## 今回の目的

demoページの MapArea 作成フォームを、現在のAPI仕様に合わせます。

現在のAPIでは、MapArea作成時に次のようなリクエストを送ります。

```json
{
  "name": "Center API Area",
  "description": "center based api",
  "center_lat": 35.695,
  "center_lng": 139.795,
  "grid_size_meters": 500,
  "rows": 6,
  "cols": 8,
  "source": "manual"
}
```

従来のように、次を直接送ってはいけません。

```json
{
  "north": 35.7,
  "south": 35.6,
  "east": 139.8,
  "west": 139.7
}
```

demoページでも、この仕様に合わせてフォームと送信payloadを変更してください。

## 今回やること

- demoページの MapArea 作成フォームから `north / south / east / west` 入力欄を削除または非表示にする
- demoページの MapArea 作成フォームに `center_lat / center_lng / rows / cols` 入力欄を追加する
- `grid_size_meters` 入力欄は維持する
- `name / description / source` 入力欄は維持する
- MapArea 作成時の JavaScript payload を中心座標方式に変更する
- 作成後の MapArea 表示・Map Preview・Score Map は、APIレスポンスの `north / south / east / west` を引き続き使う
- demoページ内の説明文を中心座標方式に合わせる
- `MapDemoViewTests` を更新する
- 既存の Score Map、Leaflet Map Preview、GridCell選択、複数採点、共有相手管理を壊さない

## 今回やらないこと

- バックエンド API の変更
- `MapAreaSerializer` の変更
- `MapAreaListCreateView` の変更
- `generate_grid_cells_for_area()` の変更
- model の変更
- migration の作成
- README.md の更新
- API_SPEC.md の更新
- memo.md の更新
- Leaflet 上でのGridCellクリック選択
- Leaflet 上でのGridCellドラッグ選択
- Score Map の描画方式変更
- MapArea 作成後レスポンス形式の変更

## 変更してよいファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `maps/tests.py`

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

## フォーム変更方針

### 残す入力欄

既存のMapArea作成フォームから、次の入力欄は維持してください。

```text
name
description
grid_size_meters
source
```

ラベルは既存の雰囲気に合わせて構いません。

例:

```text
名前
説明
1マスの大きさ（m）
source
```

### 削除または非表示にする入力欄

次の入力欄は、作成フォームから削除または非表示にしてください。

```text
north
south
east
west
```

可能であれば、単に非表示にするのではなく、フォーム入力欄としては削除してください。

ただし、作成後の表示やMap Preview用の説明で `north / south / east / west` が出ることは問題ありません。  
削除したいのは、ユーザーが作成時に直接入力する欄です。

### 追加する入力欄

次の入力欄を追加してください。

```text
center_lat
center_lng
rows
cols
```

ユーザー向けラベル例:

```text
中心緯度
中心経度
縦方向のマス数
横方向のマス数
```

input の id / name は、既存命名に合わせてください。  
迷う場合は、次の id を使ってください。

```text
area-center-lat
area-center-lng
area-rows
area-cols
```

### 入力例

初期値や placeholder を入れる場合は、次のような値を使ってください。

```text
center_lat: 35.695
center_lng: 139.795
grid_size_meters: 500
rows: 6
cols: 8
```

この組み合わせでは、GridCell が `6 * 8 = 48` 個生成される想定です。

## 説明文の追加・修正

MapArea 作成フォーム付近に、中心座標方式の説明を短く入れてください。

例:

```text
MapArea の範囲は、中心座標・1マスの大きさ・縦横のマス数から自動計算されます。
north / south / east / west は作成後にサーバー側で計算されます。
```

一般ユーザー制限も、短く表示してください。

例:

```text
一般ユーザーは最大500マス、南北30,000m、東西30,000mまで作成できます。
```

長くなりすぎる場合は、補足文として小さめに表示してください。

## demo.js の変更方針

### 1. MapArea 作成payloadを中心座標方式に変更する

現在、MapArea作成時に `north / south / east / west` をpayloadに含めている場合は、それを削除してください。

変更後のpayload例:

```javascript
const payload = {
  name: ...,
  description: ...,
  center_lat: Number(...),
  center_lng: Number(...),
  grid_size_meters: Number(...),
  rows: Number(...),
  cols: Number(...),
  source: ...,
};
```

`rows / cols` は整数として扱ってください。

例:

```javascript
rows: parseInt(..., 10),
cols: parseInt(..., 10),
```

既存の実装スタイルに合わせて、`Number()` でも問題ありません。  
ただし、小数の `rows / cols` を送らないようにしてください。

### 2. north/south/east/west を送らない

作成リクエストのpayloadに、以下を含めないでください。

```text
north
south
east
west
```

API側では、これらを作成入力に含めると400になります。

### 3. 作成後の表示処理は維持する

作成成功後のAPIレスポンスには、引き続き以下が含まれます。

```text
north
south
east
west
grid_size_meters
```

そのため、以下の処理は基本的に維持してください。

- MapArea一覧表示
- MapArea詳細表示
- Leaflet Map Preview の MapArea rectangle 表示
- GridCell境界表示
- Score Map 表示
- Score Map の縦横比計算

作成後に `north / south / east / west` を表示・利用することは問題ありません。

### 4. 入力値の基本チェック

demo側では、最低限ブラウザのinput属性で補助してください。

推奨:

```html
<input type="number" step="any" id="area-center-lat">
<input type="number" step="any" id="area-center-lng">
<input type="number" min="1" step="1" id="area-rows">
<input type="number" min="1" step="1" id="area-cols">
<input type="number" min="1" step="1" id="area-grid-size-meters">
```

厳密なバリデーションはAPI側で行うため、demo.js内で過剰に複雑な検証はしなくて構いません。

## UI上の注意

中心座標方式は、ユーザーにとって意味が分かりやすいようにしてください。

特に、`rows` と `cols` が何を意味するか分かるようにします。

例:

```text
縦方向のマス数 rows
横方向のマス数 cols
```

または、

```text
rows: 南北方向に並べるマス数
cols: 東西方向に並べるマス数
```

フォームが狭くなる場合は、説明を短くしてください。

## 既存機能との関係

今回の変更後も、次の機能は壊さないでください。

- メモグリッド作成
- メモグリッド一覧取得
- メモグリッド選択
- GridCell一覧取得
- Score Map表示
- 全体表示 / 詳細表示切り替え
- Score Mapのクリック選択
- Score Mapのドラッグ範囲選択
- 選択済みマスのクリック解除
- 選択中GridCell一覧表示
- 選択をすべて解除
- 個別に入力し、まとめて採点
- 選択グリッドを全て同じ値で採点
- Leaflet Map Preview の MapArea rectangle 表示
- Leaflet Map Preview の GridCell 境界表示
- Leaflet Map Preview の GridCell スコア色分け
- 共有相手一覧取得
- 共有相手追加
- 共有解除

## テスト方針

`maps/tests.py` の `MapDemoViewTests` を更新してください。

### 追加または確認する文言・id

最低限、demoページに以下が含まれることを確認してください。

```text
中心緯度
中心経度
縦方向のマス数
横方向のマス数
center_lat
center_lng
rows
cols
```

実装上のidに合わせて、以下のようなidも確認してください。

```text
area-center-lat
area-center-lng
area-rows
area-cols
```

もしラベル表記を変えた場合は、実装に合わせてテストを調整してください。

### 削除確認

作成フォーム用の古い入力欄idが残っていないことを確認してください。

例:

```text
area-north
area-south
area-east
area-west
```

注意:

ページ全体から `north` や `south` という文字列を完全に消すテストはしないでください。  
作成後の表示や説明、Map Preview処理で `north / south / east / west` という文字列が残る可能性があるためです。

確認するなら、古い入力欄idが残っていないことに絞ってください。

### 維持するテスト

既存のdemoページ確認項目は、必要なものを維持してください。

特に、以下は引き続き確認してください。

- `Map Demo`
- `メモグリッド作成`
- `メモグリッド一覧を取得`
- `メモグリッドを作成`
- `Score Map`
- `Map Preview`
- `Leaflet`
- `共有相手管理`
- `選択中のマス`
- `採点方式`

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
- MapArea作成フォームに中心緯度・中心経度・縦方向のマス数・横方向のマス数がある
- north/south/east/west を直接入力するフォームがない
- `center_lat=35.695`
- `center_lng=139.795`
- `grid_size_meters=500`
- `rows=6`
- `cols=8`
- 上記でメモグリッドを作成できる
- 作成後、MapArea一覧に追加される
- 作成後、GridCellを取得できる
- GridCellが48件表示される
- Score Mapが表示される
- Leaflet Map PreviewにMapAreaとGridCell境界が表示される
- 既存の採点・複数選択・共有相手管理が壊れていない
- ブラウザコンソールに重大なJavaScriptエラーが出ていない

## 確認方法

作業後、次を実行してください。

```bash
source .venv/bin/activate
node --check maps/static/maps/demo.js
python manage.py check
python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py
```

可能であれば、次も実行してください。

```bash
python manage.py test maps
```

## 注意事項

- 今回はdemoページの作成フォーム変更に集中してください。
- バックエンドAPIは変更しないでください。
- README.md / API_SPEC.md / memo.md には触れないでください。
- `north / south / east / west` は作成入力としては使わないでください。
- `north / south / east / west` はレスポンス値・表示値としては引き続き使って構いません。
- Map PreviewやScore Mapの内部処理で `north / south / east / west` を使うことは問題ありません。
- `center_lat / center_lng / rows / cols` は作成リクエスト用です。
- 既存のGridCell選択・採点・共有機能を壊さないでください。
- レート制限節約のため、必要最小限のファイルだけを変更してください。
- 実装後の報告は、変更点と実行した確認コマンドだけを短くまとめてください。


## 手動での確認結果
レート制限中に手動で行った確認作業の結果です。

- Token取得: OK
- 中心座標方式POST: OK
- 作成レスポンスに north/south/east/west が含まれる: OK
- 作成レスポンスに center_lat/center_lng/rows/cols が含まれない: OK
- GridCell一覧GETで48件取得: OK
- 従来方式 north/south/east/west POST が400になる: OK
- rows*cols > 500 が400になる: OK
- 南北30000m超過が400になる: OK
- 東西30000m超過が400になる: OK