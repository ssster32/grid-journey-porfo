# Codex タスク: MapArea 作成方式を中心座標 + グリッドサイズ + 行列数に変更するための設計を整理する

## 担当ロール

今回は **Architect** として作業してください。

このタスクでは、実装は行わず、設計整理だけを行ってください。

現在の MapArea 作成方式は、`north / south / east / west` の端の緯度経度を直接入力する方式です。  
しかし、ユーザー向けには分かりにくく、MapArea の範囲が `grid_size_meters` で割り切れない場合に、端の GridCell が半端なサイズになる問題があります。

そこで、今後は次のような作成方式に変更したいです。

```text
center_lat
center_lng
grid_size_meters
rows
cols
```

このタスクでは、その変更に向けて、影響範囲・設計方針・実装手順・テスト方針を整理してください。

## レート制限節約の方針

今回はレート制限節約を優先してください。

- いきなり実装しないでください。
- リポジトリ全体を広く読みすぎないでください。
- まず指定ファイルだけを確認してください。
- 必要以上に大きな差分を作らないでください。
- 不明点があっても、推測で実装に進まず、設計メモとして整理してください。
- 出力は長すぎないようにしてください。
- 次回実装タスクに使える形で、要点を整理してください。

## 作業前に読むファイル

まず、次のファイルだけを確認してください。

- `AGENTS.md`
- `RULES.md`
- `API_SPEC.md`
- `README.md`
- `TASK.md`
- `memo.md`
- `maps/models.py`
- `maps/serializers.py`
- `maps/services.py`
- `maps/views.py`
- `maps/tests.py`

必要がある場合のみ、次を追加で確認してください。

- `maps/static/maps/demo.html`
- `maps/static/maps/demo.js`
- `maps/static/maps/demo.css`

demo ページの詳細実装は、今回は深追いしないでください。

## 今回の目的

MapArea 作成方式を、現在の端座標指定から、中心座標指定へ移行するための設計を整理します。

現在の方式:

```json
{
  "name": "Demo Area",
  "north": 35.7,
  "south": 35.69,
  "east": 139.8,
  "west": 139.79,
  "grid_size_meters": 500
}
```

検討したい方式:

```json
{
  "name": "Demo Area",
  "center_lat": 35.695,
  "center_lng": 139.795,
  "grid_size_meters": 500,
  "rows": 6,
  "cols": 8
}
```

この方式では、サーバー側で `north / south / east / west` を計算し、MapArea と GridCell を生成します。

## 今回やること

次の内容を設計メモとして整理してください。

1. 現在の MapArea 作成処理の流れ
2. 現在の GridCell 生成処理の流れ
3. 中心座標方式に変更した場合の入力項目
4. 保存する model 項目を変更する必要があるか
5. 既存の `north / south / east / west` 方式を残すべきか
6. `center_lat / center_lng / rows / cols` を serializer でどう扱うか
7. `north / south / east / west` の計算方法
8. `rows / cols` を使って GridCell を生成する方法
9. 端の GridCell が半端にならないようにする方針
10. 既存 API との互換性
11. demo ページのフォーム変更方針
12. README / API_SPEC.md の更新方針
13. テスト追加・修正方針
14. 実装を小さく分ける場合のタスク分割案

## 今回やらないこと

- 実装
- model の変更
- serializer の変更
- service の変更
- view の変更
- migration の作成
- demo ページの変更
- README の大幅更新
- API_SPEC.md の大幅更新
- テストコードの変更
- Leaflet 表示の変更
- Score Map の変更

今回は、あくまで設計整理のみです。

## 設計時の前提

できれば、次の方針を優先してください。

### 1. MapArea model は当面そのまま維持する

既存の `MapArea` model には、現在どおり次を保存します。

```text
north
south
east
west
grid_size_meters
```

`center_lat / center_lng / rows / cols` は、まずは作成リクエスト用の入力値として扱い、保存項目として追加するかどうかは検討してください。

