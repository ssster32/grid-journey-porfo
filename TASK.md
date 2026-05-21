# TASK.md 用プロンプト

## 現在のタスク

Score Map をより地図らしく改善する

## 目的

demo ページの Score Map 表示を、現在の「マスが分離した確認用グリッド」から、将来の地図表示に近い見た目へ改善する。

今回は外部地図の取得・表示は行わない。  
将来的に地図画像や地図タイルを背景として表示することを想定し、その上に Score Map を重ねやすい構造にする。

## 作業範囲

- demo ページの Score Map 表示改善
- Score Map 用 HTML/CSS/JavaScript の必要最小限の更新
- demo ページ表示テストの必要最小限の更新
- README.md の demo ページ説明の必要最小限の更新
- API_SPEC.md は必要があれば表示方針メモのみ更新

## 変更してよいファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.css`
- `maps/static/maps/demo.js`
- `maps/tests.py`
- `README.md`
- `API_SPEC.md`
- `TASK.md`

## 変更しないファイル

- `maps/models.py`
- `maps/migrations/`
- `maps/views.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/urls.py`
- `config/settings.py`
- `config/urls.py`
- `requirements.txt`

## 実装方針

### Score Map の見た目

- GridCell を線や余白で分離したカード状に表示しない。
- Score Map 全体を、一つの大きな四角い地図表示領域として見せる。
- 各 GridCell は、その大きな四角の中を区切る領域として表示する。
- マス同士の `gap` はなくす。
- 必要であれば細い境界線は使ってよいが、見た目の主役は「分離したカード」ではなく「一枚の地図状の面」にする。

### 表示内容

- 各 GridCell では `calculated_score` をメインで大きく表示する。
- `GridCell ID`、`row_index`、`col_index` は将来的に非表示にする想定。
- ただし現在は確認用として、小さく表示しておく。
- 表示の優先度は次の順にする。

```text
1. calculated_score
2. GridCell ID
3. row_index / col_index
```

### 将来の地図背景を想定した構造

- 将来的に地図を表示するときは、Score Map の背景として地図を表示する想定にする。
- 今回は地図の取得・表示は行わない。
- CSS または HTML 構造として、将来 `map background` を入れやすい形にする。
- 例:
  - Score Map 外側に背景用レイヤーを置ける構造にする
  - Score Map のセルを半透明にしやすい CSS にする
  - 背景なしでも現在の Score Map が見やすい状態にする

### 今回やらないこと

- 外部地図 API の利用
- 地図画像の取得
- Leaflet / Google Maps / Mapbox などの導入
- 緯度経度に基づく正確な地図投影
- `models.py` の変更
- migration の作成
- API レスポンス形式の変更

## JavaScript 方針

- 既存の `renderScoreMap(grids)` を中心に更新する。
- `row_index` / `col_index` による CSS Grid 表示は維持してよい。
- `gap` 前提の見た目から、連続した面として見える表示に変える。
- `calculated_score` を大きく表示するための HTML 構造にする。
- ID や row/col は補助情報として小さく表示する。

## CSS 方針

- `.score-map` は一つの大きな表示領域として見えるようにする。
- `.score-cell` の余白や角丸を調整し、セル同士が分離したカードに見えないようにする。
- `gap` は `0` にする。
- Score Map 全体には固定または安定した最小高さを持たせる。
- 将来の地図背景を想定し、背景レイヤーや半透明セルにしやすい構造にする。
- `calculated_score` はセル内で最も目立つサイズにする。
- `GridCell ID` と `row/col` は小さく控えめに表示する。
- モバイル幅でも文字がはみ出さないようにする。

## テスト方針

以下を確認するテストを追加・更新する。

- demo ページが `200 OK` で表示される
- demo ページに `Score Map` が表示される
- demo ページに将来の地図背景を想定した要素または class が存在する
- demo ページに `GridCell を再取得` が表示される
- demo ページに `GridCell を自動生成` が表示されない

JavaScript の構文チェックも行う。

```bash
node --check maps/static/maps/demo.js
```

## README 更新方針

README.md の demo ページ説明に、以下を短く反映する。

- Score Map は一枚の地図状の四角として表示する
- 現時点では地図背景は表示しない
- 将来的には地図背景の上に Score Map を重ねる想定
- 現在は確認用に score 以外の情報も小さく表示している

## API_SPEC 更新方針

API 仕様自体は変えない。  
必要であれば、表示方針メモとして以下だけ追記する。

- `calculated_score` は Score Map 上でメイン表示に使う
- 地図背景の取得・表示は今後の別タスク
- 今回は API レスポンス形式を変更しない

## 確認方法

作業後に以下を実行する。

```bash
.venv/bin/python manage.py test maps
.venv/bin/python manage.py check
node --check maps/static/maps/demo.js
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.css maps/static/maps/demo.js maps/tests.py README.md API_SPEC.md
```

可能であれば、開発サーバーを起動して demo ページも確認する。

```bash
.venv/bin/python manage.py runserver
```

ブラウザで確認する URL:

```text
http://127.0.0.1:8000/api/maps/demo/
```

## 注意事項

- `models.py` と migration は変更しないでください。
- API レスポンス形式は変更しないでください。
- 外部地図 API や新しいライブラリは追加しないでください。
- 今回は地図の取得・表示を実装しないでください。
- GridCell の生成・採点ロジックは変更しないでください。
- 既存テストを削除して通す対応はしないでください。