#!/bin/bash
# ETF Scraper 服务停止脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "etf_scraper.pid" ]; then
    while read PID; do
        if ps -p $PID > /dev/null 2>&1; then
            echo "停止进程 PID: $PID"
            kill $PID
        fi
    done < etf_scraper.pid
    rm -f etf_scraper.pid
    echo "ETF Scraper 服务已停止"
else
    echo "ETF Scraper 服务未在运行"
fi
