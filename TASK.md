# TASK: 非同期化試験実装の現在仕様を memo.md と API_SPEC.md に整理する

## 目的

メモグリッド自動設定作成の非同期化に向けた試験実装が進み、現在の仕様が大きく変わった。

これまでの変更で、以下が実装済み。

```text
- MapArea に GridCell生成状態管理フィールドを追加
- MapArea API レスポンスに grid_generation_status 系フィールドを read-only で追加
- GridCell生成処理を run_grid_generation_for_area(area) に切り出し
- run_grid_generation_for_area() 内で running / completed / fallback_completed / failed を更新
- pending 状態の MapArea を処理する management command を追加
- initial_score_mode=auto の MapArea 作成時は GridCell を即時生成せず pending で返却
- manual 作成時は従来通り即時 GridCell 生成
- 詳細画面で pending / running / failed / fallback_completed に応じた表示を追加
- 一覧画面で GridCell生成状態バッジを表示
```

今回は、これらの現在仕様を `memo.md` と `API_SPEC.md` に整理して反映する。

## 今回のタスク範囲

実装する:

```text
- memo.md に非同期化試験実装の現在仕様を整理して追記・更新する
- API_SPEC.md に auto 作成時 pending 返却、状態フィールド、management command による生成フローを整理して追記・更新する
- 既存記述と矛盾している箇所があれば修正する
```

実装しない:

```text
- Pythonコード変更
- model変更
- migration作成
- serializer変更
- views変更
- JavaScript変更
- CSS変更
- テスト変更
- Overpass処理変更
- スコア計算変更
- 2km制限変更
```

## 対象ファイル

変更対象:

* `memo.md`
* `API_SPEC.md`

確認対象:

* `maps/models.py`
* `maps/serializers.py`
* `maps/views.py`
* `maps/services.py`
* `maps/management/commands/process_pending_grid_areas.py`
* `maps/templates/maps/grid_detail.html`
* `maps/static/maps/js/grid-list.js`

今回は変更しない:

* Pythonコード
* migration
* JavaScript
* CSS
* README.md
* tests

## memo.md に整理する内容

既存の非同期化設計・負荷対策・現在仕様の記述に合わせて、以下を自然に追記・更新する。

### 1. 現在の作成フロー

以下を整理する。

```text
manual作成:
MapArea作成
→ run_grid_generation_for_area(area)
→ GridCell即時生成
→ grid_generation_status=completed
→ レスポンス返却

auto作成:
MapArea作成
→ GridCellは即時生成しない
→ grid_generation_status=pending
→ レスポンス返却
→ process_pending_grid_areas で後からGridCell生成
→ completed / fallback_completed / failed
```

### 2. 状態値の意味

以下の状態を整理する。

```text
pending:
MapAreaは作成済みだが、GridCell生成はまだ開始されていない

running:
GridCell生成処理中

completed:
GridCell生成完了

fallback_completed:
自動設定に失敗したが、標準値でGridCell生成完了

failed:
GridCell生成失敗
```

### 3. MapAreaの状態管理フィールド

以下のフィールドを記録する。

```text
grid_generation_status
grid_generation_started_at
grid_generation_finished_at
grid_generation_error_message
grid_generation_attempt_count
```

補足:

```text
- status は API レスポンスにも read-only で返す
- started_at / finished_at は生成開始・完了時刻
- error_message は fallback / failed 時の短い内部エラー
- attempt_count は生成処理の試行回数
```

### 4. management command

以下を記録する。

```bash
python manage.py process_pending_grid_areas
python manage.py process_pending_grid_areas --dry-run
python manage.py process_pending_grid_areas --limit 1
```

説明:

```text
- pending の MapArea を created_at, id 順に取得
- run_grid_generation_for_area(area) を呼ぶ
- 1件失敗しても残りを続行
- dry-run は対象表示のみ
- limit は処理件数制限
```

### 5. 画面表示

一覧画面:

```text
- GridCell生成状態バッジを表示
- pending / running / completed / fallback_completed / failed を区別
- pending / running / fallback_completed / failed は短い補足文も表示
```

詳細画面:

```text
- pending / running / failed では基本情報と状態メッセージ、再読み込みリンクを表示
- pending / running / failed では地図・採点フォーム・共有/削除UI・詳細JSを表示しない
- fallback_completed は通常表示しつつ、標準値で作成した注意表示を出す
- completed は通常表示
```

### 6. 現時点で未実装のこと

以下を明確に書く。

```text
- Celery / RQ / Redis は未導入
- 自動でmanagement commandを起動する仕組みは未実装
- 自動ポーリングは未実装
- 本番スケジューラ設定は未実装
- 再試行ボタンは未実装
```

### 7. 注意点

以下も必要に応じて記録する。

```text
- auto作成直後はGridCellが存在しない
- pendingのままでは詳細画面に地図は出ない
- GridCell生成には management command の実行が必要
- 現状は「完全な非同期ジョブキュー」ではなく、management command を使った試験的な遅延実行
```

## API_SPEC.md に整理する内容

API仕様として、以下を追記・更新する。

