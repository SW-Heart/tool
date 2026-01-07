"""
新闻爬虫定时任务调度器
每15分钟自动抓取 PANews 重要资讯
"""

import time
import logging
import signal
import sys
from datetime import datetime
from typing import List, Optional

import schedule

# 添加项目路径
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from crawlers.panews import PANewsCrawler
from crawlers.storage import get_storage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/news_scheduler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class NewsScheduler:
    """新闻爬虫定时调度器"""
    
    # 稳定性配置
    MAX_RETRIES = 3  # 单次抓取最大重试次数
    MAX_CONSECUTIVE_FAILURES = 5  # 连续失败阈值，超过则重置爬虫
    RETRY_DELAY_SECONDS = 5  # 重试间隔
    
    def __init__(self, interval_minutes: int = 15):
        """
        初始化调度器
        
        Args:
            interval_minutes: 爬取间隔（分钟），默认15分钟
        """
        self.interval = interval_minutes
        self.crawler = PANewsCrawler(headless=True)
        self.storage = get_storage()
        self._running = False
        self._last_run: Optional[datetime] = None
        self._last_success: Optional[datetime] = None
        self._total_fetched = 0
        self._total_saved = 0
        self._consecutive_failures = 0
    
    def fetch_news(self):
        """执行一次新闻抓取（带重试机制）"""
        logger.info("=" * 50)
        logger.info(f"🚀 开始抓取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        self._last_run = datetime.now()
        last_error = None
        
        # 重试机制
        for attempt in range(self.MAX_RETRIES):
            try:
                # 抓取新闻（自动保存到数据库）
                news = self.crawler.fetch_sync(only_new=True, save_to_db=True)
                
                # 成功：重置失败计数
                self._consecutive_failures = 0
                self._last_success = datetime.now()
                self._total_fetched += len(news)
                
                if news:
                    logger.info(f"✅ 成功抓取 {len(news)} 条新资讯")
                    for item in news[:3]:  # 只显示前3条
                        logger.info(f"   📰 {item.get('time', '')} | {item['title'][:40]}...")
                    if len(news) > 3:
                        logger.info(f"   ... 还有 {len(news) - 3} 条")
                else:
                    logger.info("ℹ️ 暂无新资讯")
                
                # 显示统计
                stats = self.storage.get_stats()
                logger.info(f"📊 数据库状态: 共 {stats['total']} 条，保留 {stats['retention_hours']} 小时")
                logger.info("=" * 50)
                return  # 成功则退出
                
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"⚠️ 抓取失败，重试 {attempt + 1}/{self.MAX_RETRIES}: {e}")
                    time.sleep(self.RETRY_DELAY_SECONDS)
        
        # 全部重试失败
        self._consecutive_failures += 1
        logger.error(f"❌ 抓取失败（已重试{self.MAX_RETRIES}次）: {last_error}")
        logger.error(f"⚠️ 连续失败次数: {self._consecutive_failures}/{self.MAX_CONSECUTIVE_FAILURES}")
        
        # 检查是否需要重置爬虫
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._reset_crawler()
        
        logger.info("=" * 50)
    
    def _reset_crawler(self):
        """重置爬虫实例（连续失败过多时调用）"""
        logger.warning("🔄 连续失败过多，正在重置爬虫实例...")
        try:
            # 重新创建爬虫实例
            self.crawler = PANewsCrawler(headless=True)
            self._consecutive_failures = 0
            logger.info("✅ 爬虫实例已重置")
        except Exception as e:
            logger.error(f"❌ 重置爬虫失败: {e}")
    
    def cleanup_expired(self):
        """清理过期数据"""
        try:
            deleted = self.storage.cleanup_expired()
            if deleted > 0:
                logger.info(f"🧹 清理了 {deleted} 条过期新闻")
        except Exception as e:
            logger.error(f"清理失败: {e}")
    
    def setup_schedule(self):
        """设置定时任务"""
        # 每 N 分钟执行一次
        schedule.every(self.interval).minutes.do(self.fetch_news)
        
        # 每小时清理一次过期数据
        schedule.every().hour.do(self.cleanup_expired)
        
        logger.info(f"⏰ 定时任务已设置:")
        logger.info(f"   - 每 {self.interval} 分钟抓取新闻")
        logger.info(f"   - 每小时清理过期数据 (超过24小时)")
    
    def run(self, run_immediately: bool = True):
        """
        启动调度器
        
        Args:
            run_immediately: 是否立即执行一次
        """
        self._running = True
        
        # 确保日志目录存在
        import os
        os.makedirs('logs', exist_ok=True)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.setup_schedule()
        
        if run_immediately:
            logger.info("🔄 立即执行一次抓取...")
            self.fetch_news()
        
        logger.info(f"✅ 调度器已启动")
        logger.info(f"⏳ 下次执行: {schedule.next_run()}")
        
        while self._running:
            schedule.run_pending()
            time.sleep(30)  # 每30秒检查一次
    
    def _signal_handler(self, signum, frame):
        """处理停止信号"""
        logger.info("🛑 收到停止信号，正在关闭...")
        self._running = False
    
    def stop(self):
        """停止调度器"""
        self._running = False
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            'running': self._running,
            'interval_minutes': self.interval,
            'last_run': self._last_run.isoformat() if self._last_run else None,
            'last_success': self._last_success.isoformat() if self._last_success else None,
            'next_run': str(schedule.next_run()) if schedule.jobs else None,
            'total_fetched': self._total_fetched,
            'consecutive_failures': self._consecutive_failures,
            'storage_stats': self.storage.get_stats()
        }


def run_news_scheduler(interval: int = 15, run_immediately: bool = True):
    """
    运行新闻调度器
    
    Args:
        interval: 抓取间隔（分钟）
        run_immediately: 是否立即执行
    """
    scheduler = NewsScheduler(interval_minutes=interval)
    scheduler.run(run_immediately=run_immediately)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="新闻爬虫定时调度器")
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=15,
        help="抓取间隔（分钟），默认15"
    )
    parser.add_argument(
        "--no-immediate",
        action="store_true",
        help="启动时不立即执行"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("📰 Crypto 新闻爬虫调度器")
    print("=" * 50)
    print(f"⏰ 抓取间隔: 每 {args.interval} 分钟")
    print(f"💾 数据保留: 24 小时")
    print(f"📡 数据来源: PANews (重要资讯)")
    print("=" * 50)
    
    run_news_scheduler(
        interval=args.interval,
        run_immediately=not args.no_immediate
    )
