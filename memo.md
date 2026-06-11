# 引き継ぎメモ

更新日: 2026-06-11

## 概要

- Django REST Framework を使った地図採点 API。
- `MapArea` を作成すると、中心座標・行数・列数・セルサイズから地図範囲を計算し、`GridCell` を自動生成する。
- demo 画面では、メモグリッド一覧、Map Preview、選択中セルの採点、共有相手管理を確認できる。
- Score Map は削除済み。現在のセル確認・選択・範囲選択は Map Preview に一本化している。
- `initial_score_mode=auto` では、Overpass / OSM 由来の地物情報を使って初期スコアを計算し、`GridCell.auto_score_breakdown` に自動採点理由を保存する。

## 作業前に読むファイル

- `AGENTS.md`
- `RULES.md`
- `TASK.md`
- `README.md`
- `API_SPEC.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/views.py`
- `maps/tests.py`
- `maps/test_osm_services.py`
- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`

## 現在の Git 状態

このメモ作成前に確認した時点では、作業ツリーはクリーンだった。

```bash
git status --short
git diff --name-only
git diff --stat
```

上記はいずれも出力なし。

この `memo.md` 更新後は、`memo.md` だけが未コミット差分になる想定。

## 直近の demo UI 状態

### Score Map

- demo 画面から Score Map セクションを削除済み。
- 削除したもの:
  - `Score Map` 見出し
  - 表示モード `全体表示` / `詳細表示`
  - Score Map 専用のグリッド描画
  - Score Map 上のクリック選択
  - Score Map 上のドラッグ範囲選択
  - Score Map 専用 CSS
- JS からも `scoreMap`, `renderScoreMap`, `highlightSelectedScoreCells` などの参照を削除済み。

### Map Preview

- GridCell の表示・選択は Map Preview に一本化。
- Map Preview 上の GridCell はクリックで選択できる。
- Shift + ドラッグで範囲内の GridCell をまとめて選択できる。
- Shift を押さないドラッグは、Leaflet の通常の地図移動として動く。
- Score Map 削除後も、Map Preview のスコア色分け・境界表示・選択ハイライトは維持している。

### 上部ヘッダー

- 以前 `GridCell` 見出しがあった場所には、選択中メモグリッドの Name を表示する。
- 未選択時は `メモグリッドを選択してください` と表示する。
- メモグリッド選択時は、`selectArea(areaId, areaName)` の `areaName` を `#selected-area-name` に表示する。
- 右側の再取得ボタン文言は `セルの再取得`。
- 追加した Name 表示は少し大きめに調整済み。
- 下の `共有相手管理` との間隔は、`#message:empty` の余白を小さくして詰めている。

### 選択中のマス

- `選択中のマス` パネルは維持。
- 自動採点理由は、直近クリックしたセルだけ折りたたみ表示できる。
- 「再採点すると点数が更新されます。」の右側に小さく表示するレイアウトへ調整済み。
- 主な理由は横並び、それ以外の数値項目は縦並び。

## 自動採点まわりの主な状態

### initial_score_mode

- `manual`:
  - Overpass helper は呼ばない。
  - `region_feature_level` を `initial_score` / `calculated_score` に入れる。
- `auto`:
  - Overpass / OSM feature summary から GridCell ごとの初期スコアを計算する。
  - OSM 取得や feature summary 作成が失敗した場合は、MapArea 作成自体は止めず fallback する。
  - fallback では従来どおり `region_feature_level` を使う。

### score breakdown

- `calculate_initial_score_breakdown_from_feature_summary()` の主要項目を GridCell に保存できる。
- `GridCell.auto_score_breakdown` を API レスポンスに含める。
- demo 画面では、直近選択セルの自動採点理由として表示する。
- 保存・表示する代表項目:
  - `base_score`
  - `diversity_bonus`
  - `context_bonus`
  - `penalty`
  - `raw_score`
  - `clamped_score`
  - 主な加点フラグ

## OSM / scoring の主な加点方針

