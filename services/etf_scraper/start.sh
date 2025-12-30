#!/bin/bash
# ETF Scraper 服务启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 设置端口
PORT=8001

# 检查是否已在运行
if [ -f "etf_scraper.pid" ]; then
    PID=$(cat etf_scraper.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "ETF Scraper 服务已在运行 (PID: $PID)"
        exit 1
    fi
fi

# 激活虚拟环境 (如果存在)
if [ -d "../../venv" ]; then
    source ../../venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 启动 API 服务
echo "启动 ETF Scraper API 服务 (端口: $PORT)..."
nohup python main.py serve --port $PORT > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > etf_scraper.pid

# 启动定时任务 (如果需要)
# nohup python -c "from scheduler.cron import run_scheduler; run_scheduler()" > logs/scheduler.log 2>&1 &
# SCHEDULER_PID=$!
# echo $SCHEDULER_PID >> etf_scraper.pid

echo "ETF Scraper 服务已启动 (PID: $API_PID)"
echo "API 地址: http://localhost:$PORT"
echo "日志文件: $SCRIPT_DIR/logs/api.log"
