"""
定时任务调度器
每天 0:00, 6:00, 12:00, 18:00 自动爬取ETF数据
"""
import time
import logging
import signal
import sys
from datetime import datetime
from typing import List

import schedule

# 添加项目路径
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])
from etf_scraper.scraper.base import get_scraper
from etf_scraper.storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ETFScheduler:
    """ETF数据定时爬取调度器"""
    
    def __init__(self, etf_types: List[str] = None):
        """
        初始化调度器
        
        Args:
            etf_types: 要爬取的ETF类型列表，默认['btc', 'eth', 'sol']
        """
        self.etf_types = etf_types or ['btc', 'eth', 'sol']
        self.db = Database()
        self._running = False
    
    def scrape_all(self):
        """爬取所有ETF数据（增量更新）"""
        logger.info("=" * 50)
        logger.info(f"开始定时爬取任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        for etf_type in self.etf_types:
            try:
                self._scrape_with_incremental_update(etf_type)
            except Exception as e:
                logger.error(f"爬取 {etf_type.upper()} 失败: {e}")
        
        logger.info("定时爬取任务完成")
        logger.info("=" * 50)
    
    def _scrape_with_incremental_update(self, etf_type: str):
        """
        增量更新爬取
        只保存数据库中不存在的新数据
        """
        logger.info(f"正在爬取 {etf_type.upper()} ETF...")
        
        # 获取数据库中最新日期
        latest_date = self.db.get_latest_date(etf_type)
        logger.info(f"数据库最新日期: {latest_date or '无数据'}")
        
        # 爬取数据
        scraper = get_scraper(etf_type)
        flows = scraper.scrape(headless=True, save=False)  # 先不保存
        
        if not flows:
            logger.warning(f"{etf_type.upper()} 未获取到数据")
            return
        
        # 筛选新数据
        new_flows = []
        updated_flows = []
        
        for flow in flows:
            existing = self.db.get_flow_by_date(etf_type, flow.date)
            
            if existing is None:
                # 新数据
                new_flows.append(flow)
            elif existing.total_flow != flow.total_flow:
                # 数据有更新（同一天数据可能会更新）
                updated_flows.append(flow)
        
        # 保存新数据
        if new_flows:
            saved = self.db.save_daily_flows(new_flows)
            logger.info(f"新增 {saved} 条 {etf_type.upper()} 数据")
        
        # 更新已有数据
        if updated_flows:
            saved = self.db.save_daily_flows(updated_flows)
            logger.info(f"更新 {saved} 条 {etf_type.upper()} 数据")
        
        if not new_flows and not updated_flows:
            logger.info(f"{etf_type.upper()} 数据已是最新，无需更新")
    
    def setup_schedule(self):
        """
        设置定时任务 (服务器时间为 UTC)
        对应北京时间 (UTC+8): 
        00:00 UTC -> 08:00 (早报)
        06:00 UTC -> 14:00 (午间更新，昨天数据通常此时已出)
        12:00 UTC -> 20:00 (晚间)
        18:00 UTC -> 02:00 (凌晨)
        """
        schedule.every().day.at("00:00").do(self.scrape_all)
        schedule.every().day.at("06:00").do(self.scrape_all)
        schedule.every().day.at("12:00").do(self.scrape_all)
        schedule.every().day.at("18:00").do(self.scrape_all)
        
        logger.info("定时任务已设置 (UTC时间):")
        logger.info("  - 每天 00:00 (北京时间 08:00)")
        logger.info("  - 每天 06:00 (北京时间 14:00) *重点更新*")
        logger.info("  - 每天 12:00 (北京时间 20:00)")
        logger.info("  - 每天 18:00 (北京时间 02:00)")
    
    def run(self, run_immediately: bool = False):
        """
        启动调度器
        
        Args:
            run_immediately: 是否立即执行一次
        """
        self._running = True
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.setup_schedule()
        
        if run_immediately:
            logger.info("立即执行一次爬取...")
            self.scrape_all()
        
        logger.info("调度器已启动，等待执行...")
        logger.info(f"下次执行时间: {schedule.next_run()}")
        
        while self._running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def _signal_handler(self, signum, frame):
        """处理停止信号"""
        logger.info("收到停止信号，正在关闭调度器...")
        self._running = False
    
    def stop(self):
        """停止调度器"""
        self._running = False


def run_scheduler(etf_types: List[str] = None, run_immediately: bool = False):
    """
    运行调度器
    
    Args:
        etf_types: ETF类型列表
        run_immediately: 是否立即执行
    """
    scheduler = ETFScheduler(etf_types)
    scheduler.run(run_immediately=run_immediately)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ETF数据定时爬取调度器")
    parser.add_argument(
        "--etf", 
        nargs="+", 
        default=["btc"],
        choices=["btc", "eth", "sol"],
        help="要爬取的ETF类型"
    )
    parser.add_argument(
        "--now", 
        action="store_true",
        help="立即执行一次爬取"
    )
    
    args = parser.parse_args()
    
    print(f"ETF定时爬取调度器")
    print(f"爬取类型: {', '.join(args.etf)}")
    print(f"定时: 每天 00:00, 06:00, 12:00, 18:00")
    print("-" * 40)
    
    run_scheduler(etf_types=args.etf, run_immediately=args.now)