細かい数値は `maps/services.py` を正とすること。

- station:
  - surface station / subway station / public transport station を別々の context bonus として扱う。
  - station density は単純 count ではなく、距離ベースの station cluster 判定に置き換え済み。
  - bus station / unknown station は採点対象外。
- expressway:
  - motorway / motorway_link と trunk / trunk_link は別々の context bonus。
  - large bounds expressway は採点対象外。
  - unknown expressway は採点対象外。
- landmark:
  - tourism / historic 系を取得・分類する。
  - landmark は context_bonus にだけ反映する。
  - landmark_context_bonus の上限は 1.0。
  - historic_castle は landmark 加点が強め。
- castle proximity:
  - historic_castle 周辺セルに near / mid / far の proximity bonus を加える。
  - castle 本体セルには proximity bonus を加えない。
- station proximity / park + waterfront / high-context:
  - context candidate summary の結果をもとに、弱い context bonus として反映済み。
  - station proximity 対象から subway_station は除外済み。
- water / forest:
  - coverage ratio は bounds overlap ratio ベース。
- base_score / diversity_bonus / penalty に入れない方針の要素が多いので、変更時は必ず `context_bonus` だけかどうか確認する。

## ログ

`maps/views.py` で Overpass auto 系ログを出している。

主に確認するログ:

- `Overpass auto feature summary`
- `Overpass auto score breakdown summary`
- `Overpass auto station summary`
- `Overpass auto station cluster summary`
- `Overpass auto expressway summary`
- `Overpass auto effective expressway summary`
- `Overpass auto landmark summary`
- `Overpass auto castle proximity summary`
- `Overpass auto context candidate summary`

注意:

- Overpass クエリ全文やレスポンス全文はログに出さない方針。
- 緯度経度の詳細範囲や GridCell ごとの詳細 summary も原則ログに出さない。

## テスト状況

直近で実行済み:

```bash
.venv/bin/python manage.py test maps.tests
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
```

確認結果:

```text
maps.tests: 237 tests OK
MapDemoViewTests: 2 tests OK
System check identified no issues
```

Score Map 削除後、demo 表示テストは以下を確認するよう更新済み。

- `Score Map` が表示されない。
- Score Map 関連 DOM ID / class が出ない。
- `セルの再取得` が表示される。
- `selected-area-name` が表示される。
- `selected-area-label` / `grids-heading` は表示されない。
- Map Preview と選択中のマス UI は表示される。

## 注意点

- `TASK.md` は古い task 内容のまま残っている可能性がある。次の作業開始時は、ユーザーの最新依頼を優先しつつ `TASK.md` の内容が現在の作業に合っているか確認すること。
- `memo.md` は今回ユーザー依頼で更新している。通常の実装 task では、ユーザーが明示しない限り `memo.md` を触らない方針だった。
- `.venv` を使ってテストする。グローバル Python 環境には依存しない。
- DB / model / migration を変更する場合は、影響と migration の意味を初心者向けに説明する。

## 次にやるとよいこと

- demo 画面をブラウザで開き、上部のメモグリッド名、`セルの再取得` ボタン、共有相手管理との余白を目視確認する。
- UI 変更をさらに進める場合は、Map Preview と `選択中のマス` パネルの役割が重複していないかを見直す。
- scoring を変更する場合は、`maps/services.py` の breakdown と `maps/test_osm_services.py` の期待値をセットで更新する。
- demo 表示を変更する場合は、`maps.tests.MapDemoViewTests` を最低限実行する。

## 本サイト移行の現在地（2026-06-09 追記）

demo 画面で確認していた主要機能は、本サイト側の画面へかなり移行済み。
現在は demo を直接使う段階から、`/maps/`、`/maps/new/`、`/maps/<area_id>/` に分けた本サイト用 UI で確認する段階に近づいている。

### demo から本サイトへ移行済みの主な機能

