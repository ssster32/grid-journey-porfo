# TASK: 管理者限定pending処理画面についてREADMEに追記する

## 目的

現在、`initial_score_mode=auto` の MapArea 作成では、GridCell生成を即時実行せず、`grid_generation_status=pending` で保留する。

Render無料環境では Shell や Cron Job の利用が難しい場合があるため、代替手段として **管理者限定で pending MapArea を1件処理する画面** を追加済み。

今回は、この運用方法を `README.md` に追記し、アプリの利用・運用手順として分かるようにする。

## 今回のタスク範囲

実施する:

```text
- README.md に管理者限定pending処理画面の説明を追記する
- auto作成後にpendingになることを簡潔に説明する
- 管理者画面からpendingを1件処理できることを説明する
- staffユーザー限定であることを明記する
- Render無料環境での運用補助としての位置づけを説明する
- 必要なら既存のREADME記述との矛盾を修正する
```

実施しない:

```text
- Pythonコード変更
- model / migration変更
- serializer変更
- views変更
- URL変更
- template変更
- CSS変更
- JavaScript変更
- tests変更
- memo.md変更
- API_SPEC.md変更
- Render設定変更
- render.yaml追加
```

## 対象ファイル

変更対象:

* `README.md`

確認対象:

* `memo.md`
* `API_SPEC.md`
* `maps/views.py`
* `maps/page_urls.py`
* `maps/templates/maps/pending_grid_jobs.html`

今回は変更しない:

* Pythonコード
* tests
* API_SPEC.md
* memo.md
* render.yaml

## READMEに追記する内容

既存READMEの構成に合わせて、自然な場所に追記する。

候補見出し:

```markdown
## 管理者向け: pendingメモグリッドの手動処理
```

または既存の運用・デプロイ・補足セクションに合わせる。

## 書く内容

### 1. auto作成時のpending化

以下を簡潔に説明する。

```text
自動初期スコア設定を選んでメモグリッドを作成した場合、Overpass APIへの問い合わせに時間がかかるため、GridCell生成を即時実行せず pending 状態で作成する。
```

説明例:

```markdown
自動設定でメモグリッドを作成した場合、作成直後は `grid_generation_status=pending` になり、GridCellはまだ生成されていない場合があります。
```

### 2. 管理者限定処理画面

以下を明記する。

```text
- URL: /maps/admin/pending-grid-jobs/
- staffユーザーのみアクセス可能
- pending MapAreaを古い順に1件だけ処理する
- 処理結果は completed / fallback_completed / failed のいずれかになる
```

説明例:

```markdown
staff権限を持つ管理者は、以下の画面から pending 状態のメモグリッドを1件ずつ処理できます。

`/maps/admin/pending-grid-jobs/`
```

### 3. 画面でできること

以下を整理する。

```text
- pending件数の確認
- 次に処理されるMapAreaの確認
- ボタンによる1件処理
- 処理結果の確認
```

### 4. 注意点

以下を明記する。

```text
- Overpass APIへ問い合わせるため、処理に時間がかかる場合がある
- 連続実行は避ける
- 一般ユーザーは実行できない
- failed / fallback_completed の再処理は対象外
- Render Cron JobやCelery/RQ/Redisの代替としての簡易運用
```

説明例:

```markdown
この処理はOverpass APIへ問い合わせるため、10〜20秒程度かかる場合があります。短時間に連続して実行しないでください。
```

### 5. management commandとの関係

既にREADME内にコマンド説明がある場合は、以下を補足する。

```bash
python manage.py process_pending_grid_areas --limit 1
```

説明:

```text
ローカルやShellが使える環境では management command で処理できる。
Render無料環境などでShellやCron Jobが使いにくい場合は、管理者限定画面から手動処理できる。
```

### 6. Render無料環境での位置づけ

以下のように書く。

```text
Render無料環境ではShellやCron Jobが使いにくい場合があるため、管理者限定画面を使って必要な時にpendingを1件ずつ処理する。
```

ただし、Renderの料金やプランについて断定しすぎない。

避ける表現:

```text
Render無料プランでは絶対にCron Jobが使えない
```

推奨表現:

```text
Render無料環境ではShellやCron Jobの利用が難しい場合があるため
```

## README追記例

既存READMEに合わせて調整してよいが、以下のような内容をベースにする。

````markdown
## 管理者向け: pendingメモグリッドの手動処理

自動設定でメモグリッドを作成した場合、Overpass APIへの問い合わせに時間がかかるため、作成直後は `grid_generation_status=pending` になり、GridCellがまだ生成されていない場合があります。

pending状態のメモグリッドは、staff権限を持つ管理者が以下の画面から1件ずつ処理できます。

```text
/maps/admin/pending-grid-jobs/
````

この画面では、現在のpending件数と次に処理されるMapAreaを確認できます。
「pendingを1件処理する」ボタンを押すと、古いpending MapAreaを1件だけ処理します。

処理後の状態は以下のいずれかになります。

* `completed`: 自動初期スコア設定によるGridCell生成が完了
* `fallback_completed`: Overpass API取得に失敗したが、標準値でGridCell生成が完了
* `failed`: GridCell生成に失敗

この処理はOverpass APIへ問い合わせるため、10〜20秒程度かかる場合があります。短時間に連続して実行しないでください。

ローカルやShellが使える環境では、以下のmanagement commandでも同じpending処理を実行できます。

```bash
python manage.py process_pending_grid_areas --limit 1
```

Render無料環境など、ShellやCron Jobの利用が難しい場合は、管理者限定画面を使って必要な時に1件ずつ処理します。

````

注意: 上のMarkdown例にはコードブロックが含まれるため、READMEへ貼る際にバッククオートの入れ子が崩れないように調整すること。

## やってよい変更

```text
- README.mdへの説明追記
- README内の既存記述との矛盾修正
- 文言の軽微な整理
````

## やってはいけない変更

```text
- Pythonコードを変更する
- testsを変更する
- API_SPEC.mdを変更する
- memo.mdを変更する
- render.yamlを変更する
- URLやテンプレートを変更する
- CSS/JSを変更する
- 新しい機能を追加する
```

## 確認

確認コマンドやテストコマンドは実行しない。

文書更新のみなので、作業後は以下の差分確認だけでよい。

```bash
git diff -- README.md
rg -n "pending|pending-grid-jobs|process_pending_grid_areas|Overpass|staff|fallback_completed" README.md
git diff --name-only
```

## 作業後に報告してほしいこと

以下を報告する。

```text
- 変更したファイル
- README.md に追記した見出し
- 管理者限定画面のURLを明記したか
- staffユーザー限定であることを明記したか
- pendingを1件ずつ処理することを明記したか
- completed / fallback_completed / failed の説明を入れたか
- Overpass APIへの問い合わせで時間がかかる可能性を明記したか
- Render無料環境での位置づけを断定しすぎずに説明したか
- Pythonコード / tests / API_SPEC.md / memo.md / render.yaml を変更していないこと
- 確認コマンドやテストコマンドを実行したかどうか
  - 実行していない場合は「実行していない」と明記する
```
