# TASK: API_SPEC.md に現在のAPI仕様を反映・更新する

## 目的

提出前に、`API_SPEC.md` を現在の実装内容に合わせて更新する。

`README.md` は作品全体の説明として整理済みなので、`API_SPEC.md` では **API仕様・レスポンス項目・認証・権限制御・注意点** を中心に整理する。

ただし提出直前のため、**API_SPEC.md の更新のみ** にする。
コード・設定・画面実装・README・memo.md は変更しない。

## 対象ファイル

変更対象:

* `API_SPEC.md`

参考にしてよいファイル:

* `README.md`
* `memo.md`
* `maps/urls.py`
* `maps/page_urls.py`
* `maps/views.py`
* `maps/serializers.py`
* `maps/models.py`
* `maps/services.py`
* `maps/static/maps/js/grid-create.js`
* `maps/static/maps/js/grid-detail.js`
* `maps/static/maps/js/grid-detail-api.js`
* `maps/static/maps/js/grid-list.js`

## 更新方針

* 既存の `API_SPEC.md` の構成を確認し、現在の実装に合わせて更新する
* 古い仕様が残っている場合は、現在の仕様に合わせて修正する
* API仕様書として読みやすいように、エンドポイントごとに整理する
* 画面UIの詳細説明は書きすぎず、APIに関係する内容を中心にする
* READMEと重複しすぎないようにする
* 未実装の内容を実装済みとして書かない
* 変更対象は `API_SPEC.md` のみ

## 反映したい主な内容

### 1. 認証方式

現在の仕様に合わせて整理する。

含めたい内容:

* APIは認証が必要
* 本サイト画面ではDjangoログイン + Session + CSRFを使う
* API手動確認用として Token認証にも対応している
* Basic認証も既存テスト上は利用可能
* POST / DELETE ではCSRFが必要になる場面がある
* 作成者本人または共有されたユーザーだけが対象メモグリッドにアクセスできる
* 共有相手管理と削除は作成者のみ

### 2. APIエンドポイント一覧

`maps/urls.py` の現在の内容に合わせて整理する。

代表例:

```text
POST /api-token-auth/
GET  /api/maps/areas/
POST /api/maps/areas/
GET  /api/maps/areas/<area_id>/
DELETE /api/maps/areas/<area_id>/
GET  /api/maps/areas/<area_id>/shares/
POST /api/maps/areas/<area_id>/shares/
DELETE /api/maps/areas/<area_id>/shares/<share_id>/
GET  /api/maps/areas/<area_id>/grids/
POST /api/maps/grids/<grid_id>/ratings/
POST /api/maps/grids/bulk-ratings/
```

注意:

* 実装に存在しないエンドポイントは書かない
* URL文字列・HTTP method・nameは変更しない
* `areas/<area_id>/grids/` に `grid-cell-list` と `grid-cell-generate` の両方のnameがある場合でも、実際の利用仕様としてはGridCell取得APIとして整理する
* ページURL `/maps/` などは、API仕様の主役ではないため、必要なら「画面URL」欄に簡単に書く程度にする

### 3. MapArea 作成API

`POST /api/maps/areas/` を現在の仕様に合わせる。

現在の作成入力:

* `name`
* `description`
* `center_lat`
* `center_lng`
* `grid_size_meters`
* `rows`
* `cols`
* `initial_score_mode`
* `region_feature_level`

注意:

* `source` は現在作成画面の主要入力欄から削除済み
* APIとして残っている可能性がある場合は、現在のserializer仕様に合わせて「任意」または「内部的に残る項目」として整理する
* 旧仕様の `north` / `south` / `east` / `west` 直接指定は現在の作成APIでは使わない
* 中心座標方式を基本として書く
* `rows` / `cols` で縦横マス数を指定する
* 作成時にGridCellも生成される

### 4. initial_score_mode / region_feature_level

現在の仕様に合わせて明記する。

含めたい内容:

