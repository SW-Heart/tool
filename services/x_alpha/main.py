"""
X-Alpha 智能舆情服务
主入口文件
"""
import sys
from pathlib import Path

# 添加当前服务目录到路径 (必须最先，优先加载本地模块)
CURRENT_DIR = Path(__file__).parent
sys.path.insert(0, str(CURRENT_DIR))
# 添加项目根目录 (用于 shared 模块)
sys.path.insert(1, str(CURRENT_DIR.parent.parent))

import time
import click
import uvicorn
from fastapi import FastAPI, Query, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime

from config import API_CONFIG, API_SECRET_KEY, TARGET_USERS, DATABASE_PATH, LOG_CONFIG
from models import SignalResponse, APIResponse, HealthResponse
from storage.database import Database
from shared.logger import setup_logger
from shared.utils import time_ago

logger = setup_logger("x_alpha.api", log_file=LOG_CONFIG["api_log"])

# 创建 FastAPI 应用
app = FastAPI(
    title="X-Alpha 智能舆情服务",
    description="监控 KOL 推文，提取金融信号",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库实例
db = Database(DATABASE_PATH)


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """验证 API Key"""
    if API_SECRET_KEY and x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    stats = db.get_stats()
    
    return HealthResponse(
        status="ok",
        db_connected=True,
        last_scan_time=stats.get("last_scan_time"),
        monitored_users=[u["username"] for u in TARGET_USERS],
        total_signals=stats.get("total_signals", 0),
    )


@app.get("/api/v1/signals", response_model=APIResponse)
async def get_signals(
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
    min_sentiment: Optional[int] = Query(default=None, ge=0, le=10, description="最低情绪分"),
    symbol: Optional[str] = Query(default=None, description="筛选币种"),
    signal_type: Optional[str] = Query(default=None, description="筛选信号类型 (BUY/SELL/WATCH/NEUTRAL)"),
    author: Optional[str] = Query(default=None, description="筛选博主"),
    _auth: bool = Depends(verify_api_key),
):
    """
    获取最新信号
    
    主网站前端轮询或服务端转发调用此接口。
    """
    signals = db.get_signals(
        limit=limit,
        min_sentiment=min_sentiment,
        symbol=symbol,
        signal_type=signal_type,
        author=author,
    )
    
    response_data = []
    for s in signals:
        # 解析发布时间
        published_at = s.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except:
                published_at = datetime.utcnow()
        
        publish_timestamp = int(published_at.timestamp()) if published_at else int(time.time())
        
        response_data.append(SignalResponse(
            id=s["id"],
            author=s["author"],
            avatar_url=s.get("avatar_url"),
            summary=s.get("ai_summary", ""),
            original_text=s.get("raw_content", ""),
            signal=s.get("signal", "NEUTRAL"),
            sentiment=s.get("sentiment", 5),
            assets=s.get("assets", []),
            tweet_url=s.get("tweet_url", ""),
            time_ago=time_ago(published_at) if published_at else "unknown",
            publish_timestamp=publish_timestamp,
            tags=s.get("tags", []),
        ))
    
    return APIResponse(
        status="success",
        timestamp=int(time.time()),
        data=response_data,
    )


@app.get("/api/v1/users")
async def get_monitored_users(_auth: bool = Depends(verify_api_key)):
    """获取监控的用户列表"""
    return {
        "status": "success",
        "data": TARGET_USERS,
    }


@app.get("/api/v1/stats")
async def get_stats(_auth: bool = Depends(verify_api_key)):
    """获取统计信息"""
    return {
        "status": "success",
        "data": db.get_stats(),
    }


def run_server(host: str = "0.0.0.0", port: int = 8002):
    """运行 API 服务器"""
    uvicorn.run(app, host=host, port=port)


@click.group()
def main():
    """X-Alpha 智能舆情服务"""
    pass


@main.command()
@click.option('--host', default=API_CONFIG["host"], help='服务器地址')
@click.option('--port', default=API_CONFIG["port"], help='服务器端口')
def serve(host: str, port: int):
    """启动 API 服务"""
    logger.info(f"启动 X-Alpha API 服务: http://{host}:{port}")
    run_server(host=host, port=port)


@main.command()
def worker():
    """启动 Worker 进程"""
    import asyncio
    from worker import main as worker_main
    logger.info("启动 X-Alpha Worker 进程")
    asyncio.run(worker_main())


@main.command()
def run_once():
    """运行一次采集 (测试用)"""
    import asyncio
    from worker import XAlphaWorker
    
    async def _run():
        w = XAlphaWorker()
        await w.run_once()
    
    asyncio.run(_run())


@main.command()
def init():
    """初始化数据库"""
    db = Database(DATABASE_PATH)
    logger.info("数据库初始化完成")


if __name__ == '__main__':
    main()
