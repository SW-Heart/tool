#!/bin/bash
# ==============================================
# 从GitHub更新代码
# ==============================================

PROJECT_DIR="/opt/etf-scraper"
cd $PROJECT_DIR

echo "停止服务..."
./scripts/stop.sh

echo "拉取最新代码..."
git pull origin main

echo "更新依赖..."
source venv/bin/activate
pip install -r requirements.txt

echo "重启服务..."
./scripts/start.sh

echo "更新完成！"
