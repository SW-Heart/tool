"""
X-Alpha 数据存储模块
使用 SQLite 存储信号数据
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.logger import setup_logger

logger = setup_logger("x_alpha.storage")


class Database:
    """
    X-Alpha 数据库操作类
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alpha_signals (
                    id VARCHAR(64) PRIMARY KEY,
                    author VARCHAR(50) NOT NULL,
                    avatar_url VARCHAR(255),
                    raw_content TEXT NOT NULL,
                    ai_summary TEXT,
                    assets TEXT,
                    signal VARCHAR(10),
                    sentiment INTEGER DEFAULT 5,
                    tweet_url VARCHAR(255),
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_author ON alpha_signals(author)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signal ON alpha_signals(signal)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sentiment ON alpha_signals(sentiment)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON alpha_signals(created_at)")
            
            # 创建元数据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key VARCHAR(50) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
        
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def exists(self, tweet_id: str) -> bool:
        """检查推文是否已存在"""
        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT 1 FROM alpha_signals WHERE id = ?",
                (tweet_id,)
            ).fetchone()
            return result is not None
    
    def save_signal(self, data: Dict[str, Any]) -> bool:
        """
        保存信号数据
        
        Args:
            data: 信号数据字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO alpha_signals 
                    (id, author, avatar_url, raw_content, ai_summary, assets, signal, sentiment, tweet_url, tags, created_at, published_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("id"),
                    data.get("author"),
                    data.get("avatar_url"),
                    data.get("content") or data.get("raw_content"),
                    data.get("summary_zh") or data.get("ai_summary"),
                    json.dumps(data.get("related_assets") or data.get("assets") or []),
                    data.get("signal_type") or data.get("signal"),
                    data.get("sentiment_score") or data.get("sentiment", 5),
                    data.get("tweet_url"),
                    json.dumps(data.get("tags") or []),
                    datetime.utcnow().isoformat(),
                    data.get("published_at").isoformat() if isinstance(data.get("published_at"), datetime) else data.get("published_at"),
                ))
                conn.commit()
            
            logger.debug(f"保存信号: {data.get('id')} - {data.get('signal_type')}")
            return True
            
        except Exception as e:
            logger.error(f"保存信号失败: {e}")
            return False
    
    def get_signals(
        self,
        limit: int = 20,
        min_sentiment: Optional[int] = None,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询信号列表
        
        Args:
            limit: 返回条数
            min_sentiment: 最低情绪分
            symbol: 筛选币种
            signal_type: 筛选信号类型
            author: 筛选作者
            
        Returns:
            信号列表
        """
        query = "SELECT * FROM alpha_signals WHERE 1=1"
        params = []
        
        if min_sentiment is not None:
            query += " AND sentiment >= ?"
            params.append(min_sentiment)
        
        if signal_type:
            query += " AND signal = ?"
            params.append(signal_type.upper())
        
        if author:
            query += " AND author = ?"
            params.append(author)
        
        if symbol:
            query += " AND assets LIKE ?"
            params.append(f'%"{symbol.upper()}"%')
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "id": row["id"],
            "author": row["author"],
            "avatar_url": row["avatar_url"],
            "raw_content": row["raw_content"],
            "ai_summary": row["ai_summary"],
            "assets": json.loads(row["assets"]) if row["assets"] else [],
            "signal": row["signal"],
            "sentiment": row["sentiment"],
            "tweet_url": row["tweet_url"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "created_at": row["created_at"],
            "published_at": row["published_at"],
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM alpha_signals").fetchone()[0]
            
            by_signal = {}
            for row in conn.execute("SELECT signal, COUNT(*) as cnt FROM alpha_signals GROUP BY signal"):
                by_signal[row["signal"]] = row["cnt"]
            
            last_scan = conn.execute(
                "SELECT value FROM metadata WHERE key = 'last_scan_time'"
            ).fetchone()
            
            return {
                "total_signals": total,
                "by_signal": by_signal,
                "last_scan_time": last_scan["value"] if last_scan else None,
            }
    
    def set_metadata(self, key: str, value: str):
        """设置元数据"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.utcnow().isoformat()))
            conn.commit()
    
    def get_metadata(self, key: str) -> Optional[str]:
        """获取元数据"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else None
