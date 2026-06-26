# Grid Journey

Grid Journey は、地図上の任意の範囲をグリッド状に分割し、各マスに対して初期スコア・ユーザー採点・コメントを記録できる Web アプリです。

OSM / Overpass API を使った自動初期スコア設定にも対応しており、建物、公園、川、水辺、森林、海岸、鉄道、駅、高速道路、観光名所などの地域特徴をもとにメモグリッドを作成できます。

画面上では、個人用の分割済み地図 `MapArea` を「メモグリッド」と表示します。

## URL / ID / パスワード
https://grid-journey-p.onrender.com/login/


## 主な機能

- ユーザー登録・ログイン
- メモグリッド一覧表示
- メモグリッド作成
  - 中心座標
  - 説明
  - 1マスの大きさ
  - 縦横のマス数
  - 手動設定 / 自動設定
- 作成画面の地図プレビュー
  - 地図中央座標表示
  - 地図中央座標を入力欄へ反映
  - 中央位置を示すクロスヘア
  - `−` / `＋` / `入力座標へ戻す` のズーム操作
- 詳細画面の GridCell 表示
  - 地図上にマスを表示
  - スコア別の色表示
  - スコア数値ラベル
  - 採点済み表示
  - 色の濃さ調整
- 採点・コメント
  - 単体採点
  - Ctrl / Command クリックによる複数選択
  - Shift ドラッグによる範囲選択
  - 複数マスへの一括採点
- 自動初期スコア
  - OSM / Overpass API から地域特徴を取得
  - 各 GridCell ごとに特徴を集計
  - 自動採点理由を詳細画面で表示
- メモグリッド共有
  - 共有相手追加
  - 共有相手削除
  - 共有されたメモグリッドの閲覧・採点
- メモグリッド削除
  - 作成者のみ削除可能

## 画面構成

- `/login/`: ログイン
- `/signup/`: 新規ユーザー登録
- `/maps/`: メモグリッド一覧
- `/maps/new/`: メモグリッド作成
- `/maps/<area_id>/`: メモグリッド詳細
- `/api/maps/`: メモグリッド関連 API
- `/api/auth/token/`: Token 認証用 API

トップページ `/` は、現在 `/maps/` へリダイレクトします。

## 使い方

1. `/signup/` でユーザー登録する。
2. `/login/` でログインする。
3. `/maps/new/` でメモグリッドを作成する。
4. 作成画面の地図プレビューを見ながら、中心座標・マス数・1マスの大きさを調整する。
5. 手動設定または自動設定を選んで、メモグリッドを作成する。
6. `/maps/<area_id>/` の地図上でマスを選択する。
7. 選択したマスにスコアとコメントを記録する。
8. 必要に応じて、共有相手を追加する。

作成フォームが縦に長く、通常の作成ボタンが画面内に見えていない場合は、下部固定の `メモグリッドを作成` ボタンを表示します。
固定ボタンも既存フォームの submit を使うため、作成処理は二重管理していません。

## 自動初期スコア

自動設定では、OSM / Overpass API から地物情報を取得し、各 GridCell ごとに地域特徴を集計します。

スコア計算では、主に次の要素を組み合わせます。

- `base_score`: 建物や道路など、マス自体の基本的な特徴
- `diversity_bonus`: 複数種類の特徴があることによる加点
- `context_bonus`: 周辺の駅、公園、水辺、観光名所などによる加点
- `penalty`: 水域中心、森林中心、建物・道路なしなどによる減点

最終的な初期スコアは `0.0〜3.0` に収めます。
大きいマスほど地物が多く入りやすく、自動スコアが上がりやすいため、`base_score` / `diversity_bonus` / `context_bonus` にはマスサイズ補正を入れています。
`penalty` にはこの補正をかけません。

また、大きすぎる river / expressway bounds による過検出を抑えるため、地物ごとの判定条件も調整しています。
詳細画面では、保存された `auto_score_breakdown` から主な自動採点理由を確認できます。

負荷対策として、通常 road は自動初期スコアに使っていないため Overpass の広い取得対象から外しています。
ただし、高速道路相当の `motorway` / `trunk` 系は expressway として取得し、文脈要素に使います。

building はスコア傾向への影響が大きいため、完全除外は採用していません。
現在は building の中心点を使って `building_count` に反映する軽量な方式をデフォルトにし、OSM データに bounds や center が欠ける building が混ざっても、その building だけを安全にスキップできるようにしています。

## 表示スコア計算

地図上の色分けやスコアラベルには `calculated_score` を使います。

表示スコアは、初期スコアを最初の1票として扱い、ユーザー採点と合わせて平均します。

```text
calculated_score = (initial_score + 全ユーザー採点の合計) / (1 + rating_count)
```

- `average_user_score`: ユーザー採点だけの平均
- `rating_count`: ユーザー採点数
- 採点がない場合: `calculated_score = initial_score`

ユーザー採点が増えるほど、初期スコアの影響が自然に薄まる設計です。

## 自動設定時の注意

自動設定は外部 API 取得とスコア計算を行うため、手動設定より時間がかかる場合があります。

特に都市部の広範囲では、地物数が多くなり処理が重くなることがあります。
現在は自動設定時のみ、1辺が `2000m以上` のメモグリッド作成を画面側で制限しています。
手動設定ではこの制限はかけていません。

安定利用の目安として、都市部の自動設定は 1 辺 1.5km 以内が扱いやすいです。

提出後の改善として、road 取得除外や building 処理の軽量化を行い、将来的に制限を緩和できるか検証しています。
ただし、Overpass API の混雑や取得時間のばらつきは残るため、現時点で 2km 制限を解除したわけではありません。

