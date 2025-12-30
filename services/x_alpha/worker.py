"""
X-Alpha Worker 进程
负责定时采集推文、AI 分析、存储数据
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加当前服务目录到路径 (必须在前面，优先加载本地模块)
CURRENT_DIR = Path(__file__).parent
sys.path.insert(0, str(CURRENT_DIR))
# 添加项目根目录 (用于 shared 模块)
sys.path.insert(1, str(CURRENT_DIR.parent.parent))

from shared.logger import setup_logger

# 现在可以安全导入本地 config
from config import TARGET_USERS, DEEPSEEK_CONFIG, COLLECTOR_CONFIG, DATABASE_PATH, LOG_CONFIG
from collector.syndication import TwitterSyndicationCollector
from analyzer.deepseek import DeepSeekAnalyzer
from storage.database import Database

logger = setup_logger("x_alpha.worker", log_file=LOG_CONFIG["worker_log"])


class XAlphaWorker:
    """
    X-Alpha 后台采集与分析进程
    """
    
    def __init__(self):
        self.collector = TwitterSyndicationCollector(
            timeout=COLLECTOR_CONFIG["request_timeout"],
            max_retries=COLLECTOR_CONFIG["max_retries"],
            retry_delay=COLLECTOR_CONFIG["retry_delay"],
            cookies=COLLECTOR_CONFIG.get("cookies"),
        )
        self.analyzer = DeepSeekAnalyzer(
            api_key=DEEPSEEK_CONFIG["api_key"],
            base_url=DEEPSEEK_CONFIG["base_url"],
            model=DEEPSEEK_CONFIG["model"],
            timeout=DEEPSEEK_CONFIG["timeout"],
            max_retries=DEEPSEEK_CONFIG["max_retries"],
        )
        self.storage = Database(DATABASE_PATH)
        self.poll_interval = COLLECTOR_CONFIG["poll_interval"]
        self.running = False
    
    async def run(self):
        """
        主循环: 采集 -> 去重 -> 分析 -> 存储
        """
        self.running = True
        logger.info("X-Alpha Worker 启动")
        logger.info(f"监控用户数: {len(TARGET_USERS)}")
        logger.info(f"轮询间隔: {self.poll_interval} 秒")
        
        while self.running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Worker 循环异常: {e}")
            
            logger.info(f"等待 {self.poll_interval} 秒后进行下一轮采集...")
            await asyncio.sleep(self.poll_interval)
    
    async def _run_cycle(self):
        """执行一轮采集分析"""
        cycle_start = datetime.utcnow()
        logger.info("=" * 50)
        logger.info(f"开始新一轮采集 - {cycle_start.isoformat()}")
        
        # 1. 采集推文
        logger.info("Step 1: 采集推文...")
        tweets = await self.collector.fetch_all_users(TARGET_USERS)
        
        if not tweets:
            logger.warning("未采集到任何推文")
            return
        
        # 2. 去重
        logger.info("Step 2: 去重...")
        new_tweets = [t for t in tweets if not self.storage.exists(t["id"])]
        logger.info(f"新推文: {len(new_tweets)} / {len(tweets)}")
        
        if not new_tweets:
            logger.info("没有新推文需要分析")
            self.storage.set_metadata("last_scan_time", datetime.utcnow().isoformat())
            return
        
        # 3. AI 分析
        logger.info("Step 3: AI 分析...")
        analyzed = await self.analyzer.batch_analyze(new_tweets, concurrency=3)
        
        # 4. 存储相关信号
        logger.info("Step 4: 存储信号...")
        saved_count = 0
        for signal in analyzed:
            if signal.get("is_relevant"):
                if self.storage.save_signal(signal):
                    saved_count += 1
                    logger.info(
                        f"  [{signal.get('signal_type')}] @{signal.get('author')}: "
                        f"{signal.get('summary_zh', '')[:30]}..."
                    )
        
        # 更新最后扫描时间
        self.storage.set_metadata("last_scan_time", datetime.utcnow().isoformat())
        
        cycle_end = datetime.utcnow()
        duration = (cycle_end - cycle_start).total_seconds()
        
        logger.info("-" * 50)
        logger.info(f"本轮完成: 采集 {len(tweets)} 条, 新增 {len(new_tweets)} 条, 保存 {saved_count} 条信号")
        logger.info(f"耗时: {duration:.1f} 秒")
    
    async def run_once(self):
        """只运行一轮 (用于测试)"""
        await self._run_cycle()
    
    def stop(self):
        """停止 Worker"""
        self.running = False
        logger.info("Worker 停止中...")


async def main():
    """Worker 入口"""
    worker = XAlphaWorker()
    
    # 处理退出信号
    import signal
    
    def handle_exit(signum, frame):
        worker.stop()
    
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
