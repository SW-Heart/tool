"""
新闻爬虫完整服务
同时运行定时爬虫和 API 服务
"""

import asyncio
import threading
import signal
import sys
import logging
from typing import Optional

import uvicorn

sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from scheduler.news_scheduler import NewsScheduler
from crawlers.api import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsService:
    """新闻服务：爬虫 + API"""
    
    def __init__(
        self, 
        interval_minutes: int = 15,
        api_host: str = "0.0.0.0",
        api_port: int = 8080
    ):
        self.scheduler = NewsScheduler(interval_minutes=interval_minutes)
        self.api_host = api_host
        self.api_port = api_port
        self._running = False
        self._api_thread: Optional[threading.Thread] = None
    
    def _run_api(self):
        """在线程中运行 API 服务"""
        config = uvicorn.Config(
            app, 
            host=self.api_host, 
            port=self.api_port,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())
    
    def run(self, run_immediately: bool = True):
        """启动完整服务"""
        self._running = True
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("=" * 50)
        logger.info("🚀 启动新闻服务")
        logger.info("=" * 50)
        
        # 启动 API 服务（线程）
        self._api_thread = threading.Thread(target=self._run_api, daemon=True)
        self._api_thread.start()
        logger.info(f"📡 API 服务已启动: http://{self.api_host}:{self.api_port}")
        
        # 启动定时爬虫（主线程）
        logger.info(f"⏰ 定时爬虫已启动: 每 {self.scheduler.interval} 分钟")
        self.scheduler.run(run_immediately=run_immediately)
    
    def _signal_handler(self, signum, frame):
        """处理停止信号"""
        logger.info("🛑 正在停止服务...")
        self._running = False
        self.scheduler.stop()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="新闻爬虫完整服务")
    parser.add_argument("--interval", "-i", type=int, default=15, help="抓取间隔(分钟)")
    parser.add_argument("--port", "-p", type=int, default=8080, help="API端口")
    parser.add_argument("--host", default="0.0.0.0", help="API绑定地址")
    parser.add_argument("--no-immediate", action="store_true", help="启动时不立即执行")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("📰 Crypto 新闻完整服务")
    print("=" * 50)
    print(f"⏰ 爬虫间隔: 每 {args.interval} 分钟")
    print(f"📡 API 地址: http://{args.host}:{args.port}")
    print(f"💾 数据保留: 24 小时")
    print("=" * 50)
    
    service = NewsService(
        interval_minutes=args.interval,
        api_host=args.host,
        api_port=args.port
    )
    service.run(run_immediately=not args.no_immediate)


if __name__ == "__main__":
    main()
