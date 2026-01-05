"""
新闻 API 服务 - FastAPI
提供 RESTful 接口供外部服务获取新闻数据
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime

from .storage import get_storage, NewsStorage

app = FastAPI(
    title="Crypto News API",
    description="实时加密货币新闻聚合 API",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API 状态检查"""
    return {
        "status": "ok",
        "service": "Crypto News API",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/news")
async def get_news(
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
    source: Optional[str] = Query(default=None, description="来源筛选，如 PANews")
):
    """
    获取最新新闻
    
    - **limit**: 返回条数（1-100，默认20）
    - **source**: 来源筛选，如 `PANews`
    """
    storage = get_storage()
    news = storage.get_latest_news(limit=limit, source=source)
    
    return {
        "count": len(news),
        "data": news
    }


@app.get("/api/news/latest")
async def get_latest():
    """获取最新一条新闻"""
    storage = get_storage()
    news = storage.get_latest_news(limit=1)
    
    if not news:
        raise HTTPException(status_code=404, detail="暂无新闻数据")
    
    return news[0]


@app.get("/api/news/since/{news_id}")
async def get_news_since(news_id: str):
    """
    获取某条新闻之后的所有新闻
    
    用于增量更新场景
    """
    storage = get_storage()
    news = storage.get_news_since(news_id)
    
    return {
        "since_id": news_id,
        "count": len(news),
        "data": news
    }


@app.get("/api/stats")
async def get_stats():
    """获取数据统计信息"""
    storage = get_storage()
    stats = storage.get_stats()
    
    return stats


@app.post("/api/cleanup")
async def cleanup_expired():
    """
    手动触发清理过期数据
    
    通常由定时任务自动执行
    """
    storage = get_storage()
    deleted = storage.cleanup_expired()
    
    return {
        "deleted": deleted,
        "message": f"清理了 {deleted} 条过期新闻"
    }


# 用于直接运行
def run_server(host: str = "0.0.0.0", port: int = 8080):
    """启动 API 服务"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