- メモグリッド一覧表示。
- メモグリッド作成。
- メモグリッド詳細表示。
- 地図プレビュー上での GridCell 確認。
- Leaflet Map Preview。
- MapArea 全体枠表示。
- GridCell 境界表示。
- GridCell のスコア色分け。
- GridCell のスコアラベル表示。
- マスの単体選択、複数選択、Shift + ドラッグ範囲選択。
- 単体採点。
- 同一値一括採点。
- 採点後の GridCell 再取得と地図色更新。
- 自動採点理由表示。
- 共有相手管理。
- メモグリッド削除。
- 手動再取得。
- 画面全体ローディングオーバーレイ。

### 現在の本サイト画面構成

- `/maps/`
  - ログイン必須のメモグリッド一覧画面。
  - 自分のメモグリッドと共有されたメモグリッドを表示する。
  - 詳細画面へのリンクを表示する。
  - 新しいメモグリッド作成画面へのリンクを表示する。
  - 自分のメモグリッドは一覧から削除できる。
- `/maps/new/`
  - ログイン必須のメモグリッド作成画面。
  - name、description、center_lat、center_lng、rows、cols、grid_size_meters、initial_score_mode / region_feature_level、source を入力できる。
  - 作成処理は本サイト用 JS から Session 認証 + CSRF で `POST /api/maps/areas/` を呼ぶ。
  - 作成成功後は作成したメモグリッドの詳細画面へ移動する。
  - 作成処理中は共通ローディングオーバーレイを表示する。
  - 入力値に連動する Leaflet Map Preview を表示する。
  - PC 幅ではフォームと Map Preview を 2 カラムで表示する。
- `/maps/<area_id>/`
  - ログイン必須のメモグリッド詳細画面。
  - 地図プレビュー、選択中マス詳細、採点フォーム、共有相手管理、削除を扱う。
  - 本サイト側 JS は Session 認証前提で、Basic 認証欄は使わない。

### 本サイト画面改善の進捗

- ログイン画面
  - `/maps/` 系画面と近いカード風デザインに整理済み。
  - `ユーザー名`、`パスワード` の日本語ラベルに変更済み。
  - ログイン失敗時の表示を `.message` 系の見た目に寄せている。
- `/maps/`
  - 0 件時に `/maps/new/` への導線を表示する。
  - 一覧取得失敗時に再読み込みボタンを表示し、既存の一覧取得処理を再実行できる。
  - 一覧カードのメタ情報に `マスの数` を追加済み。`1マスの大きさ` の次に `マスの数: 縦 10 × 横 10` 形式で表示し、値がない場合は `未設定`。
  - 一覧 API レスポンスに `map_grid_rows` / `map_grid_cols` を追加済み。`Max("grid_cells__row_index")` / `Max("grid_cells__col_index")` を `annotate()` し、それぞれ +1 して算出することで、MapArea ごとの個別集計による N+1 を避けている。
  - 一覧 API レスポンス変更に合わせて `API_SPEC.md` も更新済み。
  - 一覧カードの削除導線を詳細リンクから分離し、危険操作として見えるように調整済み。
  - 一覧カード下部の削除欄は、`gap`、`margin-top`、`padding`、左線幅、削除欄内の削除ボタンサイズを調整してコンパクト化済み。
  - 警告文は `削除すると元に戻せません。` を維持し、赤系背景、枠・左線、赤い削除ボタンも残して危険操作の見た目を保っている。
  - 削除 API、確認ダイアログ、削除ボタン表示条件は変更していない。
- `/maps/new/`
  - 作成フォームと Map Preview を並べる 2 カラム構成に調整済み。
  - 中心緯度、中心経度、行数、列数、1マスの大きさから作成予定範囲を概算表示する。
  - マス数が多い場合は境界表示を省略し、重くなりすぎないようにしている。
- `/maps/<area_id>/`
  - 地図、一覧、選択状態、採点、管理の役割が分かるようにセクション導線を整理済み。
  - 説明文は提出前に読みやすい長さへ短縮済み。
  - 共有と削除は管理セクションにまとめている。