### 1. MapArea作成APIの挙動

`POST /api/maps/areas/` の説明に、manual / auto の違いを明記する。

```text
initial_score_mode=manual:
- 作成リクエスト内でGridCellを即時生成する
- レスポンス時点で grid_generation_status=completed
- GridCell一覧APIでGridCellを取得できる

initial_score_mode=auto:
- 作成リクエスト内ではGridCellを生成しない
- レスポンス時点で grid_generation_status=pending
- GridCell生成は management command / 将来のジョブ処理で行う
- pending中はGridCell一覧APIが空になる場合がある
```

### 2. MapAreaレスポンス項目

既に追加済みの以下の項目を、説明とともに整理する。

```text
grid_generation_status
grid_generation_status_display
grid_generation_started_at
grid_generation_finished_at
grid_generation_error_message
grid_generation_attempt_count
```

説明例:

```text
grid_generation_status:
GridCell生成状態。pending / running / completed / fallback_completed / failed のいずれか。

grid_generation_status_display:
grid_generation_status の表示名。

grid_generation_started_at:
GridCell生成開始日時。未開始の場合は null。

grid_generation_finished_at:
GridCell生成完了日時。未完了の場合は null。

grid_generation_error_message:
GridCell生成失敗または fallback 時の短い内部エラーメッセージ。通常は空文字。

grid_generation_attempt_count:
GridCell生成処理の試行回数。
```

### 3. GridCell一覧APIのpending時挙動

`GET /api/maps/areas/<area_id>/grids/` について、pending中はGridCellが未生成のため空になる可能性があることを明記する。

```text
- grid_generation_status=pending/running の場合、GridCellがまだ存在しない場合がある
- その場合、レスポンスは空配列になる可能性がある
- GridCell生成完了後に再取得する
```

### 4. management command はAPIではないことを明記

API_SPEC.md に書く場合は、「運用・開発用コマンド」として整理する。

```bash
python manage.py process_pending_grid_areas
python manage.py process_pending_grid_areas --dry-run
python manage.py process_pending_grid_areas --limit 1
```

注意:

```text
- これはHTTP APIではない
- pendingのMapAreaを処理するためのDjango management command
- 現状は手動実行または将来のスケジューラ想定
```

### 5. 例レスポンスの更新

MapArea作成レスポンス例に、状態フィールドを含める。

manual例:

```json
{
  "id": 1,
  "name": "手動作成サンプル",
  "initial_score_mode": "manual",
  "grid_generation_status": "completed",
  "grid_generation_status_display": "作成完了",
  "grid_generation_started_at": "2026-06-25T12:00:00+09:00",
  "grid_generation_finished_at": "2026-06-25T12:00:01+09:00",
  "grid_generation_error_message": "",
  "grid_generation_attempt_count": 1
}
```

auto例:

```json
{
  "id": 2,
  "name": "自動作成サンプル",
  "initial_score_mode": "auto",
  "grid_generation_status": "pending",
  "grid_generation_status_display": "作成待ち",
  "grid_generation_started_at": null,
  "grid_generation_finished_at": null,
  "grid_generation_error_message": "",
  "grid_generation_attempt_count": 0
}
```

実際の既存レスポンス項目に合わせ、必要に応じて既存項目を省略せず更新する。

## 書き方の注意

* 「完全な非同期化が完了した」と書かない
* 「Celeryを導入済み」と書かない
* 「自動でバックグラウンド実行される」と断定しない
* 「auto作成後すぐGridCellがある」と書かない
* 「2km制限を解除した」と書かない
* 「GridCell生成は management command / 将来のジョブ処理で行う」と書く
* 現状は「management command を使った試験的な遅延実行」として整理する

## やってよい変更

* `memo.md` の現在仕様追記・整理
* `API_SPEC.md` の作成API・レスポンス例・GridCell一覧API説明の更新
* 既存記述との矛盾修正
* 表現の軽微な整理

## やってはいけない変更

* Pythonコードを変更する
* JavaScriptを変更する
* CSSを変更する
* migrationを作る
* README.mdを変更する
* testsを変更する
* Overpass処理を変更する
* スコア計算を変更する
* 2km制限を変更する
* management commandの挙動を変更する

## 確認

確認コマンドやテストコマンドは実行しない。

文書更新のみなので、作業後は以下のような差分確認だけでよい。

```bash
git diff -- memo.md API_SPEC.md
rg -n "grid_generation_status|process_pending_grid_areas|pending|fallback_completed" memo.md API_SPEC.md
git diff --name-only
```

## 作業後に報告してほしいこと

* 変更したファイル
* memo.md に追記・整理した内容
* API_SPEC.md に追記・整理した内容
* manual / auto の作成フローを明記したこと
* pending中はGridCellが未生成の場合があることを明記したこと
* management command がHTTP APIではないことを明記したこと
* 現状は完全な非同期ジョブキューではないことを明記したこと
* Pythonコード / JS / CSS / tests / README.md を変更していないこと
* 確認コマンドやテストコマンドを実行したかどうか

  * 実行していない場合は「実行していない」と明記する
