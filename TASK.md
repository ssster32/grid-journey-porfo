# 現在のタスク

Map Preview 上に GridCell 境界を薄く表示する

# 目的

demo ページの `Map Preview` に、選択中メモグリッドの `GridCell` 境界を薄い線で重ねて表示する。

これにより、`Score Map` に表示されているマスが、実際の地図範囲上ではどのように分割されているかを確認しやすくする。

# 作業範囲

- `maps/static/maps/demo.js`
  - `GridCell` 一覧取得後、Leaflet 上に各 `GridCell` の境界を rectangle として表示する
  - メモグリッド切り替え時、古い GridCell 境界を削除する
  - `MapArea` の範囲 rectangle と `GridCell` 境界 rectangle を区別できるようにする
  - `GridCell` 境界は薄い線・低い透明度で表示する
  - `Score Map` の選択・採点処理は変更しない

- `maps/static/maps/demo.css`
  - 必要に応じて Map Preview の表示補助だけを追加する
  - 既存の Score Map 表示は崩さない

- `maps/tests.py`
  - demo ページに Map Preview / GridCell 境界表示に必要な要素や文言が含まれることを確認するテストを追加・更新する

- `README.md`
  - demo ページの手動確認手順に、Map Preview 上に GridCell 境界が薄く表示されることを短く追記する

- `memo.md`
  - 今回の作業内容、確認コマンド、次にやるとよいことを追記する

# 実装方針

- Leaflet の `L.rectangle()` を使って、各 `GridCell` の `south/west` から `north/east` までを矩形表示する
- `MapArea` 全体の矩形はこれまで通り少し目立つ線にする
- `GridCell` 境界は目立ちすぎないよう、細い線・薄い色・低い透明度にする
- `GridCell` の数が多い場合でも、まずは demo 用として単純に rectangle を並べる
- 境界表示の ON/OFF ボタンは今回は追加しない
- `GridCell` 境界は Map Preview の補助表示であり、採点操作は引き続き `Score Map` 側で行う

# 注意点

- `models.py` と migration は変更しない
- backend API は変更しない
- `views.py`, `serializers.py`, `urls.py`, `services.py` は変更しない
- `settings.py`, `requirements.txt` は変更しない
- Leaflet は既存の CDN 読み込みを使い、新しい依存関係は追加しない
- `Score Map` の既存機能を壊さない
- 既存の複数選択、ドラッグ選択、採点処理は変更しない
- CDN が読み込めない場合でも、demo ページ全体が JavaScript エラーで止まらないようにする

# 確認方法

以下を実行して確認する。

```bash
node --check maps/static/maps/demo.js
.venv/bin/python manage.py check
.venv/bin/python manage.py test maps.tests.MapDemoViewTests
git diff --check -- maps/static/maps/demo.html maps/static/maps/demo.js maps/static/maps/demo.css maps/tests.py README.md memo.md
```

可能であれば、追加で以下も実行する。

```bash
.venv/bin/python manage.py test maps
```

ブラウザで確認する内容:

1. demo ページを開く
2. メモグリッドを作成、または既存のメモグリッドを選択する
3. `Map Preview` に選択中メモグリッドの範囲が表示される
4. `Map Preview` 上に `GridCell` 境界が薄く表示される
5. `Score Map` の表示、選択、採点がこれまで通り動く
6. 別のメモグリッドに切り替えた時、古い GridCell 境界が残らない