- 共通スタイル
  - `site.css` にボタン、メッセージ、フォーム、ローディング、セクション見出しなどの共通スタイルを整理済み。
  - 表示文言は本サイト向けに日本語化済み。
  - `Map Preview` は `地図プレビュー`、`score` は `スコア`、`comment` は `コメント`、`username` は画面上では `ユーザー名` / `共有相手のユーザー名` と表示する。
  - form の `name`、`id`、data 属性、API 送信用キーは既存機能を壊さないため英語名のまま維持している。

### 詳細画面で実装済みの機能

- 基本情報
  - ブラウザタイトルは `<メモグリッド名> | メモグリッド詳細` 形式。
  - 画面上の `h1` はメモグリッド名。
  - `メモグリッド詳細` は見出し下の補助テキストとして表示する。
  - 概要セクション見出しは `基本情報`。
  - 説明文は常時表示する。
  - `種別`、`作成者`、`1マスの大きさ`、`マスの数`、`初期スコア設定`、`地域特徴レベル`、`作成日時` は `詳細情報` の折りたたみ欄に入れている。
  - `マスの数` は `縦 10 × 横 10` 形式。
  - `MapArea` に `rows / cols` は保存されていないため、詳細画面では `area.grid_cells` の `row_index` / `col_index` 最大値 + 1 から `map_grid_rows` / `map_grid_cols` を算出している。
  - GridCell が無い場合、`マスの数` は `未設定`。
- Leaflet Map Preview
  - 詳細画面は地図プレビュー中心の UI に整理済み。
  - PC 幅では左に地図プレビュー、右に `選択中のマス` と `採点フォーム` を配置する。
  - GridCell のテキスト一覧は復活させず、地図プレビュー上で確認・選択する。
  - 地図プレビューの高さは PC 幅で大きめに調整済み。
  - `グリッドを再取得` ボタンは `地図プレビュー` 見出し横に移動し、小さめの補助ボタンにしている。
  - 地図操作・色の濃さ・表示切替はコンパクトに配置している。
  - 地図ステータスメッセージ欄は小型化済み。
  - MapArea 全体枠を表示する。
  - GridCell 境界を表示する。
  - GridCell 面を `calculated_score` に応じた半透明色で塗る。
  - スコア色分け凡例を表示する。
  - GridCell のスコア数値ラベルを表示する。
  - スコアラベルはズームに応じてサイズ class を切り替える。
  - スコア数値ラベルは背景・枠線・影を削除し、数値だけを軽く表示する。
  - 色の濃さスライダーでグリッド面の塗りを調整できる。
  - スコア数値ラベル表示 ON/OFF を切り替えられる。
  - 採点済み表示 ON/OFF を切り替えられる。
  - 採点済み表示の初期状態は OFF。
  - 採点済み印は小さめの `✓`。
  - 採点済み表示は `rating_count` ではなく、ログイン中ユーザー自身の採点有無で判定する。
  - 判定用に GridCell 一覧レスポンスへ `current_user_has_rating` を追加済み。
  - 表示 ON/OFF 状態はページ内 state で保持し、localStorage は使わない。
  - 通常地図にはズーム操作バーを追加済み。
    - `−`
    - `＋`
    - `範囲に戻す`
  - Leaflet 標準の左上ズームボタンは残している。
  - `範囲に戻す` は MapArea 全体が見える位置へ戻す。
- 選択操作
  - 通常クリックで単体選択できる。
  - Ctrl / Command クリックで複数選択できる。
  - Shift + ドラッグで範囲内のマスをまとめて選択できる。
  - 範囲選択中は Escape でキャンセルできる。
  - 選択状態は地図、拡大地図、右カラム、採点フォームへ同期する。
