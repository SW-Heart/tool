#!/bin/bash
# X-Alpha 智能舆情服务停止脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "x_alpha.pid" ]; then
    echo "停止 X-Alpha 服务..."
    while read PID; do
        if ps -p $PID > /dev/null 2>&1; then
            echo "  停止进程 PID: $PID"
            kill $PID
        fi
    done < x_alpha.pid
    rm -f x_alpha.pid
    echo "X-Alpha 服务已停止"
else
    echo "X-Alpha 服务未在运行"
fi
