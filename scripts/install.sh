#!/bin/bash
# ==============================================
# Farside ETF 爬虫服务器 - 安装脚本
# 适用于全新的 Ubuntu/Debian 服务器
# ==============================================

set -e

echo "=========================================="
echo "Farside ETF 爬虫服务器 - 安装脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="/opt/etf-scraper"
REPO_URL="https://github.com/SW-Heart/tool.git"

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}请使用 root 用户运行此脚本${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/6] 更新系统包...${NC}"
apt update && apt upgrade -y

echo -e "${YELLOW}[2/6] 安装基础依赖...${NC}"
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    unzip \
    chromium-browser \
    chromium-chromedriver

# 检查 Chrome 版本
echo -e "${GREEN}Chrome 版本: $(chromium-browser --version)${NC}"

echo -e "${YELLOW}[3/6] 创建项目目录...${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

echo -e "${YELLOW}[4/6] 克隆代码仓库...${NC}"
if [ -d ".git" ]; then
    echo "仓库已存在，执行更新..."
    git pull origin main
else
    git clone $REPO_URL .
fi

echo -e "${YELLOW}[5/6] 创建虚拟环境并安装依赖...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt setuptools

echo -e "${YELLOW}[6/6] 创建数据和日志目录...${NC}"
mkdir -p data logs

echo ""
echo -e "${GREEN}=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "项目目录: $PROJECT_DIR"
echo ""
echo "使用方法:"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo ""
echo "  # 手动爬取测试"
echo "  python cli.py scrape btc"
echo ""
echo "  # 启动定时爬虫"
echo "  nohup python cli.py scheduler -e btc -e eth -e sol --now > scheduler.log 2>&1 &"
echo ""
echo "  # 启动API服务"
echo "  nohup python cli.py serve --port 8000 > api.log 2>&1 &"
echo ""
echo -e "${NC}"