```text
initial_score_mode:
- manual
- auto

region_feature_level:
- 0: 初期値
- 1: ありふれた地域
- 2: 普通の地域
- 3: 特徴的な地域
```

補足:

* 手動設定では `region_feature_level` が初期スコアとして使われる
* 自動設定ではOSM/Overpassから特徴を取得し、自動初期スコアを計算する
* 画面上では「自動設定」を選ぶと `initial_score_mode="auto"`、`region_feature_level=0` として送信する
* 自動設定時の地域特徴レベル表示は画面では `-` と表示しているが、API値としては `region_feature_level` を持つ

### 5. 自動設定時の注意・制限

API_SPEC.md にも簡潔に反映する。

含めたい内容:

* 自動設定はOSM/Overpass API取得を伴う
* 都市部や広範囲では処理が重くなりやすい
* 画面側では自動設定時のみ、1辺が `2000m以上` の作成をAPI送信前に制限している
* 手動設定ではこの画面側制限はかけていない
* API側に同じ制限があるかどうかは、実装に合わせて正確に書く
* READMEと同じく、都市部の自動設定は1辺1.5km以内が安定しやすい目安として書いてよい

### 6. MapArea レスポンス

現在のレスポンスに含まれる項目を整理する。

含めたい候補:

* `id`
* `name`
* `description`
* `north`
* `south`
* `east`
* `west`
* `grid_size_meters`
* `region_feature_level`
* `initial_score_mode`
* `source`
* `created_by`
* `created_at`
* `updated_at`
* 一覧用の追加情報がある場合:

  * 作成者情報
  * 共有メモグリッド判定
  * `map_grid_rows`
  * `map_grid_cols`

実装に合わせて正確に書くこと。

### 7. GridCell 一覧API

`GET /api/maps/areas/<area_id>/grids/` を現在仕様に合わせる。

レスポンスに含める項目候補:

* `id`
* `area`
* `row_index`
* `col_index`
* `north`
* `south`
* `east`
* `west`
* `initial_score`
* `auto_score_breakdown`
* `average_user_score`
* `rating_count`
* `calculated_score`
* `score_updated_at`
* `current_user_has_rating`
* `current_user_comment`
* `created_at`
* `updated_at`

補足:

* `calculated_score` が画面上の表示スコアとして使われる
* `average_user_score` はユーザー採点だけの平均
* `rating_count` はユーザー採点数
* `current_user_has_rating` はログインユーザーがそのGridCellを採点済みかどうか
* `current_user_comment` はログインユーザーのコメント表示に使う

### 8. auto_score_breakdown

現在の自動採点理由表示に合わせて整理する。

含めたい内容:

* 自動設定時に、GridCellごとの自動採点内訳として保存される
* 詳細画面の「自動採点理由」に使う
* 主な項目:

  * `base_score`
  * `diversity_bonus`
  * `context_bonus`
  * `penalty`
  * `raw_score`
  * `clamped_score`
  * `grid_size_multiplier`
  * `flags`
  * `bonuses`
  * `counts`
* `grid_size_multiplier` はマスサイズ補正係数
* 自動採点では最終的に0.0〜3.0へclampする
* 自動設定でない場合や自動特徴がない場合は `null` になる可能性がある

### 9. 表示スコア計算

API_SPEC.md に現在の計算仕様を反映する。

```text
calculated_score = (initial_score + 全ユーザー採点の合計) / (1 + rating_count)
```

説明:

* `initial_score` を最初の1票として扱う
* ユーザー採点が増えるほど初期スコアの影響が自然に薄まる
* `average_user_score` はユーザー採点だけの平均
* `rating_count` はユーザー採点数
* 採点がない場合は `calculated_score = initial_score`

### 10. 採点API

`POST /api/maps/grids/<grid_id>/ratings/`

整理する内容:

* 対象GridCellに対して、ログインユーザーの採点を作成または更新する
* `score` は 1〜10
* `comment` は任意
* 同じユーザーが同じGridCellへ複数回採点した場合は、既存採点を更新する仕様ならそのように書く
* 採点後に対象GridCellのスコア集計が更新される

