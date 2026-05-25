# Codex タスク: Score Map で複数グリッドを選択して採点できるようにする

## 担当ロール

今回は **Frontend Developer** と **Tester** として作業してください。

確認用 `demo` ページの Score Map を改善し、複数の GridCell を選択してまとめて採点できるようにしてください。

採点方式は次の2種類を選べるようにします。

1. 個別に入力し、まとめて採点
2. 選択グリッドを全て同じ値で採点

この demo ページは開発確認用です。
本番向けの完成 UI ではなく、既存 API の動作確認と今後の地図 UI 検証をしやすくするためのページとして実装してください。

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
- `maps/serializers.py`

特に、以下を確認してください。

- `demo.js` の `state`
- `selectedGridId`
- `selectedGrid`
- `gridsById`
- `selectGrid(gridId)`
- `clearSelectedGrid()`
- `renderSelectedGrid()`
- `renderScoreMap(grids)`
- `renderGrids(grids)`
- `submitRating(gridId, score, comment)`
- `rateSelectedGrid(event)`
- 既存の Score Map クリック選択処理
- 既存の単体採点パネル
- 既存の一括採点 API
- `BulkGridRatingSerializer`
- `BulkGridRatingCreateViewTests`
- `MapDemoViewTests`

## 今回の目的

現在の demo ページでは、Score Map のマスを1つクリックして選択し、選択中の GridCell を採点できます。

今回の目的は、Score Map 上で複数の GridCell を選択し、次の2種類の方式で採点できるようにすることです。

### 採点方式1: 個別に入力し、まとめて採点

選択した GridCell ごとに score 入力欄を表示し、それぞれ別の score を入力して、まとめて採点できるようにします。

例:

```text
GridCell #1: 8
GridCell #2: 5
GridCell #3: 10
```

この方式では、既存の単体採点 API を複数回呼び出して構いません。

```text
POST /api/maps/grids/{grid_id}/ratings/
```

### 採点方式2: 選択グリッドを全て同じ値で採点

選択した GridCell 全てに同じ score を付けます。

例:

```text
GridCell #1, #2, #3 をすべて 7 点で採点
```

この方式では、既存の一括採点 API を使ってください。

```text
POST /api/maps/grids/bulk-ratings/
```

## 今回やること

- Score Map で複数の GridCell を選択できるようにする
- 選択中 GridCell を単数ではなく複数管理できる state を追加する
- 複数選択中の GridCell 一覧を demo ページに表示する
- 採点方式を選択できる UI を追加する
- 「個別に入力し、まとめて採点」用の入力 UI を追加する
- 「選択グリッドを全て同じ値で採点」用の入力 UI を追加する
- 選択中 GridCell の選択解除をできるようにする
- 選択をすべて解除できるようにする
- 採点成功後に GridCell 一覧と Score Map を再読み込みする
- 再読み込み後も、存在する GridCell は選択状態を維持する
- 必要に応じて `MapDemoViewTests` に表示確認を追加する
- 必要に応じて `README.md` の demo ページ確認手順を更新する
- `memo.md` に作業内容と確認結果を追記する

## 対象 API

### 単体採点 API

個別入力方式では、既存の単体採点 API を複数回呼び出してください。

```text
POST /api/maps/grids/{grid_id}/ratings/
```

リクエスト例:

```json
{
  "score": 8,
  "comment": "demo page multi rating"
}
```

### 一括採点 API

同じ値でまとめて採点する方式では、既存の一括採点 API を使ってください。

```text
POST /api/maps/grids/bulk-ratings/
```

リクエスト例:

```json
{
  "grid_ids": [1, 2, 3],
  "score": 7,
  "comment": "demo page bulk rating"
}
```

一括採点 API は、権限外または存在しない GridCell が1件でも含まれる場合、全体を失敗させる想定です。
一部だけ成功させる実装にはしないでください。

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

単体採点 API と一括採点 API は既に実装済みの前提です。
API 側に明らかな不具合を見つけた場合は、勝手に大きく修正せず、原因と修正方針を説明してから最小限の修正にしてください。

## UI 方針

現在の `選択中のマス` パネルを、複数選択に対応したパネルへ拡張してください。

表示名は、ユーザー向けに分かりやすくするため、次のような文言を使ってください。

```text
選択中のマス
選択中 GridCell
選択数
選択をすべて解除
採点方式
個別に入力し、まとめて採点
選択グリッドを全て同じ値で採点
まとめて採点する
同じ値で採点する
```

内部名として `GridCell`、`bulkRating`、`selectedGridIds` などを使うのは構いません。
画面表示でも、開発確認用ページなので `GridCell` という語は使って構いません。

