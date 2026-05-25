# Codex タスク: Score Map のマスをクリックして採点できるようにする

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

確認用 `demo` ページの Score Map を改善し、Score Map 上のマスをクリックして GridCell を選択し、選択中の GridCell を demo ページ内の採点パネルから採点できるようにしてください。

この demo ページは開発確認用です。
本番向けの完成UIではなく、既存APIの動作確認と今後の地図UI検証をしやすくするためのページとして実装してください。

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
- `maps/views.py`
- `maps/urls.py`

特に、以下を確認してください。

- demo ページの既存HTML構成
- `demo.js` の `state`
- `renderScoreMap(grids)`
- `renderGrids(grids)`
- `loadGrids()`
- `rateGrid(gridId)`
- 既存のテーブル側採点処理
- Score Map の既存CSS
- `MapDemoViewTests` の書き方

## 今回の目的

現在の demo ページでは、Score Map に GridCell のスコアを表示できます。

今回の目的は、Score Map を単なる表示用ではなく、次の操作ができる確認UIにすることです。

1. Score Map 上のマスをクリックする
2. クリックした GridCell が選択状態になる
3. demo ページ内の採点パネルに選択中 GridCell の情報が表示される
4. 採点パネルから score を入力して採点できる
5. 採点成功後、GridCell 一覧と Score Map が再読み込みされる
6. 可能であれば、採点後も同じ GridCell の選択状態を維持する

## 今回やること

- Score Map の各マスをクリック可能にする
- 選択中 GridCell を管理する state を追加する
- 選択中 GridCell の情報を表示する採点パネルを demo ページに追加する
- 採点パネルから既存の採点APIを呼べるようにする
- 採点後に GridCell 一覧と Score Map を更新する
- 選択中の Score Map マスに選択中スタイルを付ける
- メモグリッド切り替え時に選択中 GridCell をリセットする
- 必要に応じて `MapDemoViewTests` に表示確認を追加する
- 必要に応じて `README.md` の demo ページ確認手順を更新する

## 対象API

既存の採点APIを使用してください。

```text
POST /api/maps/grids/{grid_id}/ratings/
```

リクエスト例:

```json
{
  "score": 8,
  "comment": "demo page rating"
}
```

既存のテーブル側採点処理で使っているAPIと同じものを使ってください。

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

採点APIは既に実装済みの前提です。
API側に明らかな不具合を見つけた場合は、勝手に大きく修正せず、原因と修正方針を説明してから最小限の修正にしてください。

## UI 方針

demo ページ内に、選択中 GridCell を採点するためのパネルを追加してください。

表示名は、ユーザー向けに分かりやすくするため、次のような文言を使ってください。

```text
選択中のマス
GridCell を選択してください。
選択中 GridCell
行
列
現在のスコア
採点する
score
```

内部名として `GridCell` を使うのは構いません。
画面表示でも、開発確認用ページなので `GridCell` という語は使って構いません。

## UI の具体要件

### 1. Score Map のマスをクリック可能にする

`renderScoreMap(grids)` で生成している `.score-cell` に、クリック判定用の data 属性を追加してください。

例:

```html
<div
  class="score-cell ..."
  data-grid-id="..."
>
```

必要に応じて、行・列・スコアなども data 属性に入れて構いません。

```html
data-grid-row="..."
data-grid-col="..."
data-grid-score="..."
```

ただし、実際の選択中 GridCell 情報は、できるだけ `state` か読み込み済みの `grids` から取得してください。

### 2. 選択中 GridCell 用の state を追加する

既存の `state` に、選択中 GridCell を表す値を追加してください。

例:

```javascript
const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  selectedGridId: null,
  selectedGrid: null,
  areasById: new Map(),
  gridsById: new Map(),
};
```

既存の構成に合わせて、より自然な名前があればそちらを優先してください。

### 3. GridCell 読み込み時に参照用 Map を作る

`renderGrids(grids)` または `loadGrids()` の中で、GridCell ID から GridCell を取得できるようにしてください。

例:

```javascript
state.gridsById = new Map(grids.map((grid) => [Number(grid.id), grid]));
```

これにより、Score Map のクリック時に対象 GridCell の詳細を取得しやすくしてください。

### 4. 採点パネルを追加する

`demo.html` に、Score Map の近くか GridCell 一覧の上あたりに、採点パネルを追加してください。

最低限、次の要素を置いてください。

