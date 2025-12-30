#!/bin/bash
# 一键停止所有服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICES_DIR="$SCRIPT_DIR/../services"

echo "停止所有服务..."
echo ""

# 遍历 services 目录下的所有服务
for service_dir in "$SERVICES_DIR"/*/; do
    if [ -f "$service_dir/stop.sh" ]; then
        service_name=$(basename "$service_dir")
        echo ">>> 停止 $service_name..."
        cd "$service_dir" && ./stop.sh
        echo ""
    fi
done

echo "所有服务已停止！"
