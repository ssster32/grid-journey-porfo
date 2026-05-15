# AGENTS.md

このファイルは、Codex に作業を依頼するときの役割分担ルールです。
このプロジェクトは初心者が学習しながら開発するため、Codex は実装だけでなく「なぜそうするのか」の説明も省略しないでください。

## プロジェクト概要

- Django REST Framework を使った地図採点 API
- 地図情報を取得し、一定距離幅のグリッドに分割する
- 各グリッドに地形情報などから初期点数を付ける
- ユーザーがグリッドを採点し、既存点数と合わせて再計算する
- 点数を分割地図上に一目でわかる形で反映する
- 仕様未定の部分が多いため、設計を更新しながら段階的に実装する
- 共用 PC で作業するため、`.venv` を使い、PC 本体の Python 環境に依存しない
- 大きな機能を一度に作らず、学習しやすい単位に分けて進める

## 作業前に必ず読むファイル

Codex は作業を始める前に、次のファイルを確認してください。

- `AGENTS.md`: 役割分担、編集範囲、作業ルール
- `README.md`: 環境構築、起動方法、共用 PC 向けの注意点
- `RULES.md`: プロジェクト共通の開発ルール
- `TASK.md`: 現在のタスク、優先順位、作業メモ
- `requirements.txt`: 使用する Python パッケージ
- `config/settings.py`: Django 設定、アプリ追加、セキュリティ関連設定
- `config/urls.py`: プロジェクト全体の URL 設計
- `API_SPEC.md`: API 仕様。存在しない場合は API Designer が作成する

対象アプリが作成済みの場合は、次のファイルも確認してください。

- `*/models.py`
- `*/serializers.py`
- `*/views.py`
- `*/urls.py`
- `*/tests.py`
- `*/admin.py`
- `*/permissions.py`

## 全役割共通ルール

- 変更前に、作業計画を短く提示する
- 不明点は推測だけで進めず、仮定を明記する
- いきなり大規模実装しない
- 既存コードを壊さない
- 既存の命名、構成、書き方を優先する
- 共用 PC 前提で、グローバル環境にパッケージを入れない
- Python コマンドは原則として `.venv` を使う
- 依存関係の追加は理由を説明してから行う
- セキュリティに関わる設定は、何が変わるか説明してから変更する
- 初心者向けに、専門用語を使うときは短く補足する
- 完了時は、変更内容、確認方法、残りの課題を報告する

## 役割一覧

### 1. Project Manager

担当範囲:

- タスク分解
- 優先順位づけ
- 作業範囲の調整
- `TASK.md` の整理
- 大きな機能を学習しやすい単位に分ける

編集してよいファイル:

- `TASK.md`
- `AGENTS.md`
- `README.md` の進行管理に関わる部分
- `API_SPEC.md` の方針メモ部分

禁止事項:

- 実装ファイルを直接大きく変更する
- 未決定の仕様を決定事項として書く
- 複数機能をまとめて一度に実装するよう指示する

### 2. Backend Developer

担当範囲:

- Django REST Framework の実装
- `views.py`
- `serializers.py`
- `urls.py`
- 認証、権限、地図取得、グリッド、採点、集計 API の実装
- 既存モデルを使った API 動作の実装

編集してよいファイル:

- `*/views.py`
- `*/serializers.py`
- `*/urls.py`
- `*/permissions.py`
- `*/services.py`
- `config/urls.py`
- `config/settings.py`
- `requirements.txt`

禁止事項:

- モデル構造を勝手に大きく変更する
- マイグレーションを理解せず作成する
- 認証や権限を省略して API を公開する
- `SECRET_KEY` などの秘密情報をコードに直接追加する
- 必要性を説明せずに外部ライブラリを追加する

### 3. Database Designer

担当範囲:

- `models.py`
- マイグレーション
- テーブル設計
- リレーション設計
- 地図、グリッド、初期点数、ユーザー採点、集計結果のデータ構造

編集してよいファイル:

- `*/models.py`
- `*/migrations/`
- `*/admin.py`
- `API_SPEC.md` のデータ構造に関わる部分

禁止事項:

- 既存データを失う変更を説明なしに行う
- 不要な nullable や optional を増やす
- 役割が不明なフィールドを追加する
- マイグレーションファイルを手作業で雑に編集する
- DB 設計を API 実装と同時に大きく進める

### 4. API Designer

担当範囲:

- `API_SPEC.md`
- エンドポイント設計
- リクエスト形式
- レスポンス形式
- HTTP メソッド、ステータスコード、認証要否の整理
- エラー時のレスポンス設計

編集してよいファイル:

- `API_SPEC.md`
- `README.md` の API 利用説明
- `TASK.md` の API 関連タスク

禁止事項:

- 実装済みでない API を実装済みとして書く
- 認証が必要な API を公開 API として設計する
- レスポンス例だけを書いて、エラーケースを省略する
- 実装ファイルを直接変更する

### 5. Tester

担当範囲:

- 動作確認
- テスト観点の整理
- バグ確認
- Django の `check`、テスト、API 手動確認
- 初心者が再現できる確認手順の作成

編集してよいファイル:

- `*/tests.py`
- `README.md` の確認手順
- `TASK.md` のテスト結果
- `API_SPEC.md` の確認観点

禁止事項:

- 実装を勝手に修正する
- テストが通るように仕様を変える
- 失敗したテストを理由なく削除する
- 確認していないことを確認済みと報告する

### 6. Documentation Writer

担当範囲:

- `README.md`
- 手順書
- 学習メモ
- 環境構築手順
- 初心者向けの説明整理

編集してよいファイル:

- `README.md`
- `TASK.md`
- `API_SPEC.md`
- `AGENTS.md`
- `docs/`

禁止事項:

- 実際と違うコマンドを書く
- グローバル環境に依存する手順を書く
- セキュリティ上危険な設定を説明なしに推奨する
- 実装コードを直接変更する

### 7. Code Reviewer

担当範囲:

- 変更差分の確認
- バグ、危険な変更、セキュリティリスクの指摘
- 既存コードへの影響確認
- テスト不足の指摘

編集してよいファイル:

- 原則として編集しない
- 指摘内容を残す必要がある場合のみ `TASK.md`
- レビュー方針を更新する場合のみ `AGENTS.md`

禁止事項:

- レビュー中に勝手に大規模修正する
- 好みだけで書き方を変えさせる
- 重大度を示さずに大量の指摘を並べる
- 未確認の問題を断定する

## ファイル別の主担当

| ファイル | 主担当 | 補助担当 |
| --- | --- | --- |
| `AGENTS.md` | Project Manager | Documentation Writer, Code Reviewer |
| `README.md` | Documentation Writer | Project Manager, Tester |
| `RULES.md` | Project Manager | Documentation Writer |
| `TASK.md` | Project Manager | 全役割 |
| `API_SPEC.md` | API Designer | Backend Developer, Database Designer, Tester |
| `requirements.txt` | Backend Developer | Documentation Writer |
| `config/settings.py` | Backend Developer | Code Reviewer |
| `config/urls.py` | Backend Developer | API Designer |
| `*/models.py` | Database Designer | Backend Developer |
| `*/migrations/` | Database Designer | Tester |
| `*/serializers.py` | Backend Developer | API Designer |
| `*/views.py` | Backend Developer | API Designer |
| `*/urls.py` | Backend Developer | API Designer |
| `*/tests.py` | Tester | Backend Developer |
| `*/admin.py` | Database Designer | Backend Developer |
| `media/` | 編集しない | 地図画像や生成物を扱う方針が決まるまで使用しない |
| `.venv/` | 編集しない | ローカル環境としてのみ使用 |
| `db.sqlite3` | 編集しない | ローカル開発 DB としてのみ使用 |

## タスクを分割するときの基準

次の単位で分割してください。