## UI の具体要件

### 1. Score Map の複数選択

Score Map のマスをクリックすると、その GridCell の選択状態を切り替えてください。

- 未選択のマスをクリック → 選択する
- 選択済みのマスをクリック → 選択解除する

既存の単体選択のように、クリックしたら他の選択が消える挙動ではなく、複数選択できる挙動にしてください。

キーボード操作も既存方針を維持してください。

- `Enter`
- `Space`

で選択状態を切り替えられるようにしてください。

### 2. state を複数選択対応にする

既存の `state` は単体選択向けです。

現在のような状態:

```javascript
selectedGridId: null,
selectedGrid: null,
```

を残すか置き換えるかは既存コードとの相性で判断してください。

推奨は、複数選択用に次を追加する形です。

```javascript
selectedGridIds: new Set(),
```

必要であれば、選択中 GridCell の配列を取得する helper を追加してください。

例:

```javascript
function selectedGrids() {
  return Array.from(state.selectedGridIds)
    .map((gridId) => state.gridsById.get(gridId))
    .filter(Boolean);
}
```

既存の `selectedGridId` / `selectedGrid` を残す場合は、最後に選択した GridCell を表す用途に限定してください。
ただし、実装が複雑になる場合は、複数選択用の state に整理して構いません。

### 3. 選択状態のCSS

選択中の Score Map マスには、引き続き `.is-selected` を付けてください。

複数の `.score-cell` が同時に `.is-selected` になる想定です。

既存の色分けを壊さないようにしてください。

必要であれば、複数選択中に分かりやすい表示を追加してください。

例:

```css
.score-cell.is-selected {
  outline: 3px solid rgba(23, 111, 92, 0.86);
  outline-offset: -3px;
}
```

既存CSSがある場合は、それを活かしてください。

### 4. 選択中 GridCell 一覧の表示

採点パネル内に、選択中 GridCell の一覧を表示してください。

最低限、各 GridCell について次を表示してください。

- GridCell ID
- row_index
- col_index
- calculated_score
- 個別採点用 score 入力欄
- 選択解除ボタン

表示例:

```text
#1 / row 0 / col 0 / 現在のスコア 5.5 / score [8] / 選択解除
#2 / row 0 / col 1 / 現在のスコア 3.0 / score [5] / 選択解除
```

選択中 GridCell がない場合は、次のようなメッセージを表示してください。

```text
GridCell を選択してください。
```

### 5. 選択数の表示

選択中の GridCell 数を表示してください。

例:

```text
選択数: 3
```

### 6. 選択をすべて解除

選択中 GridCell をすべて解除するボタンを追加してください。

表示例:

```text
選択をすべて解除
```

未選択時は disabled にしてください。

### 7. 採点方式の選択 UI

採点方式を選択できる UI を追加してください。

実装しやすい形式で構いませんが、推奨は radio button です。

例:

```html
<label>
  <input type="radio" name="multi-rating-mode" value="individual" checked>
  個別に入力し、まとめて採点
</label>
<label>
  <input type="radio" name="multi-rating-mode" value="same">
  選択グリッドを全て同じ値で採点
</label>
```

選択した方式に応じて、表示する入力欄やボタンを分けてください。

### 8. 個別に入力し、まとめて採点

この方式では、選択中 GridCell ごとの score 入力欄を使って採点してください。

- 各 GridCell ごとに 1〜10 の整数を入力する
- `まとめて採点する` を押す
- 各 GridCell に対して単体採点 API を呼ぶ

リクエストは、既存の `submitRating(gridId, score, comment)` を再利用できるなら再利用してください。

ただし、現在の `submitRating()` が毎回 `loadGrids()` を呼ぶ実装の場合、複数回採点時に毎回再読み込みすると非効率です。
必要であれば、API 呼び出し部分と再読み込み部分を分けてください。

例:

```javascript
async function postRating(gridId, score, comment = "demo page rating") {
  return apiFetch(`/api/maps/grids/${gridId}/ratings/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ score, comment }),
  });
}