- 拡大表示モーダル
  - `拡大表示` ボタンを追加済み。
  - Fullscreen API ではなく、モーダル方式。
  - 拡大表示用 Leaflet map は通常地図とは別インスタンス。
  - モーダル表示後にコンテナサイズが安定してから map を作成する。
  - 背景地図タイルを先に表示し、その後に MapArea 枠、GridCell 境界、ラベル類を重ねる流れ。
  - `invalidateSize()` / `fitBounds()` のタイミングは調整済み。
  - 拡大表示を閉じる時は、拡大用 map / layer state を破棄・初期化する。
  - 以前発生した `Cannot read properties of undefined (reading 'parentNode')` は対策済み。
  - 拡大表示内にもズーム操作バーを追加済み。
    - `−`
    - `＋`
    - `範囲に戻す`
  - 拡大表示内でも通常クリック、Ctrl / Command クリック、Shift + ドラッグ範囲選択に対応済み。
- 採点
  - 単体選択時は単体採点フォームを表示する。
  - 複数選択時は同一スコア・同一コメントで一括採点するフォームだけを表示する。
  - 複数選択時の個別採点 UI は廃止済み。
  - 採点後は GridCell を再取得し、地図色分けとスコアラベルを更新する。
  - 採点中は画面全体ローディングオーバーレイを表示する。
- 選択中のマス表示
  - 右カラム側の `選択中のマス` と `採点フォーム` は余白・文字サイズを軽く調整済み。
  - `グリッド詳細`、`コメント`、`自動採点理由` は折りたたみ表示。
  - コメントはログイン中ユーザー自身の `GridRating.comment`。
  - GridCell 一覧レスポンスに `current_user_comment` を追加済み。
  - 複数選択時は一覧表示を短くし、`#1: 行 ...` のような形式にしている。
  - 選択中のマスに `auto_score_breakdown` がある場合、主な理由や内訳を表示する。
- 共有相手管理
  - メモグリッド作成者は共有相手一覧を表示できる。
  - username を指定して共有相手を追加できる。
  - 共有を解除できる。
- 削除
  - 自分のメモグリッドは詳細画面から削除できる。
  - 削除時は確認ダイアログを表示する。

### JS の整理状況

- `grid-detail-utils.js`
  - 表示用フォーマット、CSRF cookie 取得、API レスポンス読み取り、エラー文言生成、自動採点理由ラベルなどを担当する。
  - 詳細画面の小さな共通関数をまとめる場所になっている。
- `grid-detail-api.js`
  - 詳細画面で使う API 呼び出しを担当する。
  - GridCell 取得、単体採点、一括採点、メモグリッド削除、共有相手取得、共有追加、共有解除を扱う。
  - Session 認証 + CSRF 前提。
- `grid-detail.js`
  - 詳細画面の DOM 描画、選択状態、Leaflet 表示、採点フォーム、共有相手管理、削除などの画面制御を担当する。
  - かなり大きくなってきているので、今後は DOM 描画系の棚卸しと小分けを検討してよい。

### ローディングオーバーレイ

- 画面全体ローディングオーバーレイは `base.html` に共通化済み。
- CSS は `site-loading-overlay` 系 class で定義している。
- 詳細画面では、単体採点、同一値一括採点の処理中に表示する。
- 作成画面では、メモグリッド作成処理中に表示する。
- どちらも `finally` で非表示にする方針。

### demo 専用として本サイトに移行しないもの

- Basic 認証の username / password 入力欄。
- demo 用の 1 ページ完結 UI。
- demo 用の固定値や固定コメント文言。
- demo.js / demo.css の見た目や構造の直接移植。
- demo ページ内でメモグリッド一覧、作成、詳細をすべて切り替える検証用構成。

### 今後の候補

- 見た目改善は、提出前に小修正単位で進める。
- 詳細画面は機能が多いので、必要ならセクション順や余白の最終調整を行う。
- `/maps/new/` の Map Preview は表示まで実装済み。今後は地図クリックで中心座標を入力するかどうかを検討する。
- `grid-detail.js` が大きくなってきたため、DOM 描画、Leaflet、採点、共有管理などの分割を検討する。
- 必要になったタイミングで、本サイトと demo の機能差分を再確認する。
