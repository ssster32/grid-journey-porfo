#!/usr/bin/env bash
set -o errexit

# 1. ライブラリのインストール
pip install -r requirements.txt

# 2. 静的ファイルの収集
python manage.py collectstatic --no-input

# 3. データベースのマイグレーション
python manage.py migrate

# 4. スーパーユーザーの自動作成（環境変数がある場合のみ）
if [[ -n "$DJANGO_SUPERUSER_USERNAME" ]]; then
python manage.py createsuperuser --noinput || echo "Already exists."
fi