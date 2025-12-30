"""
表格解析器
解析Farside网站的ETF数据表格
"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])
from config import ETF_TICKERS
from etf_scraper.storage.models import ETFDailyFlow

logger = logging.getLogger(__name__)


class TableParser:
    """Farside ETF表格解析器"""
    
    # 日期格式正则 (如 "26 Dec 2025")
    DATE_PATTERN = re.compile(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})')
    
    # 月份映射
    MONTHS = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
        'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
        'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    def __init__(self, etf_type: str):
        """
        初始化解析器
        
        Args:
            etf_type: ETF类型 (btc/eth/sol)
        """
        self.etf_type = etf_type.lower()
        self.tickers = ETF_TICKERS.get(self.etf_type, [])
    
    def parse_html(self, html: str) -> List[ETFDailyFlow]:
        """
        解析HTML获取ETF数据
        
        Args:
            html: 页面HTML源码
            
        Returns:
            ETF每日流入数据列表
        """
        soup = BeautifulSoup(html, 'lxml')
        table = soup.select_one('table.etf')
        
        if not table:
            logger.error("未找到ETF数据表格")
            return []
        
        # 解析表头获取列映射
        headers = self._parse_headers(table)
        
        # 解析数据行
        flows = self._parse_rows(table, headers)
        
        return flows
    
    def _parse_headers(self, table) -> Dict[int, str]:
        """
        解析表头，建立列索引到机构代码的映射
        
        Returns:
            {列索引: 机构代码}
        """
        headers = {}
        rows = table.find_all('tr')
        
        # 通常第2行包含机构代码
        for row in rows[:4]:
            cells = row.find_all(['th', 'td'])
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True).upper()
                # 检查是否是已知的机构代码
                if text in self.tickers or text == 'TOTAL':
                    headers[i] = text
        
        logger.debug(f"解析到的表头: {headers}")
        return headers
    
    def _parse_rows(self, table, headers: Dict[int, str]) -> List[ETFDailyFlow]:
        """
        解析数据行
        
        Args:
            table: BeautifulSoup表格元素
            headers: 列索引到机构代码的映射
            
        Returns:
            ETF每日流入数据列表
        """
        flows = []
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            
            # 第一列是日期
            date_text = cells[0].get_text(strip=True)
            date_str = self._parse_date(date_text)
            
            if not date_str:
                # 可能是汇总行 (Total, Average等)
                continue
            
            # 解析各机构的流入数据
            ticker_flows = {}
            total_flow = 0.0
            
            for col_idx, ticker in headers.items():
                if col_idx >= len(cells):
                    continue
                
                value = self._parse_flow_value(cells[col_idx].get_text(strip=True))
                
                if ticker == 'TOTAL':
                    total_flow = value
                else:
                    ticker_flows[ticker] = value
            
            # 如果没有解析到Total，则计算总和
            if total_flow == 0.0 and ticker_flows:
                total_flow = sum(ticker_flows.values())
            
            flow = ETFDailyFlow(
                etf_type=self.etf_type,
                date=date_str,
                total_flow=total_flow,
                price_usd=None,
                ticker_flows=ticker_flows,
            )
            flows.append(flow)
        
        logger.info(f"解析到 {len(flows)} 条数据")
        return flows
    
    def _parse_date(self, text: str) -> Optional[str]:
        """
        解析日期文本
        
        Args:
            text: 日期文本 (如 "26 Dec 2025")
            
        Returns:
            标准日期格式 (YYYY-MM-DD) 或 None
        """
        match = self.DATE_PATTERN.search(text)
        if not match:
            return None
        
        day = int(match.group(1))
        month_str = match.group(2)
        year = int(match.group(3))
        
        month = self.MONTHS.get(month_str[:3].title())
        if not month:
            return None
        
        try:
            date_obj = datetime(year, month, day)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    def _parse_flow_value(self, text: str) -> float:
        """
        解析流入值
        括号表示负数，如 (103.6) = -103.6
        
        Args:
            text: 流入值文本
            
        Returns:
            流入金额（百万美元）
        """
        text = text.strip()
        
        if not text or text == '-' or text == '':
            return 0.0
        
        # 移除逗号
        text = text.replace(',', '')
        
        # 检查是否是括号包裹的负数
        if text.startswith('(') and text.endswith(')'):
            try:
                return -float(text[1:-1])
            except ValueError:
                return 0.0
        
        try:
            return float(text)
        except ValueError:
            return 0.0
    
    def parse_summary_row(self, table) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        解析汇总行 (Total, Average)
        
        Returns:
            (总计字典, 平均值字典)
        """
        totals = {}
        averages = {}
        
        rows = table.find_all('tr')
        headers = self._parse_headers(table)
        
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            
            first_cell = cells[0].get_text(strip=True).lower()
            
            if first_cell == 'total':
                for col_idx, ticker in headers.items():
                    if col_idx < len(cells):
                        value = self._parse_flow_value(cells[col_idx].get_text(strip=True))
                        totals[ticker] = value
                        
            elif first_cell == 'average':
                for col_idx, ticker in headers.items():
                    if col_idx < len(cells):
                        value = self._parse_flow_value(cells[col_idx].get_text(strip=True))
                        averages[ticker] = value
        
        return totals, averages