async function submitRating(gridId, score, comment = "demo page rating") {
  await postRating(gridId, score, comment);
  await loadGrids();
}
```

個別まとめ採点では、`postRating()` を複数回呼び、最後に1回だけ `loadGrids()` してください。

### 9. 選択グリッドを全て同じ値で採点

この方式では、一括採点 API を使ってください。

- 共通 score 入力欄を表示する
- `同じ値で採点する` を押す
- `grid_ids` に選択中 GridCell ID を入れる
- `score` に共通 score を入れる
- `POST /api/maps/grids/bulk-ratings/` を呼ぶ
- 成功後に `loadGrids()` を1回だけ呼ぶ

実装例:

```javascript
async function submitBulkRating(gridIds, score, comment = "demo page bulk rating") {
  await apiFetch("/api/maps/grids/bulk-ratings/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      grid_ids: gridIds,
      score,
      comment,
    }),
  });
  await loadGrids();
}
```

### 10. 入力値チェック

score は 1〜10 の整数にしてください。

不正な場合は、APIを呼ばずに画面上にエラーを表示してください。

例:

```text
score は 1 から 10 の整数で入力してください。
```

個別入力方式では、1件でも不正な score がある場合は、API を呼ばずに全体を止めてください。

例:

```text
GridCell #12 の score は 1 から 10 の整数で入力してください。
```

### 11. 選択なしの場合

選択中 GridCell が 0 件の状態で採点しようとした場合は、API を呼ばずにエラーを表示してください。

例:

```text
採点する GridCell を選択してください。
```

### 12. メモグリッド切り替え時の挙動

メモグリッドを切り替えたときは、選択中 GridCell をすべてリセットしてください。

表示は次のような状態に戻してください。

```text
GridCell を選択してください。
```

採点ボタンは disabled にしてください。

### 13. GridCell 再読み込み後の選択状態

採点後に `loadGrids()` で一覧を再読み込みしてください。

再読み込み後も、選択中 GridCell ID が存在する場合は選択状態を維持してください。

ただし、対象 GridCell が再読み込み後に存在しない場合は、その GridCell ID は選択状態から外してください。

## JavaScript 実装方針

既存 demo ページの書き方を優先してください。

特に、以下を守ってください。

- 既存の Basic 認証入力欄を使う
- 既存の `apiFetch()` を再利用する
- 既存の `setMessage()` / `setSelectedGridMessage()` の方針に合わせる
- 既存のメモグリッド一覧取得を壊さない
- 既存のメモグリッド作成を壊さない
- 既存の共有相手管理を壊さない
- 既存の Score Map 表示を壊さない
- 既存の単体クリック採点機能を、複数選択採点へ自然に発展させる
- `fetch` のエラー処理は既存方針に合わせる
- 成功後は画面表示を更新する
- 採点API呼び出し処理は、できるだけ共通化する

追加する関数名は、既存の命名に合わせてください。
迷う場合は、次のような名前にしてください。

```javascript
selectedGrids()
toggleGridSelection(gridId)
clearSelectedGrids()
removeSelectedGrid(gridId)
renderSelectedGrids()
highlightSelectedScoreCells()
readMultiRatingMode()
readIndividualScores()
postRating(gridId, score, comment)
submitIndividualRatings(event)
submitSameScoreBulkRating(event)
submitBulkRating(gridIds, score, comment)
```

## 既存の単体選択UIとの関係

現在の `選択中のマス` パネルは、単体 GridCell を採点する前提です。

今回のタスクでは、このパネルを複数選択対応へ拡張してください。

既存の単体採点パネルを完全に削除する必要はありませんが、ユーザーが混乱しないようにしてください。

推奨は、次の形です。

- パネル名は `選択中のマス` のまま
- 未選択時は `GridCell を選択してください。`
- 1件選択時も複数選択時も同じパネルで扱う
- 選択中一覧を表示する
- 採点方式を選べる
- 1件だけ選択している場合でも、個別入力方式・同じ値方式のどちらでも採点できる

## CSS 方針

`demo.css` に必要なスタイルを追加してください。

最低限、次の表示が分かりやすくなるようにしてください。

- Score Map のマスが複数選択できること
- 選択中のマスが複数分かること
- 選択中 GridCell 一覧が見やすいこと
- 個別入力欄が詰まりすぎないこと
- 採点方式の選択 UI が分かりやすいこと
- 採点ボタン disabled 時の見た目が不自然でないこと
- モバイル幅でも大きく崩れないこと

例:

```css
.selected-grid-list {
  display: grid;
  gap: 8px;
}

.selected-grid-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px auto;
  gap: 8px;
  align-items: end;
}