- 選択中 GridCell の表示エリア
- score 入力欄
- 採点ボタン
- メッセージ表示エリア

例として、以下のようなUIを想定します。

```html
<section class="panel score-rating-panel">
  <h2>選択中のマス</h2>
  <p id="selected-grid-label">GridCell を選択してください。</p>

  <form id="selected-grid-rating-form">
    <label for="selected-grid-score">score</label>
    <input id="selected-grid-score" type="number" min="1" max="10" value="5">
    <button id="selected-grid-rate-button" type="submit" disabled>採点する</button>
  </form>

  <p id="selected-grid-message" class="message"></p>
</section>
```

既存HTMLの構造・class名に合わせて調整してください。

### 5. 選択中 GridCell の情報を表示する

Score Map のマスをクリックしたら、採点パネルに次の情報を表示してください。

- GridCell ID
- row_index
- col_index
- initial_score
- average_user_score
- rating_count
- calculated_score

表示例:

```text
選択中 GridCell #12 / row 2 / col 3 / 現在のスコア 7.5
```

長くなりすぎる場合は、複数行に分けても構いません。

### 6. 選択中スタイルを付ける

選択中の Score Map マスには、分かりやすいCSSを追加してください。

例:

```css
.score-cell.is-selected {
  outline: 3px solid currentColor;
  outline-offset: -3px;
}
```

既存の色分けを壊さないようにしてください。
色指定は既存CSSの雰囲気に合わせてください。

### 7. 採点パネルから採点できるようにする

採点パネルのフォーム送信時に、選択中 GridCell に対して採点APIを呼んでください。

既存の `rateGrid(gridId)` を再利用できるなら再利用してください。
ただし、現在の `rateGrid(gridId)` はテーブル内の `[data-score-for="${gridId}"]` を参照しているため、必要に応じて次のように分離してください。

例:

```javascript
async function submitRating(gridId, score, comment = "demo page rating") {
  // POST /api/maps/grids/{gridId}/ratings/
}
```

その上で、

- テーブル側採点
- Score Map 採点パネル側採点

の両方から `submitRating()` を使う形にするとよいです。

### 8. 入力値チェック

score は 1〜10 の整数にしてください。

不正な場合は、APIを呼ばずに画面上にエラーを表示してください。

例:

```text
score は 1 から 10 の整数で入力してください。
```

### 9. メモグリッド切り替え時の挙動

メモグリッドを切り替えたときは、選択中 GridCell をリセットしてください。

表示は次のような状態に戻してください。

```text
GridCell を選択してください。
```

採点ボタンは disabled にしてください。

### 10. GridCell 再読み込み後の選択状態

採点後に `loadGrids()` で一覧を再読み込みしてください。

可能であれば、再読み込み後も同じ `selectedGridId` の GridCell を再選択状態にしてください。

ただし、対象 GridCell が再読み込み後に存在しない場合は、選択状態をリセットしてください。

## JavaScript 実装方針

既存 demo ページの書き方を優先してください。

特に、以下を守ってください。

- 既存の Basic 認証入力欄を使う
- 既存の `apiFetch()` を再利用する
- 既存の `setMessage()` の方針に合わせる
- 必要であれば、選択中 GridCell 用に `setSelectedGridMessage()` のような関数を追加する
- 既存のメモグリッド一覧取得を壊さない
- 既存のメモグリッド作成を壊さない
- 既存の共有相手管理を壊さない
- 既存の GridCell テーブル採点を壊さない
- 既存の Score Map 表示を壊さない
- `fetch` のエラー処理は既存方針に合わせる
- 成功後は画面表示を更新する

追加する関数名は、既存の命名に合わせてください。
迷う場合は、次のような名前にしてください。

```javascript
selectGrid(gridId)
clearSelectedGrid()
renderSelectedGrid()
setSelectedGridMessage(text, type = "")
submitRating(gridId, score, comment)
rateSelectedGrid(event)
```

## 既存のテーブル採点との関係

既存のテーブル側採点機能は残してください。

今回の追加後は、採点方法が2つになります。

1. GridCell 一覧テーブルの入力欄から採点
2. Score Map のマスをクリックして、採点パネルから採点

どちらも同じ採点APIを使ってください。

可能であれば、内部的なAPI呼び出し処理は共通化してください。

## CSS 方針

`demo.css` に必要なスタイルを追加してください。

最低限、次の表示が分かりやすくなるようにしてください。

