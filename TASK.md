# Codex タスク: MapArea に initial_score_mode を追加し、MapArea作成APIで manual / auto を受け取れるようにする

## 担当ロール

今回は **Backend Developer** と **Tester** として作業してください。

MapArea に `initial_score_mode` を追加し、MapArea作成APIで `manual` / `auto` を受け取れるようにしてください。

今回は **バックエンド実装のみ** を対象にします。  
demoページ、README.md、API_SPEC.md は今回変更しないでください。

## レート制限節約の方針

今回はレート制限節約を優先してください。

- 変更範囲を必要最小限にしてください。
- demoページは変更しないでください。
- README.md / API_SPEC.md / memo.md / TASK.md は変更しないでください。
- OSM / Overpass API 接続は行わないでください。
- 外部API、キャッシュ、地物取得の実装は行わないでください。
- 既存の採点API、共有API、削除API、demo UI は変更しないでください。
- 実装後の報告は短くしてください。

## 作業前に読むファイル

まず、次のファイルだけを確認してください。

- `AGENTS.md`
- `RULES.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `maps/tests.py`

必要がある場合のみ、次を確認してください。

- `API_SPEC.md`
- `README.md`

今回は、以下のファイルは原則として読まなくてよいです。

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `memo.md`

## 背景

現在、MapArea作成時に `region_feature_level` を指定できるようになっています。

`region_feature_level` は、GridCell生成時の `initial_score` / `calculated_score` に反映されます。

現在の意味は以下です。

```text
0: 初期値
1: ありふれた地域
2: 普通の地域
3: 特徴的な地域
```

また、将来的な自動判定に向けて、以下の土台が入っています。

- `calculate_initial_score_from_feature_summary()`
- `determine_initial_score_for_grid_cell()`
- `build_grid_cell_contexts_for_area()`
- `build_feature_summary_for_grid_cell()`
- `build_feature_summaries_for_grid_cell_contexts()`
- `generate_grid_cells_for_area(..., feature_summaries_by_position=...)`

ただし、現時点では OSM / Overpass API 連携は未実装です。

今回追加する `initial_score_mode` は、MapArea作成時に **GridCellの初期点数をどう決めるか** を表す値です。

## 今回の目的

MapArea に `initial_score_mode` を追加し、MapArea作成APIで以下の2値を受け取れるようにします。

```text
manual
auto
```

### manual

`manual` は、現在の既存挙動です。

```text
region_feature_level を使って GridCell.initial_score / calculated_score を決める
```

### auto

`auto` は、将来の自動判定モードです。

ただし、現時点では OSM / Overpass API が未実装のため、`auto` を指定しても外部API接続は行いません。

今回の `auto` の挙動は以下です。

```text
initial_score_mode = auto
↓
外部API接続は行わない
↓
feature_summary 自動生成はまだ行わない
↓
region_feature_level を fallback として使う
↓
GridCell.initial_score / calculated_score に region_feature_level が入る
```

つまり、現時点では `manual` と `auto` の GridCell生成結果は同じで構いません。

ただし、MapArea には `initial_score_mode = "auto"` を保存してください。

## 重要な設計方針

### 1. initial_score_mode はDBに保存する

MapArea に `initial_score_mode` を保存してください。

理由:

```text
- あとからMapAreaを見たときに、初期点数を手動設定で作ったのか自動設定で作ろうとしたのか分かる
- 将来OSM自動判定を追加したとき、auto選択済みMapAreaを再計算対象にできる
- demoやAPIレスポンスでも状態を確認しやすい
```

### 2. initial_score_mode の選択肢

`initial_score_mode` は以下のみ許可してください。

```text
manual
auto
```

未指定時は `manual` にしてください。

### 3. region_feature_level は残す

`region_feature_level` は削除しないでください。

役割:

```text
manual:
- GridCell.initial_score の元になる値

