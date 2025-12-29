"""
SQLite 数据库操作
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict
from contextlib import contextmanager

import sys
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])
from config import DATABASE_PATH
from etf_scraper.storage.models import ETFDailyFlow, ETFSummary

logger = logging.getLogger(__name__)


class Database:
    """ETF数据数据库管理"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path or str(DATABASE_PATH)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # ETF每日流入数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS etf_flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    etf_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    flow_usd REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(etf_type, date, ticker)
                )
            ''')
            
            # ETF每日汇总表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    etf_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_flow REAL NOT NULL,
                    price_usd REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(etf_type, date)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_flows_etf_date ON etf_flows(etf_type, date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_flows_ticker ON etf_flows(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_summary_etf_date ON daily_summary(etf_type, date)')
            
            conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def save_daily_flow(self, flow: ETFDailyFlow) -> bool:
        """
        保存每日流入数据
        
        Args:
            flow: ETF每日流入数据
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 保存汇总数据
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_summary 
                    (etf_type, date, total_flow, price_usd) 
                    VALUES (?, ?, ?, ?)
                ''', (flow.etf_type, flow.date, flow.total_flow, flow.price_usd))
                
                # 保存各机构数据
                for ticker, amount in flow.ticker_flows.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO etf_flows 
                        (etf_type, date, ticker, flow_usd) 
                        VALUES (?, ?, ?, ?)
                    ''', (flow.etf_type, flow.date, ticker, amount))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
    
    def save_daily_flows(self, flows: List[ETFDailyFlow]) -> int:
        """
        批量保存每日流入数据
        
        Args:
            flows: ETF每日流入数据列表
            
        Returns:
            成功保存的数量
        """
        saved = 0
        for flow in flows:
            if self.save_daily_flow(flow):
                saved += 1
        
        logger.info(f"成功保存 {saved}/{len(flows)} 条数据")
        return saved
    
    def get_daily_flows(self, etf_type: str, days: int = 15) -> List[ETFDailyFlow]:
        """
        获取最近N天的流入数据
        
        Args:
            etf_type: ETF类型
            days: 天数
            
        Returns:
            ETF每日流入数据列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取每日汇总
            cursor.execute('''
                SELECT date, total_flow, price_usd 
                FROM daily_summary 
                WHERE etf_type = ? 
                ORDER BY date DESC 
                LIMIT ?
            ''', (etf_type.lower(), days))
            
            summaries = cursor.fetchall()
            
            flows = []
            for row in summaries:
                date = row['date']
                
                # 获取该日各机构数据
                cursor.execute('''
                    SELECT ticker, flow_usd 
                    FROM etf_flows 
                    WHERE etf_type = ? AND date = ?
                ''', (etf_type.lower(), date))
                
                ticker_flows = {r['ticker']: r['flow_usd'] for r in cursor.fetchall()}
                
                flow = ETFDailyFlow(
                    etf_type=etf_type,
                    date=date,
                    total_flow=row['total_flow'],
                    price_usd=row['price_usd'],
                    ticker_flows=ticker_flows,
                )
                flows.append(flow)
            
            return flows
    
    def get_flow_by_date(self, etf_type: str, date: str) -> Optional[ETFDailyFlow]:
        """
        按日期查询流入数据
        
        Args:
            etf_type: ETF类型
            date: 日期 (YYYY-MM-DD)
            
        Returns:
            ETF每日流入数据或None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT total_flow, price_usd 
                FROM daily_summary 
                WHERE etf_type = ? AND date = ?
            ''', (etf_type.lower(), date))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # 获取各机构数据
            cursor.execute('''
                SELECT ticker, flow_usd 
                FROM etf_flows 
                WHERE etf_type = ? AND date = ?
            ''', (etf_type.lower(), date))
            
            ticker_flows = {r['ticker']: r['flow_usd'] for r in cursor.fetchall()}
            
            return ETFDailyFlow(
                etf_type=etf_type,
                date=date,
                total_flow=row['total_flow'],
                price_usd=row['price_usd'],
                ticker_flows=ticker_flows,
            )
    
    def get_flows_by_ticker(self, etf_type: str, ticker: str, days: int = 30) -> List[Dict]:
        """
        按机构查询流入数据
        
        Args:
            etf_type: ETF类型
            ticker: 机构代码
            days: 天数
            
        Returns:
            流入数据列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT date, flow_usd 
                FROM etf_flows 
                WHERE etf_type = ? AND ticker = ? 
                ORDER BY date DESC 
                LIMIT ?
            ''', (etf_type.lower(), ticker.upper(), days))
            
            return [{"date": r['date'], "flow_usd": r['flow_usd']} for r in cursor.fetchall()]
    
    def get_ticker_summary(self, etf_type: str) -> Dict[str, float]:
        """
        获取各机构累计流入
        
        Args:
            etf_type: ETF类型
            
        Returns:
            {机构代码: 累计流入}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ticker, SUM(flow_usd) as total 
                FROM etf_flows 
                WHERE etf_type = ? 
                GROUP BY ticker
                ORDER BY total DESC
            ''', (etf_type.lower(),))
            
            return {r['ticker']: r['total'] for r in cursor.fetchall()}
    
    def get_summary(self, etf_type: str) -> ETFSummary:
        """
        获取ETF汇总统计
        
        Args:
            etf_type: ETF类型
            
        Returns:
            ETF汇总统计
        """
        flows = self.get_daily_flows(etf_type, days=9999)
        return ETFSummary.from_daily_flows(etf_type, flows)
    
    def get_latest_date(self, etf_type: str) -> Optional[str]:
        """获取最新数据日期"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(date) as latest 
                FROM daily_summary 
                WHERE etf_type = ?
            ''', (etf_type.lower(),))
            
            row = cursor.fetchone()
            return row['latest'] if row else None
