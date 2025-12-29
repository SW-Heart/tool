"""
数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional


@dataclass
class ETFTickerFlow:
    """单个ETF机构的流入数据"""
    ticker: str                 # 机构代码 (如 IBIT, FBTC)
    flow_usd: float            # 流入金额 (百万美元，负数表示流出)
    
    def __post_init__(self):
        self.ticker = self.ticker.upper()


@dataclass
class ETFDailyFlow:
    """单日ETF流入数据"""
    etf_type: str              # ETF类型 (btc/eth/sol)
    date: str                  # 日期 (格式: YYYY-MM-DD)
    total_flow: float          # 总流入 (百万美元)
    price_usd: Optional[float] # 当日价格
    ticker_flows: Dict[str, float] = field(default_factory=dict)  # 各机构流入
    
    def __post_init__(self):
        self.etf_type = self.etf_type.lower()
    
    @property
    def date_obj(self) -> date:
        """转换为date对象"""
        return datetime.strptime(self.date, "%Y-%m-%d").date()
    
    def get_ticker_flow(self, ticker: str) -> float:
        """获取指定机构的流入"""
        return self.ticker_flows.get(ticker.upper(), 0.0)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "etf_type": self.etf_type,
            "date": self.date,
            "total_flow": self.total_flow,
            "price_usd": self.price_usd,
            "ticker_flows": self.ticker_flows,
        }


@dataclass
class ETFSummary:
    """ETF汇总统计"""
    etf_type: str              # ETF类型
    start_date: str            # 开始日期
    end_date: str              # 结束日期
    total_inflow: float        # 总流入
    total_outflow: float       # 总流出
    net_flow: float            # 净流入
    avg_daily_flow: float      # 日均流入
    trading_days: int          # 交易天数
    ticker_totals: Dict[str, float] = field(default_factory=dict)  # 各机构累计
    
    @classmethod
    def from_daily_flows(cls, etf_type: str, flows: List[ETFDailyFlow]) -> "ETFSummary":
        """从每日数据计算汇总"""
        if not flows:
            return cls(
                etf_type=etf_type,
                start_date="",
                end_date="",
                total_inflow=0,
                total_outflow=0,
                net_flow=0,
                avg_daily_flow=0,
                trading_days=0,
            )
        
        # 按日期排序
        sorted_flows = sorted(flows, key=lambda x: x.date)
        
        total_inflow = 0.0
        total_outflow = 0.0
        ticker_totals: Dict[str, float] = {}
        
        for flow in sorted_flows:
            if flow.total_flow > 0:
                total_inflow += flow.total_flow
            else:
                total_outflow += abs(flow.total_flow)
            
            for ticker, amount in flow.ticker_flows.items():
                ticker_totals[ticker] = ticker_totals.get(ticker, 0) + amount
        
        net_flow = total_inflow - total_outflow
        trading_days = len(sorted_flows)
        avg_daily_flow = net_flow / trading_days if trading_days > 0 else 0
        
        return cls(
            etf_type=etf_type,
            start_date=sorted_flows[0].date,
            end_date=sorted_flows[-1].date,
            total_inflow=total_inflow,
            total_outflow=total_outflow,
            net_flow=net_flow,
            avg_daily_flow=avg_daily_flow,
            trading_days=trading_days,
            ticker_totals=ticker_totals,
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "etf_type": self.etf_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_inflow": round(self.total_inflow, 2),
            "total_outflow": round(self.total_outflow, 2),
            "net_flow": round(self.net_flow, 2),
            "avg_daily_flow": round(self.avg_daily_flow, 2),
            "trading_days": self.trading_days,
            "ticker_totals": {k: round(v, 2) for k, v in self.ticker_totals.items()},
        }