リクエスト例:

```json
{
  "score": 8,
  "comment": "駅が近くて使いやすそう"
}
```

レスポンス項目は現在のserializerに合わせて書く。

### 11. 一括採点API

`POST /api/maps/grids/bulk-ratings/`

整理する内容:

* 複数GridCellに同じスコア・コメントをまとめて登録する
* `grid_ids`
* `score`
* `comment`
* `score` は 1〜10
* `grid_ids` は空不可
* 重複IDはserializer側で整理される場合、その仕様を正確に書く
* 権限のないGridCellには採点できない

リクエスト例:

```json
{
  "grid_ids": [1, 2, 3],
  "score": 7,
  "comment": "まとめて評価"
}
```

### 12. 共有API

対象:

```text
GET /api/maps/areas/<area_id>/shares/
POST /api/maps/areas/<area_id>/shares/
DELETE /api/maps/areas/<area_id>/shares/<share_id>/
```

整理する内容:

* 作成者のみ共有相手一覧を取得・追加・削除できる
* 共有相手は username で追加する仕様なら、そのように書く
* 同じユーザーへの重複共有はできない
* 共有されたユーザーは対象メモグリッドを閲覧・採点できる
* 共有されたユーザーは共有相手管理やメモグリッド削除はできない

### 13. 削除API

`DELETE /api/maps/areas/<area_id>/`

整理する内容:

* 作成者のみ削除可能
* 削除すると関連するGridCell、採点、共有設定も削除される
* 共有されたユーザーは削除できない

### 14. エラー・権限

必要に応じて整理する。

含めたい内容:

* 未認証時
* 権限なし
* 存在しないMapArea/GridCell
* validation error
* Overpass取得失敗時の扱い

  * 自動設定時にOverpass取得失敗した場合、フォールバックする仕様があるなら正確に書く
* 400 / 401 / 403 / 404 など、実装に合わせて書く

### 15. 画面URLとの関係

必要なら短く書く。

```text
画面URL:
- /login/
- /signup/
- /maps/
- /maps/new/
- /maps/<area_id>/
```

API仕様書なので、画面URLは補足程度でよい。

## 書き方の方針

* API仕様書として、エンドポイントごとに整理する
* リクエスト例・レスポンス例を必要な範囲で載せる
* 既存の内容がある場合は、現在の仕様に合わせて更新する
* 古い仕様やdemo中心の説明は、現在の本サイト/API仕様に合わせて整理する
* READMEと同じ説明を長く繰り返さない
* 不明な項目は実装ファイルを確認してから書く
* 推測で書かない

## やらないこと

* `API_SPEC.md` 以外の変更
* コード変更
* `README.md` の変更
* `memo.md` の変更
* model / migration の変更
* UI調整
* テスト修正
* demo.js / demo.css の変更
* デプロイ設定変更

## 注意

* 今回は `API_SPEC.md` のみ更新する
* コードや設定ファイルには触らない
* API URL・serializer・viewは変更しない
* 古い仕様が残っている場合は、現在の実装に合わせて文書だけ更新する
* `source` 入力欄は現在作成画面の主要入力ではないため、画面入力として強調しない
* 旧仕様の `north` / `south` / `east` / `west` 直接指定は現在の作成APIの基本仕様として書かない
* `center_lat` / `center_lng` / `rows` / `cols` を中心に書く
* 自動設定の範囲制限は、画面側制限かAPI側制限かを混同しない
* migrationに触らない
* 確認コマンドやテストコマンドは実行しないこと

## 作業後に報告してほしいこと

* 変更したファイル
* API_SPEC.md に追記・更新した主な内容
* 古い仕様を現在の仕様に合わせて直した箇所
* `API_SPEC.md` 以外を変更していないこと
* コード・README.md・memo.md・model・migration・demo.js / demo.css を変更していないこと
* 確認コマンドやテストコマンドを実行していないこと
