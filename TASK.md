# TASK.md 用プロンプト

## 現在のタスク

Score Map の表示範囲や縦横比を MapArea の緯度経度比に近づける

## 目的

demo ページの Score Map を、現在の単純な row/col ベースの表示から、MapArea の緯度経度範囲に少し近い見た目へ改善する。

今回は正確な地図投影や外部地図 API 連携は行わない。  
まずは `MapArea.north`, `south`, `east`, `west` の差分を使って、Score Map 全体の縦横比を MapArea の範囲に近づける。

## 作業範囲

- demo ページの Score Map 表示改善
- MapArea の緯度経度範囲を Score Map 表示に利用する
- CSS / JavaScript の必要最小限の更新
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

### 基本方針

- API レスポンス形式は変更しない。
- 既存の GridCell 一覧 API レスポンスに含まれている `area` 情報と `grids` 情報を使う。
- 現在の `GET /api/maps/areas/{area_id}/grids/` の `area` レスポンスに `north`, `south`, `east`, `west` が含まれていない場合は、追加で MapArea 詳細 API を呼ぶか、既に取得済みの MapArea 一覧の情報を保持して使う。
- 今回は demo ページ内の表示改善にとどめ、API 側の serializer や view は変更しない。

### 表示範囲・縦横比

- `MapArea.east - MapArea.west` を横方向の範囲として扱う。
- `MapArea.north - MapArea.south` を縦方向の範囲として扱う。
- Score Map の表示領域に、概算の縦横比を反映する。
- 例:

```text
width_ratio = east - west
height_ratio = north - south
aspect-ratio = width_ratio / height_ratio
```

- `height_ratio` が 0 以下、または不正値の場合は既存の固定表示に近い fallback を使う。
- 極端に細長くなりすぎる場合は、最小値・最大値で制限する。
  - 例: `aspect-ratio` を `0.6` から `2.2` 程度に収める
- 正確な地球測地計算は行わない。
- 経度 1 度あたりの距離が緯度で変わる問題は、今回は扱わない。

### GridCell の配置

- 既存の `row_index` / `col_index` による CSS Grid 配置は維持してよい。
- Score Map 全体の縦横比だけを MapArea の緯度経度比に近づける。
- 各 GridCell の正確な緯度経度座標による pixel 配置は今回は行わない。
- 今回は「地図っぽい縦横比に近づける」段階とする。

### UI 表示

- Score Map の近くに、確認用として MapArea の縦横比が反映されていることが分かる短い表示を追加してよい。
- ただし、UI が説明文だらけにならないようにする。
- 例:
  - `area ratio 1.25`
  - `area bounds based`
- score 値が主役である状態は維持する。
- GridCell ID と row/col は引き続き小さく表示する。

## JavaScript 方針

- MapArea 一覧取得時、各 MapArea の `north`, `south`, `east`, `west` を保持できるようにする。
- 選択中 MapArea の bounds を `state` に保持する。
- Score Map 描画時に、選択中 MapArea の bounds から概算 `aspect-ratio` を計算する。
- CSS custom property などを使って Score Map の表示領域に反映する。
- 不正値や未取得時は fallback を使う。

例:

```js
function mapAreaAspectRatio(area) {
  const width = Number(area.east) - Number(area.west);
  const height = Number(area.north) - Number(area.south);

  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return 1.4;
  }

  return Math.min(Math.max(width / height, 0.6), 2.2);
}
```

## CSS 方針

- `.score-map-stage` または適切な外側要素に `aspect-ratio` を設定する。
- 既存の一枚の地図状の四角表示は維持する。
- `min-height` / `max-height` / `aspect-ratio` のバランスを調整し、極端な表示崩れを防ぐ。
- モバイル幅でも Score Map が潰れすぎないようにする。
- セル間の `gap: 0` は維持する。

## テスト方針

以下を確認するテストを追加・更新する。

- demo ページが `200 OK` で表示される
- demo ページに `Score Map` が表示される
- demo ページに将来の地図背景用 class が存在する
- demo ページに縦横比反映用の class または表示要素が存在する
- demo ページに `GridCell を再取得` が表示される
- demo ページに `GridCell を自動生成` が表示されない

JavaScript の構文チェックも行う。

```bash
node --check maps/static/maps/demo.js
```

## README 更新方針

README.md の demo ページ説明に、以下を短く反映する。

- Score Map の表示領域は MapArea の緯度経度範囲から概算した縦横比に近づける
- 正確な地図投影ではない
- 外部地図 API や地図画像はまだ使っていない
- row/col による簡易グリッド配置は維持している

## API_SPEC 更新方針

API 仕様自体は変えない。  
必要であれば、表示方針メモとして以下だけ追記する。

- demo ページでは、MapArea の `north`, `south`, `east`, `west` を使って Score Map の概算縦横比を決める
- 正確な地図投影や地図背景表示は今後の別タスク
- API レスポンス形式は変更しない

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
- `maps/views.py`、`maps/serializers.py`、`maps/services.py` は変更しないでください。
- 外部地図 API や新しいライブラリは追加しないでください。
- 今回は正確な地図投影を実装しないでください。
- 今回は地図の取得・表示を実装しないでください。
- GridCell の生成・採点ロジックは変更しないでください。
- 既存テストを削除して通す対応はしないでください。