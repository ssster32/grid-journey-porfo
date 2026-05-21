# TASK.md 用プロンプト

## 現在のタスク

demo ページの Score Map 背景に地図画像を指定できるようにする

## 目的

グループメンバーへの説明時に地図イメージを伝えやすくするため、demo ページの Score Map 背景に任意の地図画像を指定できるようにする。

今回は画像アップロード機能は作らない。  
ローカルまたは静的ファイルとして配置した画像の URL を入力し、Score Map の背景として表示する。

## 作業範囲

- demo ページに背景画像 URL 入力欄を追加
- Score Map 背景レイヤーに画像 URL を反映
- Score Map のセルを背景画像の上に重ねても見やすいように調整
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

### 背景画像の指定方法

- demo ページに、Score Map 背景画像 URL の入力欄を追加する。
- 入力例として `/static/maps/demo-map.png` を placeholder または説明に使う。
- 画像アップロード機能は作らない。
- 画像ファイル自体は今回追加しなくてよい。
- ユーザーがローカルに配置した画像 URL を入力して使う想定にする。

例:

```text
/static/maps/demo-map.png
```

### 背景画像の反映

- 既存の `.score-map-background` レイヤーを活用する。
- JavaScript で入力された URL を読み取り、CSS custom property または style に反映する。
- 背景画像は Score Map の背面に表示する。
- Score Map のセルはその上に重ねて表示する。
- 背景画像 URL が空の場合は、現在の簡易背景表示を維持する。

### UI 方針

- 入力欄は Score Map の近くに置く。
- 画面が説明文だらけにならないよう、短いラベルにする。
- 例:
  - `Map image URL`
  - `Background image`
- 必要であれば `背景を反映` ボタンを追加する。
- 入力後すぐ反映してもよい。
- 入力値が空になったら背景画像を解除する。

### CSS 方針

- `.score-map-background` に背景画像を表示できるようにする。
- 背景画像は Score Map 全体に収まるようにする。
- `background-size` はまず `cover` または `100% 100%` のどちらかを選ぶ。
  - 地図スクリーンショットを Score Map の範囲に合わせたい場合は `100% 100%` が分かりやすい。
- 背景画像がないときも、現在の簡易背景が見えるようにする。
- Score Map のセルは背景画像の上でも score が読めるようにする。
  - 例: セル背景を少し透過する
  - score 文字に読みやすい色や軽い影を付ける
- score が主役である状態は維持する。

### JavaScript 方針

- 背景画像 URL 入力欄を取得する。
- 入力値を `.score-map-stage` または `.score-map-background` に反映する。
- CSS custom property を使う場合の例:

```js
elements.scoreMap.parentElement.style.setProperty(
  "--score-map-image",
  `url("${imageUrl}")`
);
```

- URL が空の場合は CSS custom property を削除する。
- `"` などが入った場合の扱いに注意し、最低限 `trim()` する。
- 今回は本格的な URL バリデーションは行わない。

## README 更新方針

README.md の demo ページ説明に、以下を短く追記する。

- Score Map 背景画像 URL を指定できる
- 画像アップロード機能はない
- 画像を使う場合は、例として `maps/static/maps/demo-map.png` に置き、`/static/maps/demo-map.png` を指定する
- 地図画像の利用条件には注意する
- 背景画像は説明用の簡易機能であり、外部地図 API 連携ではない

## API_SPEC 更新方針

API 仕様自体は変えない。  
必要であれば、表示方針メモとして以下だけ追記する。

- demo ページでは、Score Map 背景に任意の画像 URL を指定できる
- これは UI 側の表示機能であり、API レスポンス形式は変更しない
- 画像アップロードや外部地図 API 連携はまだ行わない

## テスト方針

以下を確認するテストを追加・更新する。

- demo ページが `200 OK` で表示される
- demo ページに Score Map 背景画像 URL 入力欄がある
- demo ページに `score-map-background` がある
- demo ページに `GridCell を再取得` が表示される
- demo ページに `GridCell を自動生成` が表示されない

JavaScript の構文チェックも行う。

```bash
node --check maps/static/maps/demo.js
```

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
- 画像アップロード機能は実装しないでください。
- 画像ファイル自体は今回追加しなくてよいです。
- 外部地図 API や新しいライブラリは追加しないでください。
- 地図画像の利用条件に注意する説明を README.md に入れてください。
- GridCell の生成・採点ロジックは変更しないでください。
- 既存テストを削除して通す対応はしないでください。