保存が必要な理由が弱い場合は、model 変更を避ける方針を優先してください。

### 2. 既存の north/south/east/west 方式は互換用に残す

既存の API やテストを壊しにくくするため、すぐに削除せず、当面は互換用として残す方針を検討してください。

理想は、作成 API が次の2方式を受け付ける形です。

```text
A. 従来方式: north / south / east / west / grid_size_meters
B. 新方式: center_lat / center_lng / grid_size_meters / rows / cols
```

ただし、両方が同時に指定された場合の扱いも設計してください。

例:

```text
両方指定された場合は 400 Bad Request にする
```

### 3. 中心座標方式では、MapArea の範囲を grid_size_meters の倍数にする

新方式では、MapArea の実サイズを次のように考えます。

```text
南北方向の長さ = grid_size_meters * rows
東西方向の長さ = grid_size_meters * cols
```

これにより、端の GridCell が半端なサイズにならないようにします。

### 4. 経度方向の距離補正を検討する

緯度方向は、おおまかに次の換算でよいです。

```text
1度 ≒ 111000m
```

経度方向は、緯度によって距離が変わるため、中心緯度を使って次の補正を検討してください。

```text
1度 ≒ 111000m * cos(center_lat)
```

ただし、現在の既存実装との整合性や、実装コストも考慮してください。

### 5. rows / cols のバリデーションを設計する

`rows` と `cols` は、正の整数にしてください。

検討する制限例:

```text
rows >= 1
cols >= 1
rows * cols が大きすぎる場合は 400 Bad Request
一般ユーザーは既存の 20分制限、または新しいセル数制限の対象
管理者は一部制限を緩和
```

既存の 20分制限と、新方式でのサイズ制限をどう整理するか検討してください。

## 出力してほしい内容

作業後、次の形式で設計メモを出力してください。

```markdown
# MapArea 作成方式変更 設計メモ

## 現状

- ...

## 課題

- ...

## 推奨方針

- ...

## 入力仕様案

### 従来方式

```json
{
  "north": 35.7,
  "south": 35.69,
  "east": 139.8,
  "west": 139.79,
  "grid_size_meters": 500
}
```

### 新方式

```json
{
  "center_lat": 35.695,
  "center_lng": 139.795,
  "grid_size_meters": 500,
  "rows": 6,
  "cols": 8
}
```

## north/south/east/west 計算方針

- ...

## GridCell 生成方針

- ...

## serializer 方針

- ...

## service 方針

- ...

## view 方針

- ...

## 既存 API 互換性

- ...

## demo ページ変更方針

- ...

## README / API_SPEC.md 更新方針

- ...

## テスト方針

- ...

## 実装タスク分割案

1. ...
2. ...
3. ...

## 注意点

- ...
```

## 実装タスク分割案に含めてほしい候補

最後に、次回以降の実装タスクとして、少なくとも次のように分割してください。

```text
1. center_lat / center_lng / rows / cols から MapArea 範囲を計算する helper を追加する
2. MapArea 作成 serializer で中心座標方式を受け付ける
3. GridCell 生成処理を rows / cols 方式に対応させる
4. API_SPEC.md と README を更新する
5. demo ページの MapArea 作成フォームを中心座標方式に変更する
6. 既存の north/south/east/west 方式を互換用として残すか、段階的に非推奨化する
```

## 確認方法

今回は設計整理のみなので、原則としてテスト実行は不要です。

ただし、ファイルを変更した場合は次を実行してください。

```bash
source .venv/bin/activate
python manage.py check
git diff --check
```

## 注意事項

- 今回は実装しないでください。
- 今回は設計整理だけにしてください。
- レート制限節約のため、読むファイルと出力を必要最小限にしてください。
- 既存の API / demo ページ / Leaflet / Score Map を変更しないでください。
- 既存の `north / south / east / west` 方式をすぐに消す前提にしないでください。
- model 変更や migration が本当に必要か慎重に検討してください。
- 初心者が後から読んでも、次に何を実装すればよいか分かるように整理してください。