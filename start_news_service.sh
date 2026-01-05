#!/bin/bash
# 新闻爬虫服务启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================================="
echo "📰 Crypto 新闻爬虫服务"
echo "=================================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装"
    exit 1
fi

# 检查依赖
echo -e "${YELLOW}📦 检查依赖...${NC}"
pip3 install -q playwright schedule fastapi uvicorn 2>/dev/null || true

# 检查 Playwright 浏览器
if [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
    echo -e "${YELLOW}🌐 安装 Playwright 浏览器...${NC}"
    playwright install chromium
fi

# 创建日志目录
mkdir -p logs data

# 解析参数
MODE="scheduler"  # 默认模式
INTERVAL=15
PORT=8080

while [[ $# -gt 0 ]]; do
    case $1 in
        --api)
            MODE="api"
            shift
            ;;
        --both)
            MODE="both"
            shift
            ;;
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

case $MODE in
    "scheduler")
        echo -e "${GREEN}🚀 启动定时爬虫 (每 ${INTERVAL} 分钟)${NC}"
        python3 -m scheduler.news_scheduler --interval $INTERVAL
        ;;
    "api")
        echo -e "${GREEN}🚀 启动 API 服务 (端口 ${PORT})${NC}"
        uvicorn crawlers.api:app --host 0.0.0.0 --port $PORT
        ;;
    "both")
        echo -e "${GREEN}🚀 启动完整服务 (爬虫 + API)${NC}"
        # 后台启动 API
        uvicorn crawlers.api:app --host 0.0.0.0 --port $PORT &
        API_PID=$!
        echo "   📡 API 服务 PID: $API_PID (端口 $PORT)"
        
        # 前台启动爬虫
        python3 -m scheduler.news_scheduler --interval $INTERVAL
        
        # 清理
        kill $API_PID 2>/dev/null || true
        ;;
esac
