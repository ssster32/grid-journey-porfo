# TASK: 未コミット差分を整理して、コミット単位を分ける

## 目的

ここまでの実装で、MapArea / GridCell / Overpass / 非同期化試験実装 / 画面表示 / 文書更新に関する変更が多数発生している。

このまま1つの大きなコミットにすると、後から内容を追いにくくなるため、未コミット差分を確認し、意味のある単位に分けてコミットできるよう整理する。

今回は **実装変更は行わない**。
目的は、現在の差分を確認し、コミット候補を分類し、どの順番でコミットすべきかを提案すること。

## 今回のタスク範囲

やること:

```text
- git status で未コミット差分を確認する
- git diff --name-only で変更ファイル一覧を確認する
- 各ファイルの差分内容をざっくり分類する
- コミット単位を提案する
- 各コミットの候補メッセージを提案する
- コミット前に確認すべきコマンドを提案する
```

やらないこと:

```text
- 実装変更
- ファイル編集
- コミット実行
- git add 実行
- git commit 実行
- git reset / checkout / restore 実行
- ブランチ操作
- rebase / merge
- force push
- テスト実行
```

## 対象

確認対象はリポジトリ全体。

主に想定される変更カテゴリ:

```text
- Overpass負荷対策
- GridCell生成状態管理
- APIレスポンスへの状態追加
- GridCell生成service切り出し
- management command追加
- auto作成pending返却
- 詳細画面のpending/running/failed表示
- 一覧画面の状態バッジ表示
- memo.md / API_SPEC.md / README.md / TASK.md などの文書更新
```

## 実行してよい確認コマンド

以下の確認コマンドは実行してよい。

```bash
git status --short
git diff --name-only
git diff --stat
git diff -- maps/models.py
git diff -- maps/serializers.py
git diff -- maps/views.py
git diff -- maps/services.py
git diff -- maps/tests.py
git diff -- maps/test_osm_services.py
git diff -- maps/admin.py
git diff -- maps/static/maps/js/grid-list.js
git diff -- maps/static/maps/css/site.css
git diff -- maps/templates/maps/grid_detail.html
git diff -- memo.md
git diff -- API_SPEC.md
git diff -- README.md
git diff -- TASK.md
```

必要に応じて、追加で以下も実行してよい。

```bash
find maps/management -maxdepth 3 -type f -print
git diff -- maps/management
```

## 実行してはいけないコマンド

以下は実行しない。

```bash
git add
git commit
git reset
git checkout
git restore
git clean
git stash
git merge
git rebase
git push
```

また、今回はテストコマンドも実行しない。

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test maps.tests
```

ただし、作業後に「ユーザーが実行すべき確認コマンド」として提示するのはよい。

## コミット分割の推奨方針

差分を確認した上で、次のような単位に分けられるか検討する。

### 1. Overpass負荷対策系

候補内容:

```text
- road取得除外
- building center mode
- 不完全building feature安全化
- Overpass分割取得の比較用実装
- Overpass軽量出力の比較用実装
- ログ追加
- 関連テスト
```

候補コミットメッセージ:

```text
Improve Overpass auto scoring performance diagnostics
```

または日本語なら:

```text
Overpass自動採点の負荷対策と検証ログを追加
```

### 2. GridCell生成状態管理のDB/API基盤

候補内容:

```text
- MapArea に grid_generation_status 系フィールド追加
- migration追加
- admin表示追加
- serializer/APIレスポンスに read-only 状態フィールド追加
- API_SPEC.md の状態フィールド説明
- 関連テスト
```

候補コミットメッセージ:

```text
Add GridCell generation status fields to MapArea
```

または:

```text
MapAreaにGridCell生成状態管理を追加
```

### 3. GridCell生成service化と状態更新

候補内容:

```text
- run_grid_generation_for_area(area) 追加
- views.py からservice呼び出しへ整理
- service内で running / completed / fallback_completed / failed 更新
- manual / auto / fallback の既存挙動維持
- 関連テスト
```

候補コミットメッセージ:

```text
Extract GridCell generation into service with status updates
```

または:

```text
GridCell生成処理をservice化し状態更新を追加
```

### 4. pending処理用management command

候補内容:

```text
- maps/management/commands/process_pending_grid_areas.py
- --dry-run
- --limit
- pending MapArea処理
- 1件失敗時も続行
- 関連テスト
```

候補コミットメッセージ:

```text
Add command to process pending GridCell generation
```

または:

```text
pending状態のGridCell生成を処理する管理コマンドを追加
```

### 5. auto作成pending返却

候補内容:

```text
- initial_score_mode=auto 作成時に即時GridCell生成しない
- auto作成時は pending 返却
- manual作成は従来通り即時生成
- process_pending_grid_areas で後から生成できる
- API_SPEC.md更新
- 関連テスト
```

候補コミットメッセージ:

```text
Return pending MapArea for auto grid generation
```

または:

```text
自動設定のMapArea作成をpending返却に変更
```

### 6. pending/running/failedの画面表示

候補内容:

```text
- 詳細画面で pending / running / failed 表示
- fallback_completed の注意表示
- pending/running/failed 時は地図・採点UI・詳細JSを非表示
- 一覧画面の状態バッジ
- grid-list.js の状態バッジ描画
- CSS追加
- 関連テスト
```

候補コミットメッセージ:

```text
Show GridCell generation status in map pages
```

または:

```text
MapArea一覧・詳細にGridCell生成状態表示を追加
```

### 7. 文書更新

候補内容:

```text
- memo.md
- API_SPEC.md
- README.md
- 非同期化試験実装の現在仕様
- process_pending_grid_areas の運用方針
- Render運用方針
```

候補コミットメッセージ:

```text
Document async grid generation trial workflow
```

または:

```text
非同期化試験実装と運用方針を文書化
```

## 注意点

実際の差分を見て、上記の通りにきれいに分けられない場合は、無理に分けない。

例えば、同じファイル内に複数カテゴリの変更が混ざっている場合は、以下を提案する。

```text
- 安全に分けられるファイル単位で分ける
- どうしても混ざっている場合は1コミットにまとめる
- git add -p が必要そうな箇所は「ユーザー判断」として明記する
```

Codex側で `git add -p` やコミット操作はしない。

## 確認してほしいこと

差分整理時に、特に以下を確認する。

```text
- README.md と TASK.md に意図しない差分があるか
- migrationファイルが作成済みか
- maps/management/__init__.py と commands/__init__.py が含まれているか
- API_SPEC.md と memo.md の内容が現在仕様と矛盾していないか
- services.py にOverpass検証系とGridCell生成service系の変更が混ざっているか
- tests.py に複数カテゴリのテストが混在しているか
```

## 作業後に報告してほしいこと

以下を報告する。

```text
- 未コミットの変更ファイル一覧
- 変更ファイルごとの内容要約
- 推奨コミット分割案
- 各コミットに含めるファイル候補
- 各コミットの候補メッセージ
- 分割が難しいファイルと理由
- README.md / TASK.md に意図しない差分があるか
- コミット前にユーザーが実行すべき確認コマンド
- 今回 git add / commit / reset / restore 等は実行していないこと
```

## コミット前にユーザーが実行するとよい確認コマンド

作業後の報告に、以下を含める。

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test maps.tests
.venv/bin/python manage.py test maps.test_osm_services
.venv/bin/python manage.py makemigrations --check --dry-run
```

必要に応じて、手動確認として以下も提案する。

```bash
.venv/bin/python manage.py process_pending_grid_areas --dry-run
.venv/bin/python manage.py process_pending_grid_areas --limit 1
```