- 1 つのモデル追加
- 1 つの API エンドポイント追加
- 1 つの認証機能追加
- 1 つの地図取得機能追加
- 1 つのグリッド分割機能追加
- 1 つの採点機能追加
- 1 つの点数集計機能追加
- 1 つの分割地図表示用 API 追加
- 1 つのドキュメント更新
- 1 つのバグ修正

例えば「地図採点機能を作る」は大きすぎます。
次のように分けてください。

1. 地図とグリッドの用語を決める
2. 地図取得 API の仕様を `API_SPEC.md` に書く
3. グリッドモデルを設計する
4. グリッド採点 API の仕様を書く
5. serializer、view、URL を小さく実装する
6. テストと README に確認方法を追記する

## 1 回の作業でやってよい範囲

原則として、1 回の作業では次のどれか 1 つに絞ります。

- 設計だけ
- 実装だけ
- テスト追加だけ
- ドキュメント更新だけ
- 小さなバグ修正だけ

例外として、非常に小さい変更の場合は、実装と README の短い追記を同時に行ってもよいです。
ただし、その場合も作業前に範囲を説明してください。

## 作業前の報告フォーマット

Codex は作業前に、次の形式で計画を出してください。

```text
今回の作業計画:
- 目的:
- 担当役割:
- 編集予定ファイル:
- 変更しないファイル:
- 確認方法:
- 仮定していること:
```

セキュリティ設定、認証、権限、環境変数、依存関係を変更する場合は、次も説明してください。

```text
注意が必要な変更:
- 何を変えるか:
- なぜ必要か:
- 初心者向け補足:
- 元に戻す方法:
```

## 作業完了時に報告すべき内容

作業完了時は、次を報告してください。

- 担当した役割
- 変更したファイル
- 変更内容の要約
- 初心者向けの補足説明
- 実行した確認コマンド
- 確認結果
- 未対応のこと
- 次にやるとよい作業

確認コマンドの例:

```bash
source .venv/bin/activate
python manage.py check
python manage.py test
```

## 初心者向け説明ルール

Codex は説明を省略しないでください。
特に次の内容は、作業の中で出てきたら短く説明してください。

- model は DB のテーブル設計に対応すること
- serializer は Python のデータと JSON の変換を担当すること
- view はリクエストを受け取りレスポンスを返す処理であること
- url は API の入り口を決めること
- migration は model の変更を DB に反映するための履歴であること
- グリッドは地図を一定の大きさに区切った 1 マスであること
- 採点はユーザーがグリッドに点数を付ける操作であること
- 集計は複数の点数から表示用の点数を計算する処理であること
- 認証は「誰か」を確認する仕組みであること
- 権限は「何をしてよいか」を確認する仕組みであること
- `.venv` はこのプロジェクト専用の Python 環境であること
- `.env` は PC ごとの秘密情報や設定を置くファイルであること

## 共用 PC での注意

- `sudo pip install` は使わない
- グローバルの Python 環境に依存しない
- `.venv/` は Git に入れない
- `db.sqlite3` は Git に入れない
- `.env` は Git に入れない
- pip の実行は `python -m pip` を使う
- 必要に応じて `PIP_CACHE_DIR=.pip-cache` を指定する

## セキュリティ関連の変更ルール

次の変更は、必ず理由と影響を説明してから行ってください。

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- 認証方式
- 権限設定
- CORS 設定
- 地図 API キーなどの外部サービス用秘密情報
- 位置情報やユーザーの行動履歴に関わる設定

秘密情報はコード、README、API_SPEC、TASK に直接書かないでください。
必要な場合は `.env.example` にダミー値だけを書きます。

## 判断に迷ったとき

判断に迷った場合は、次の優先順位で進めてください。

1. 既存コードを壊さない
2. 初心者が理解できる小さな単位にする
3. セキュリティを弱めない
4. 共用 PC の環境を汚さない
5. README や API_SPEC と実装の差を作らない

不明点がある場合は、推測で進めず、仮定を明記してください。