## 認証・権限

- 本サイト画面は Django のログイン機能を使います。
- 新規登録は Django 標準の `UserCreationForm` を使います。
- 独自 User model は使っていません。
- メモグリッドは、作成者本人と共有されたユーザーが閲覧できます。
- 共有されたユーザーは、共有メモグリッドを閲覧・採点できます。
- 共有相手管理とメモグリッド削除は作成者のみ可能です。
- API では Session 認証、Basic 認証、Token 認証を利用できます。

## UI 面の工夫

- 作成画面では、地図を見ながら中心座標を調整できます。
- クロスヘアで地図中央が分かるようにしています。
- 地図中央座標を `center_lat` / `center_lng` へ反映できます。
- 作成ボタンが画面外にある場合、下部固定ボタンを表示します。
- 詳細画面では、スコア分布を地図上の色で確認できます。
- スコア数値ラベルは背景をなくし、地図上で軽く読める形にしています。
- クリック、Ctrl / Command クリック、Shift ドラッグで GridCell を選択できます。
- 通常地図と拡大表示モーダルに `−` / `＋` / `範囲に戻す` のズーム操作を用意しています。
- 一覧画面では、通常メモグリッドと共有メモグリッドを視覚的に区別しています。

## 技術構成

- Python
- Django
- Django REST Framework
- SQLite
- PostgreSQL 対応
- Leaflet
- OpenStreetMap
- Overpass API
- HTML / CSS / JavaScript
- WhiteNoise
- gunicorn
- Render 想定

ローカル開発では SQLite を使います。
`DATABASE_URL` が設定されている環境では、`dj-database-url` 経由で PostgreSQL などへ接続できます。

## セットアップ

職業訓練校の共用 Mac で使うことを想定しています。
Python パッケージはプロジェクト直下の `.venv` にだけ入れ、PC 本体の Python 環境はできるだけ汚さない構成にします。

### 前提

- Python 3.12 以上
- macOS のターミナル
- `pip` は必ず `.venv` のものを使う

現在の依存関係は Django 6 系を前提にしているため、Python 3.11 以下では動きません。

### 初回セットアップ

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install --upgrade pip
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt
python manage.py migrate
```

仮想環境が有効な間は、プロンプトの先頭に `(.venv)` が表示されます。

### 起動

```bash
source .venv/bin/activate
python manage.py runserver
```

ブラウザで次を開きます。

```text
http://127.0.0.1:8000/
```

## 開発時のコマンド

```bash
# 仮想環境を有効化
source .venv/bin/activate

# 依存関係をインストール
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt

# マイグレーション
python manage.py migrate

# 開発サーバー
python manage.py runserver

# Django の設定確認
python manage.py check

# 仮想環境を終了
deactivate
```

## API の手動確認

API の詳細な仕様は `API_SPEC.md` を参照します。
ここでは代表的な入口だけを示します。

### Token 発行

```bash
curl -i \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/auth/token/ \
  -d '{"username": "testuser", "password": "test-password"}'
```

### メモグリッド一覧

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  http://127.0.0.1:8000/api/maps/areas/
```

### GridCell 一覧

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  http://127.0.0.1:8000/api/maps/areas/<AREA_ID>/grids/
```

### 単体採点

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/<GRID_ID>/ratings/ \
  -d '{"score": 8, "comment": "水辺が近くて良さそう"}'
```

### 一括採点

```bash
curl -i \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/maps/grids/bulk-ratings/ \
  -d '{"grid_ids": [1, 2], "score": 5, "comment": "まとめて採点"}'
```

## コード整理

提出前に、`services.py` や主要 JavaScript ファイルへ、処理意図が分かるコメントを追加しました。

特に次のような、仕様の意図が伝わりにくい箇所を中心に整理しています。

- OSM / Overpass 取得
- 自動採点
- マスサイズ補正
- 表示スコア計算
- 地図操作
- 採点 UI
- 共有管理
- 削除処理

コメント追加は、ロジック変更ではなく保守性を上げるための整理です。

## 依存関係を追加したいとき

必ず `.venv` を有効化してからインストールします。

```bash
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install パッケージ名
python -m pip freeze > requirements.txt
```

`pip install` だけを直接使うと、別の Python に入ってしまうことがあります。
このプロジェクトでは `python -m pip ...` の形を推奨します。

## Git に入れないもの

以下は PC ごとに作られるため、Git 管理しません。

- `.venv/`
- `db.sqlite3`
- `.env`
- `__pycache__/`
- `.pip-cache/`
- `.DS_Store`

## 環境変数

通常のローカル開発では設定不要です。
端末ごとに値を変えたい場合は `.env.example` を参考に `.env` を作成し、ターミナルで読み込んでから Django を起動します。

```bash
cp .env.example .env
set -a
source .env
set +a
python manage.py runserver
```

主な環境変数:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`

## Codex で作業するとき

Codex には次の手順をセットアップとして伝えると安定します。

```bash
python3 -m venv .venv
source .venv/bin/activate
PIP_CACHE_DIR=.pip-cache python -m pip install --upgrade pip
PIP_CACHE_DIR=.pip-cache python -m pip install -r requirements.txt
python manage.py migrate
```

テストや管理コマンドを依頼するときも、`.venv` を使う前提で次の形にすると PC 本体の環境に依存しにくくなります。

```bash
source .venv/bin/activate
python manage.py check
```

## 設計メモ

- `TASK.md`: 現在の目標変更と作業メモ
- `API_SPEC.md`: 地図採点 API の仕様
- `memo.md`: 引き継ぎ用の作業メモ
- `AGENTS.md`: Codex に依頼するときの役割分担ルール
