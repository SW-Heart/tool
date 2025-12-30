#!/bin/bash
# X-Alpha 智能舆情服务启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 设置端口
PORT=8002

# 检查环境变量
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "警告: .env 文件不存在，正在从 .env.example 复制..."
        cp .env.example .env
        echo "请编辑 .env 文件配置必要的环境变量 (DEEPSEEK_API_KEY 等)"
        exit 1
    fi
fi

# 检查是否已在运行
if [ -f "x_alpha.pid" ]; then
    PID=$(cat x_alpha.pid | head -1)
    if ps -p $PID > /dev/null 2>&1; then
        echo "X-Alpha 服务已在运行 (PID: $PID)"
        exit 1
    fi
fi

# 激活虚拟环境 (如果存在)
if [ -d "../../venv" ]; then
    source ../../venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 确保日志目录存在
mkdir -p logs

# 代理设置 (如需在中国本地测试，取消下面的注释)
# export http_proxy=http://127.0.0.1:7890
# export https_proxy=http://127.0.0.1:7890

# 启动 API 服务
echo "启动 X-Alpha API 服务 (端口: $PORT)..."
nohup python main.py serve --port $PORT > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > x_alpha.pid

# 启动 Worker 进程
echo "启动 X-Alpha Worker 进程..."
nohup python worker.py > logs/worker.log 2>&1 &
WORKER_PID=$!
echo $WORKER_PID >> x_alpha.pid

echo ""
echo "=========================================="
echo "X-Alpha 智能舆情服务已启动"
echo "=========================================="
echo "API 进程 PID: $API_PID"
echo "Worker 进程 PID: $WORKER_PID"
echo ""
echo "API 地址: http://localhost:$PORT"
echo "健康检查: http://localhost:$PORT/health"
echo "信号接口: http://localhost:$PORT/api/v1/signals"
echo ""
echo "日志文件:"
echo "  API:    $SCRIPT_DIR/logs/api.log"
echo "  Worker: $SCRIPT_DIR/logs/worker.log"
echo "=========================================="
