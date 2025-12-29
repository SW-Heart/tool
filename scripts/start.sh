#!/bin/bash
# ==============================================
# 启动爬虫服务（scheduler + API）
# ==============================================

PROJECT_DIR="/opt/etf-scraper"
cd $PROJECT_DIR
source venv/bin/activate

echo "启动定时爬虫调度器..."
nohup python cli.py scheduler -e btc -e eth -e sol --now > logs/scheduler.log 2>&1 &
echo "调度器 PID: $!"

echo "启动API服务..."
nohup python cli.py serve --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
echo "API服务 PID: $!"

echo ""
echo "服务已启动！"
echo "  - 调度器日志: tail -f logs/scheduler.log"
echo "  - API日志: tail -f logs/api.log"
echo "  - API地址: http://$(hostname -I | awk '{print $1}'):8000"
