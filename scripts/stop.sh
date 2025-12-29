#!/bin/bash
# ==============================================
# 停止爬虫服务
# ==============================================

echo "停止所有爬虫服务..."

pkill -f "cli.py scheduler" 2>/dev/null && echo "调度器已停止" || echo "调度器未运行"
pkill -f "cli.py serve" 2>/dev/null && echo "API服务已停止" || echo "API服务未运行"

echo "完成"
