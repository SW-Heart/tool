"""
通用工具函数
"""
from datetime import datetime, timezone
from typing import Optional
import time


def time_ago(timestamp: datetime) -> str:
    """
    将时间戳转换为 "X mins ago" 格式
    
    Args:
        timestamp: datetime 对象
    
    Returns:
        人类可读的时间差描述
    """
    now = datetime.now(timezone.utc)
    
    # 确保 timestamp 是 UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    diff = now - timestamp
    seconds = int(diff.total_seconds())
    
    if seconds < 60:
        return f"{seconds} secs ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day{'s' if days > 1 else ''} ago"
    else:
        return timestamp.strftime("%Y-%m-%d")


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """
    解析多种格式的时间戳字符串
    
    Args:
        ts_str: 时间戳字符串
    
    Returns:
        datetime 对象或 None
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a %b %d %H:%M:%S %z %Y",  # Twitter 格式
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    
    return None


def get_random_user_agent() -> str:
    """
    返回随机 User-Agent 字符串
    """
    import random
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    return random.choice(user_agents)
