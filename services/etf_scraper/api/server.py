"""
FastAPI 服务
提供ETF数据查询API
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])
from etf_scraper.scraper.base import get_scraper
from etf_scraper.storage.database import Database
from etf_scraper.storage.models import ETFDailyFlow, ETFSummary

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="ETF Flow Scraper API",
    description="Farside ETF流入数据查询服务",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库实例
db = Database()


# 响应模型
class DailyFlowResponse(BaseModel):
    etf_type: str
    date: str
    total_flow: float
    price_usd: Optional[float]
    ticker_flows: dict


class SummaryResponse(BaseModel):
    etf_type: str
    start_date: str
    end_date: str
    total_inflow: float
    total_outflow: float
    net_flow: float
    avg_daily_flow: float
    trading_days: int
    ticker_totals: dict


class TickerFlowResponse(BaseModel):
    date: str
    flow_usd: float


class ScrapeResponse(BaseModel):
    success: bool
    message: str
    records_count: int


# API路由
@app.get("/")
async def root():
    """API根路径"""
    return {
        "service": "ETF Flow Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "flows": "/api/etf/{type}/flows",
            "date": "/api/etf/{type}/date/{date}",
            "ticker": "/api/etf/{type}/ticker/{ticker}",
            "summary": "/api/etf/{type}/summary",
            "scrape": "/api/scrape/{type}",
        }
    }


@app.get("/api/etf/{etf_type}/flows", response_model=List[DailyFlowResponse])
async def get_flows(
    etf_type: str,
    days: int = Query(default=15, ge=1, le=365, description="查询天数")
):
    """
    获取ETF历史流入数据
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    - **days**: 查询天数 (1-365)
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型，请使用 btc/eth/sol")
    
    flows = db.get_daily_flows(etf_type, days)
    
    return [
        DailyFlowResponse(
            etf_type=f.etf_type,
            date=f.date,
            total_flow=f.total_flow,
            price_usd=f.price_usd,
            ticker_flows=f.ticker_flows,
        )
        for f in flows
    ]


@app.get("/api/etf/{etf_type}/date/{date}", response_model=DailyFlowResponse)
async def get_flow_by_date(etf_type: str, date: str):
    """
    按日期查询ETF流入数据
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    - **date**: 日期 (格式: YYYY-MM-DD)
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型")
    
    # 验证日期格式
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    
    flow = db.get_flow_by_date(etf_type, date)
    
    if not flow:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的数据")
    
    return DailyFlowResponse(
        etf_type=flow.etf_type,
        date=flow.date,
        total_flow=flow.total_flow,
        price_usd=flow.price_usd,
        ticker_flows=flow.ticker_flows,
    )


@app.get("/api/etf/{etf_type}/ticker/{ticker}", response_model=List[TickerFlowResponse])
async def get_flows_by_ticker(
    etf_type: str,
    ticker: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """
    按机构查询ETF流入数据
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    - **ticker**: 机构代码 (如 IBIT, FBTC)
    - **days**: 查询天数
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型")
    
    flows = db.get_flows_by_ticker(etf_type, ticker.upper(), days)
    
    if not flows:
        raise HTTPException(status_code=404, detail=f"未找到机构 {ticker} 的数据")
    
    return [TickerFlowResponse(**f) for f in flows]


@app.get("/api/etf/{etf_type}/summary", response_model=SummaryResponse)
async def get_summary(etf_type: str):
    """
    获取ETF汇总统计
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型")
    
    summary = db.get_summary(etf_type)
    
    if not summary.trading_days:
        raise HTTPException(status_code=404, detail="暂无数据，请先执行爬取")
    
    return SummaryResponse(**summary.to_dict())


@app.post("/api/scrape/{etf_type}", response_model=ScrapeResponse)
async def scrape_etf(etf_type: str, headless: bool = True):
    """
    手动触发ETF数据爬取
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    - **headless**: 是否使用无头模式
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型")
    
    try:
        scraper = get_scraper(etf_type)
        flows = scraper.scrape(headless=headless, save=True)
        
        return ScrapeResponse(
            success=True,
            message=f"成功爬取 {etf_type.upper()} ETF 数据",
            records_count=len(flows),
        )
        
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etf/{etf_type}/tickers")
async def get_ticker_summary(etf_type: str):
    """
    获取各机构累计流入汇总
    
    - **etf_type**: ETF类型 (btc/eth/sol)
    """
    etf_type = etf_type.lower()
    if etf_type not in ["btc", "eth", "sol"]:
        raise HTTPException(status_code=400, detail="不支持的ETF类型")
    
    tickers = db.get_ticker_summary(etf_type)
    
    return {
        "etf_type": etf_type,
        "tickers": tickers,
    }


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动API服务"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
