"""
X-Alpha 数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    """信号类型枚举"""
    BUY = "BUY"
    SELL = "SELL"
    WATCH = "WATCH"
    NEUTRAL = "NEUTRAL"


class Tweet(BaseModel):
    """推文数据模型"""
    id: str
    author: str
    avatar_url: Optional[str] = None
    content: str
    tweet_url: str
    published_at: datetime
    
    class Config:
        from_attributes = True


class AnalysisResult(BaseModel):
    """AI 分析结果"""
    is_relevant: bool = False
    sentiment_score: int = Field(default=5, ge=0, le=10)
    related_assets: List[str] = Field(default_factory=list)
    signal_type: SignalType = SignalType.NEUTRAL
    summary_zh: str = ""


class Signal(BaseModel):
    """完整的信号数据"""
    id: str
    author: str
    avatar_url: Optional[str] = None
    raw_content: str
    ai_summary: str
    assets: List[str]
    signal: SignalType
    sentiment: int
    tweet_url: str
    created_at: datetime
    published_at: datetime
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    """API 响应格式"""
    id: str
    author: str
    avatar_url: Optional[str] = None
    summary: str
    original_text: str
    signal: str
    sentiment: int
    assets: List[str]
    tweet_url: str
    time_ago: str
    publish_timestamp: int
    tags: List[str] = Field(default_factory=list)


class APIResponse(BaseModel):
    """统一 API 响应格式"""
    status: str = "success"
    timestamp: int
    data: List[SignalResponse] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    db_connected: bool = True
    last_scan_time: Optional[str] = None
    monitored_users: List[str] = Field(default_factory=list)
    total_signals: int = 0