- Score Map のマスがクリック可能であること
- hover 時に選択できそうに見えること
- 選択中マスが分かること
- 採点パネルが既存のdemo UIに馴染むこと
- 採点ボタン disabled 時の見た目が不自然でないこと

例:

```css
.score-cell {
  cursor: pointer;
}

.score-cell:hover {
  filter: brightness(1.08);
}

.score-cell.is-selected {
  outline: 3px solid currentColor;
  outline-offset: -3px;
}
```

既存CSSと競合する場合は、既存方針を優先してください。

## テスト方針

最低限、`MapDemoViewTests` に demo ページの表示確認を追加してください。

既存の `test_demo_page_returns_200` に追加するか、別テストに分けてください。

確認したい文言例:

- `選択中のマス`
- `GridCell を選択してください`
- `採点する`
- `score`

確認したいHTML要素例:

- `selected-grid-label`
- `selected-grid-rating-form`
- `selected-grid-score`
- `selected-grid-rate-button`
- `selected-grid-message`

JavaScriptのブラウザ実行テストまでは必須にしません。
このプロジェクトでは、まず demo ページが表示され、必要なUIが含まれることをDjangoのテストで確認してください。

ただし、`demo.js` の構文チェックは必ず行ってください。

## README 更新方針

必要であれば、`README.md` の確認用 demo ページ手順に、Score Map クリック採点の確認手順を追記してください。

追記する場合は、次のような流れにしてください。

1. demo ページを開く。
2. Basic 認証用の username / password を入力する。
3. メモグリッド一覧を取得する。
4. メモグリッドを選択する。
5. Score Map に GridCell が表示されることを確認する。
6. Score Map の任意のマスをクリックする。
7. 選択中のマス情報が採点パネルに表示されることを確認する。
8. score に 1〜10 の整数を入力する。
9. `採点する` を押す。
10. 採点後に Score Map と GridCell 一覧が更新されることを確認する。

`README.md` は長くなりすぎないように、demo ページでの確認に必要な分だけ追記してください。

## memo.md 更新方針

`memo.md` は引き継ぎ用メモファイルです。

作業後、今回の実装内容・確認結果・次にやるとよさそうなことを簡潔に追記してください。

追記例:

```markdown
## YYYY-MM-DD Score Map クリック採点対応

- Score Map のマスをクリックして GridCell を選択できるようにした。
- 選択中 GridCell を demo ページ内の採点パネルから採点できるようにした。
- 採点後に GridCell 一覧と Score Map を再読み込みする。
- 確認: `node --check maps/static/maps/demo.js`
- 確認: `python manage.py test maps`
- 次: 必要に応じて Score Map の見た目や地図画像との重ね合わせ精度を調整する。
```

実際に実行したコマンドだけを書いてください。
実行できなかったコマンドは、実行できなかった理由を書いてください。

## 今回は実装しないこと

- 採点APIの新規実装
- GridCell model の変更
- Rating model の変更
- migration の作成
- ユーザーごとの採点履歴一覧表示
- コメント入力欄の本格実装
- 採点の編集・削除
- Score Map のドラッグ選択
- 複数マスの一括採点
- 地図画像のアップロード
- 地図画像の座標補正
- Leaflet や Mapbox などの外部地図ライブラリ導入
- 依存関係の追加
- 本番用UIへの作り込み

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
- Score Map のマスをクリックできる
- クリックしたマスが選択状態になる
- 採点パネルに選択中 GridCell の情報が表示される
- score 未入力・範囲外・小数でエラーになる
- score 1〜10 の整数で採点できる
- 採点後に Score Map と GridCell 一覧が更新される
- 既存のテーブル側採点も引き続き動く
- 共有相手管理が壊れていない

## 注意事項

- 既存の demo ページの機能を壊さないでください。
- 既存のメモグリッド作成、一覧取得、GridCell 表示、テーブル採点、共有相手管理の流れを維持してください。
- API の認証情報は、既存の username/password 入力欄を使ってください。
- 採点APIは既存の `/api/maps/grids/{grid_id}/ratings/` を使ってください。
- Score Map の見た目は、既存のスコア色分けを維持してください。
- 選択中マスの見た目は、既存の色分けの邪魔にならないようにしてください。
- 依存関係は追加しないでください。
- 大きな設計変更はしないでください。
- 初心者が後から読んでも分かるように、複雑な処理には短いコメントを付けてください。