# 引き継ぎメモ

更新日: 2026-06-05

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