.rating-mode-options {
  display: grid;
  gap: 8px;
}
```

既存CSSと競合する場合は、既存方針を優先してください。

## テスト方針

最低限、`MapDemoViewTests` に demo ページの表示確認を追加してください。

既存の `test_demo_page_returns_200` に追加するか、別テストに分けてください。

確認したい文言例:

- `選択数`
- `選択をすべて解除`
- `採点方式`
- `個別に入力し、まとめて採点`
- `選択グリッドを全て同じ値で採点`
- `まとめて採点する`
- `同じ値で採点する`

確認したいHTML要素例:

- `selected-grid-count`
- `clear-selected-grids`
- `selected-grids-list`
- `multi-rating-mode-individual`
- `multi-rating-mode-same`
- `same-score-input`
- `individual-rating-submit`
- `same-score-rating-submit`

JavaScriptのブラウザ実行テストまでは必須にしません。
このプロジェクトでは、まず demo ページが表示され、必要なUIが含まれることを Django のテストで確認してください。

ただし、`demo.js` の構文チェックは必ず行ってください。

## README 更新方針

必要であれば、`README.md` の確認用 demo ページ手順に、複数選択採点の確認手順を追記してください。

追記する場合は、次のような流れにしてください。

1. demo ページを開く。
2. Basic 認証用の username / password を入力する。
3. メモグリッド一覧を取得する。
4. メモグリッドを選択する。
5. Score Map に GridCell が表示されることを確認する。
6. Score Map の複数のマスをクリックして選択する。
7. 選択数が増えることを確認する。
8. `個別に入力し、まとめて採点` を選び、GridCell ごとに score を入力する。
9. `まとめて採点する` を押し、Score Map と GridCell 一覧が更新されることを確認する。
10. 再度複数のマスを選択する。
11. `選択グリッドを全て同じ値で採点` を選び、共通 score を入力する。
12. `同じ値で採点する` を押し、Score Map と GridCell 一覧が更新されることを確認する。
13. `選択をすべて解除` で選択状態をリセットできることを確認する。

`README.md` は長くなりすぎないように、demo ページでの確認に必要な分だけ追記してください。

## memo.md 更新方針

`memo.md` は引き継ぎ用メモファイルです。

作業後、今回の実装内容・確認結果・次にやるとよさそうなことを簡潔に追記してください。

追記例:

```markdown
## YYYY-MM-DD Score Map 複数選択採点対応

- Score Map のマスを複数選択できるようにした。
- 選択中 GridCell 一覧を demo ページ内に表示するようにした。
- 採点方式として、個別入力まとめ採点と同じ値での一括採点を選べるようにした。
- 個別入力まとめ採点では、単体採点 API を複数回呼び、最後に GridCell 一覧を再読み込みする。
- 同じ値での一括採点では、一括採点 API を使う。
- 確認: `node --check maps/static/maps/demo.js`
- 確認: `python manage.py test maps`
- 次: 必要に応じてドラッグ選択や矩形選択を検討する。
```

実際に実行したコマンドだけを書いてください。
実行できなかったコマンドは、実行できなかった理由を書いてください。

## 今回は実装しないこと

- 採点APIの新規実装
- 一括採点APIの新規実装
- GridCell model の変更
- GridRating model の変更
- migration の作成
- ユーザーごとの採点履歴一覧表示
- コメント入力欄の本格実装
- 採点の編集・削除専用 UI
- Score Map のドラッグ選択
- 矩形選択
- 範囲選択
- Shift クリック選択
- Ctrl / Cmd クリック専用操作
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
- Score Map のマスを複数クリックして選択できる
- 選択済みマスをもう一度クリックすると選択解除できる
- 選択中マスが複数分かる
- 選択数が表示される
- 選択中 GridCell 一覧が表示される
- 各 GridCell の個別 score 入力欄が表示される
- 個別入力方式でまとめて採点できる
- 同じ値方式で一括採点できる
- score 未入力・範囲外・小数でエラーになる
- 採点後に Score Map と GridCell 一覧が更新される
- 採点後も存在する選択中 GridCell は選択状態を維持する
- 選択をすべて解除できる
- メモグリッド切り替え時に選択状態がリセットされる
- 共有メモグリッドでも、権限がある場合は採点できる
- 既存の共有相手管理が壊れていない

## 注意事項

- 既存の demo ページの機能を壊さないでください。
- 既存のメモグリッド作成、一覧取得、GridCell 表示、共有相手管理の流れを維持してください。
- API の認証情報は、既存の username/password 入力欄を使ってください。
- 個別入力方式では、既存の単体採点 API を使ってください。
- 同じ値方式では、既存の一括採点 API を使ってください。
- 一括採点 API の仕様を demo ページ側で変えないでください。
- Score Map の見た目は、既存のスコア色分けを維持してください。
- 選択中マスの見た目は、既存の色分けの邪魔にならないようにしてください。
- 依存関係は追加しないでください。
- 大きな設計変更はしないでください。
- 初心者が後から読んでも分かるように、複雑な処理には短いコメントを付けてください。