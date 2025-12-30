"""
Farside ETF 爬虫服务器配置
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库配置
DATABASE_PATH = BASE_DIR / "data" / "etf_data.db"

# 爬虫配置
SCRAPER_CONFIG = {
    "headless": True,           # 无头模式
    "timeout": 60,              # 页面加载超时(秒) - 增加到60秒
    "retry_count": 5,           # 重试次数 - 增加到5次
    "retry_delay": 5,           # 重试间隔(秒)
    "request_delay": 2,         # 请求间隔(秒)
}

# Farside 网站URL
FARSIDE_URLS = {
    "btc": "https://farside.co.uk/btc/",
    "eth": "https://farside.co.uk/eth/",
    "sol": "https://farside.co.uk/sol/",
}

# ETF机构列表
ETF_TICKERS = {
    "btc": ["IBIT", "FBTC", "BITB", "ARKB", "BTCO", "EZBC", "BRRR", "HODL", "BTCW", "GBTC", "BTC"],
    "eth": ["ETHA", "FETH", "ETHW", "CETH", "ETHV", "QETH", "EZET", "ETHE", "ETH"],
    "sol": ["BSOL", "VSOL", "FSOL", "TSOL", "SOEZ", "GSOL"],
}

# API配置
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": True,
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": BASE_DIR / "logs" / "etf_scraper.log",
}

# 确保必要目录存在
def ensure_dirs():
    """创建必要的目录"""
    (BASE_DIR / "data").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

ensure_dirs()
