"""
X-Alpha 智能舆情服务配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库配置
DATABASE_PATH = BASE_DIR / "data" / "x_alpha.db"

# API 配置
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8002,
    "reload": False,
}

# API 鉴权
API_SECRET_KEY = os.getenv("X_ALPHA_API_KEY", "")

# DeepSeek 配置
DEEPSEEK_CONFIG = {
    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "model": "deepseek-chat",
    "timeout": 60,
    "max_retries": 3,
}

# 默认轮询间隔 (秒)
DEFAULT_POLL_INTERVAL = 900

# Twitter 采集配置
COLLECTOR_CONFIG = {
    "poll_interval": int(os.getenv("X_ALPHA_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL))),  # 15分钟
    "request_timeout": 60,  # 增加超时时间
    "max_retries": 3,
    "retry_delay": 10,  # 增加重试间隔
    "cookies": os.getenv("X_ALPHA_COOKIES", ""),  # 新增: 支持自定义 Cookie 以绕过限流
}

# 监控的 KOL 列表 (带标签)
# 格式: {"username": "用户名", "tags": ["标签1", "标签2"], "priority": 1-3}
TARGET_USERS = [
    # === 行业大佬 ===
    {"username": "elonmusk", "tags": ["大佬", "DOGE", "TSLA", "AI"], "priority": 1},
    {"username": "VitalikButerin", "tags": ["大佬", "ETH", "DeFi"], "priority": 1},
    {"username": "cabornsco", "tags": ["大佬", "BTC", "宏观"], "priority": 1},
    {"username": "michael_saylor", "tags": ["大佬", "BTC", "机构"], "priority": 1},
    
    # === 交易所/机构 ===
    {"username": "binance", "tags": ["交易所", "公告"], "priority": 2},
    {"username": "coinabornsco", "tags": ["交易所", "公告"], "priority": 2},
    {"username": "Grayscale", "tags": ["机构", "ETF", "BTC"], "priority": 2},
    {"username": "BlackRock", "tags": ["机构", "ETF", "传统金融"], "priority": 2},
    
    # === 分析师/交易员 ===
    {"username": "CryptoCred", "tags": ["分析师", "技术分析"], "priority": 2},
    {"username": "CryptoCapo_", "tags": ["分析师", "BTC", "山寨币"], "priority": 2},
    {"username": "lookonchain", "tags": ["链上数据", "巨鲸追踪"], "priority": 1},
    {"username": "spoabornsconomics", "tags": ["链上数据", "研究"], "priority": 2},
    
    # === 宏观/美股 ===
    {"username": "zabornsckworks", "tags": ["宏观", "美股", "科技股"], "priority": 2},
    {"username": "federalreserve", "tags": ["宏观", "美联储", "利率"], "priority": 1},
    
    # === 项目方 ===
    {"username": "solana", "tags": ["项目", "SOL", "L1"], "priority": 2},
    {"username": "ethereum", "tags": ["项目", "ETH", "L1"], "priority": 2},
]

# 从环境变量追加用户 (逗号分隔)
extra_users = os.getenv("X_ALPHA_TARGET_USERS", "")
if extra_users:
    for username in extra_users.split(","):
        username = username.strip()
        if username and not any(u["username"] == username for u in TARGET_USERS):
            TARGET_USERS.append({
                "username": username,
                "tags": ["自定义"],
                "priority": 3,
            })

# 日志配置
LOG_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "api_log": BASE_DIR / "logs" / "api.log",
    "worker_log": BASE_DIR / "logs" / "worker.log",
}

# 确保必要目录存在
def ensure_dirs():
    (BASE_DIR / "data").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

ensure_dirs()