auto:
- 自動判定失敗時、または現時点の未実装期間中の fallback 値
```

### 4. autoでも外部API接続しない

今回は以下を行わないでください。

```text
- OSM / Overpass API 接続
- 地物取得
- feature_summary 自動生成
- キャッシュ
- 自動判定の本接続
```

### 5. initial_score はユーザーがGridCellごとに直接編集しない

今回も `initial_score` をユーザーがGridCellごとに直接編集できる設計にはしないでください。

## 今回やること

- `MapArea` モデルに `initial_score_mode` を追加する
- `initial_score_mode` は `manual` / `auto` の文字列として扱う
- default は `manual` にする
- migration を作成する
- 既存データには `manual` が入るようにする
- `MapAreaSerializer` で `initial_score_mode` を受け取れるようにする
- 未指定時は `manual` にする
- `manual` / `auto` 以外は validation error にする
- MapArea作成レスポンスに `initial_score_mode` を含める
- MapArea詳細・一覧レスポンスに `initial_score_mode` が含まれるようにする
  - serializerを共通利用している場合は自然に含まれればよい
- MapArea作成APIで `initial_score_mode=manual` を保存できるようにする
- MapArea作成APIで `initial_score_mode=auto` を保存できるようにする
- `auto` の場合でも、現時点では `region_feature_level` fallback により GridCell の `initial_score` / `calculated_score` が設定されるようにする
- 既存テストを更新する
- 必要な新規テストを追加する

## 今回やらないこと

- demoページ変更
- README.md 更新
- API_SPEC.md 更新
- memo.md 更新
- OSM / Overpass API 接続
- 外部API接続
- 外部APIキー管理
- 地物取得
- キャッシュ設計の実装
- feature_summary 自動生成の本接続
- `initial_score_source` の追加
- `initial_score` のGridCell単位手動編集機能
- `calculated_score` の計算式変更
- 既存のユーザー採点API仕様変更

## 変更してよいファイル

- `maps/models.py`
- `maps/serializers.py`
- `maps/views.py`
- `maps/services.py`
- `maps/tests.py`
- `maps/migrations/*.py`

必要がない場合、`views.py` / `services.py` は変更しなくても構いません。

## 変更しないファイル

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`
- `README.md`
- `API_SPEC.md`
- `memo.md`
- `TASK.md`
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`

## 実装方針

### 1. MapAreaモデルに initial_score_mode を追加する

`MapArea` に `initial_score_mode` を追加してください。

想定:

```python
class InitialScoreMode(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTO = "auto", "Auto"

initial_score_mode = models.CharField(
    max_length=20,
    choices=InitialScoreMode.choices,
    default=InitialScoreMode.MANUAL,
)
```

既存コードの命名方針に合わせて、別の実装でも構いません。

ただし、API上の値は必ず以下にしてください。

```text
manual
auto
```

### 2. migrationを作成する

`initial_score_mode` 追加用の migration を作成してください。

既存のMapAreaには `manual` が入るようにしてください。

### 3. Serializerで initial_score_mode を扱う

`MapAreaSerializer` で `initial_score_mode` を受け取れるようにしてください。

仕様:

```text
- 作成時に指定可能
- 未指定時は manual
- manual / auto のみ許可
- レスポンスにも含める
```

不正値の例:

```text
"invalid"
""
null
1
true
```

これらは validation error にしてください。

### 4. MapArea作成Viewとの接続

MapArea作成時に `initial_score_mode` が保存されるようにしてください。

`manual` の場合:

```text
region_feature_level を使って GridCell.initial_score / calculated_score を設定
```

`auto` の場合:

```text
現時点では OSM未実装のため、region_feature_level を fallback として使う
```

つまり、今回の時点では `generate_grid_cells_for_area()` に `feature_summaries_by_position` を渡さなくて構いません。

既存の `generate_grid_cells_for_area()` の fallback 動作でよいです。

### 5. auto時の挙動

今回の `auto` は、あくまで「ユーザーが自動設定を選んだ意図を保存する」ためのものです。

そのため、今回の時点では以下で構いません。

```text
initial_score_mode=auto
region_feature_level=2
↓
MapArea.initial_score_mode = auto
MapArea.region_feature_level = 2
GridCell.initial_score = 2.0
GridCell.calculated_score = 2.0
```

外部API接続や feature_summary 生成は行わないでください。

## テスト方針

既存テストを更新し、必要な新規テストを追加してください。

### 1. Model / Serializer 系

以下を確認してください。

```text
- MapArea.initial_score_mode のデフォルトが manual
- MapAreaSerializer が initial_score_mode を受け取れる
- 未指定時は manual になる
- manual は valid
- auto は valid
- invalid は invalid
- 空文字は invalid
- null は invalid
- serializer data に initial_score_mode が含まれる
```

### 2. MapArea作成API系

以下を確認してください。

```text
- initial_score_mode=manual でMapAreaを作成できる
- response に initial_score_mode=manual が含まれる
- DB上の MapArea.initial_score_mode が manual になる
- initial_score_mode=auto でMapAreaを作成できる
- response に initial_score_mode=auto が含まれる
- DB上の MapArea.initial_score_mode が auto になる
- initial_score_mode=auto でも、現時点では region_feature_level fallback により GridCell.initial_score が設定される
- initial_score_mode=auto でも GridCell.calculated_score が initial_score と同じになる
- initial_score_mode 不正値では 400 Bad Request になる
- 不正値の場合 MapArea / GridCell は作成されない
```

### 3. 既存テストの更新

MapAreaレスポンスのフィールドを厳密に確認しているテストがあれば、`initial_score_mode` を追加してください。

既存payloadに `initial_score_mode` を必ず追加する必要はありません。

未指定時 default `manual` の挙動も確認したいため、既存payloadは基本そのままで構いません。

新規テストで `initial_score_mode=auto` を明示してください。

## 確認コマンド

作業後、次を実行してください。

```bash
source .venv/bin/activate
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test maps
git diff --check -- maps/models.py maps/serializers.py maps/views.py maps/services.py maps/tests.py maps/migrations
```

注意:

今回のタスクでは migration 追加が必要です。  
作業途中では以下を実行して migration を作成してください。

```bash
source .venv/bin/activate
python manage.py makemigrations maps
python manage.py migrate
python manage.py test maps
```

migration作成後に、最終確認として `makemigrations --check --dry-run` が通る状態にしてください。

## 手動確認方針

可能であれば、API client または curl で以下も確認してください。

### manual

```json
{
  "name": "Manual Mode Area",
  "center_lat": 35.695,
  "center_lng": 139.795,
  "grid_size_meters": 500,
  "rows": 6,
  "cols": 8,
  "region_feature_level": 2,
  "initial_score_mode": "manual",
  "source": "manual"
}
```

期待:

```text
MapArea.initial_score_mode = manual
GridCell.initial_score = 2.0
GridCell.calculated_score = 2.0
```

### auto

```json
{
  "name": "Auto Mode Area",
  "center_lat": 35.695,
  "center_lng": 139.795,
  "grid_size_meters": 500,
  "rows": 6,
  "cols": 8,
  "region_feature_level": 2,
  "initial_score_mode": "auto",
  "source": "manual"
}
```

期待:

```text
MapArea.initial_score_mode = auto
現時点ではOSM未実装のため、
GridCell.initial_score = 2.0
GridCell.calculated_score = 2.0
```

## 注意事項

- `initial_score_mode` はDBに保存してください。
- default は `manual` にしてください。
- API上の値は `manual` / `auto` の2つにしてください。
- `auto` でも、今回は外部API接続を行わないでください。
- `auto` でも、今回は `region_feature_level` fallback でGridCellを生成してください。
- `region_feature_level` は削除・変更しないでください。
- `initial_score` をユーザーがGridCellごとに直接編集できる設計にはしないでください。
- `calculated_score` の既存計算式は変更しないでください。
- demoページは変更しないでください。
- README.md / API_SPEC.md / memo.md は変更しないでください。
- MapArea作成とGridCell生成のtransaction方針は維持してください。
- レート制限節約のため、必要最小限のファイルだけを確認・変更してください。
- 実装後の報告は、変更点と実行した確認コマンドだけを短くまとめてください。