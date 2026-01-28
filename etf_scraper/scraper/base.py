"""
ETF 爬虫基类
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])
from config import SCRAPER_CONFIG, FARSIDE_URLS, BASE_DIR
from etf_scraper.browser.driver import BrowserDriver, get_browser
from etf_scraper.parser.table_parser import TableParser
from etf_scraper.storage.models import ETFDailyFlow
from etf_scraper.storage.database import Database

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """ETF爬虫基类"""
    
    def __init__(self, etf_type: str):
        """
        初始化爬虫
        
        Args:
            etf_type: ETF类型 (btc/eth/sol)
        """
        self.etf_type = etf_type.lower()
        self.url = FARSIDE_URLS.get(self.etf_type)
        self.parser = TableParser(self.etf_type)
        self.db = Database()
        
        if not self.url:
            raise ValueError(f"不支持的ETF类型: {etf_type}")
    
    def scrape(self, headless: bool = True, save: bool = True) -> List[ETFDailyFlow]:
        """
        执行爬取任务
        
        Args:
            headless: 是否使用无头模式
            save: 是否保存到数据库
            
        Returns:
            ETF每日流入数据列表
        """
        retry_count = SCRAPER_CONFIG["retry_count"]
        retry_delay = SCRAPER_CONFIG["retry_delay"]
        
        for attempt in range(retry_count):
            try:
                logger.info(f"开始爬取 {self.etf_type.upper()} ETF 数据 (尝试 {attempt + 1}/{retry_count})")
                
                with get_browser(headless=headless) as browser:
                    try:
                        # 访问页面
                        success = browser.get(self.url, wait_for_selector="table.etf")
                        
                        if not success:
                            raise Exception("页面加载失败")
                        
                        # 额外等待确保JavaScript执行完成
                        time.sleep(SCRAPER_CONFIG["request_delay"])
                        
                        # 获取页面源码
                        html = browser.get_page_source()
                        
                        # 解析数据
                        flows = self.parser.parse_html(html)
                        
                        if not flows:
                            raise Exception("未解析到任何数据")
                        
                        logger.info(f"成功解析 {len(flows)} 条 {self.etf_type.upper()} ETF 数据")
                        
                        # 保存到数据库
                        if save:
                            saved = self.db.save_daily_flows(flows)
                            logger.info(f"保存 {saved} 条数据到数据库")
                        
                        return flows
                        
                    except Exception as e:
                        # 在浏览器关闭前保存调试信息
                        logger.error(f"爬取过程中出错: {e}")
                        self._save_debug_info(browser)
                        raise e
                    
            except Exception as e:
                logger.error(f"本次尝试失败: {e}")
                
                if attempt < retry_count - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"重试 {retry_count} 次后仍然失败")
                    raise
        
        return []

    def _save_debug_info(self, browser):
        """保存调试信息(截图和源码)"""
        try:
            timestamp = int(time.time())
            log_dir = BASE_DIR / "logs"
            
            # 确保目录存在
            log_dir.mkdir(exist_ok=True)
            
            screenshot_path = log_dir / f"error_{self.etf_type}_{timestamp}.png"
            html_path = log_dir / f"error_{self.etf_type}_{timestamp}.html"
            
            if browser.save_screenshot(screenshot_path):
                logger.info(f"已保存调试截图: {screenshot_path}")
                
            if browser.save_page_source(html_path):
                logger.info(f"已保存调试源码: {html_path}")
                
        except Exception as e:
            logger.error(f"保存调试信息失败: {e}")
    
    def get_latest_data(self, days: int = 15) -> List[ETFDailyFlow]:
        """
        从数据库获取最新数据
        
        Args:
            days: 天数
            
        Returns:
            ETF每日流入数据列表
        """
        return self.db.get_daily_flows(self.etf_type, days)
    
    def get_by_date(self, date: str) -> Optional[ETFDailyFlow]:
        """按日期查询"""
        return self.db.get_flow_by_date(self.etf_type, date)
    
    def get_by_ticker(self, ticker: str, days: int = 30) -> List[dict]:
        """按机构查询"""
        return self.db.get_flows_by_ticker(self.etf_type, ticker, days)
    
    def get_summary(self):
        """获取汇总统计"""
        return self.db.get_summary(self.etf_type)


class BTCScraper(BaseScraper):
    """BTC ETF 爬虫"""
    
    def __init__(self):
        super().__init__("btc")


class ETHScraper(BaseScraper):
    """ETH ETF 爬虫"""
    
    def __init__(self):
        super().__init__("eth")


class SOLScraper(BaseScraper):
    """SOL ETF 爬虫"""
    
    def __init__(self):
        super().__init__("sol")


def get_scraper(etf_type: str) -> BaseScraper:
    """
    获取指定类型的爬虫实例
    
    Args:
        etf_type: ETF类型 (btc/eth/sol)
        
    Returns:
        爬虫实例
    """
    scrapers = {
        "btc": BTCScraper,
        "eth": ETHScraper,
        "sol": SOLScraper,
    }
    
    etf_type = etf_type.lower()
    if etf_type not in scrapers:
        raise ValueError(f"不支持的ETF类型: {etf_type}")
    
    return scrapers[etf_type]()
