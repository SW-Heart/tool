#!/bin/bash
# 一键启动所有服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICES_DIR="$SCRIPT_DIR/../services"

echo "启动所有服务..."
echo ""

# 遍历 services 目录下的所有服务
for service_dir in "$SERVICES_DIR"/*/; do
    if [ -f "$service_dir/start.sh" ]; then
        service_name=$(basename "$service_dir")
        echo ">>> 启动 $service_name..."
        cd "$service_dir" && ./start.sh
        echo ""
    fi
done

echo "所有服务启动完成！"
