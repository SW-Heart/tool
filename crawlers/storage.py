"""
新闻数据存储层 - SQLite
规则：只保留24小时内的数据，过期自动清理
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class NewsStorage:
    """新闻数据存储 - 24小时滚动窗口"""
    
    # 数据保留时间（小时）
    RETENTION_HOURS = 24
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else Path("./data/news.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    link TEXT,
                    publish_time TEXT,
                    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_important BOOLEAN DEFAULT 0,
                    extra_data TEXT
                )
            ''')
            # 创建索引加速查询
            conn.execute('CREATE INDEX IF NOT EXISTS idx_crawled_at ON news(crawled_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_source ON news(source)')
            # 添加 link 唯一索引防止重复
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_link ON news(link)')
    
    def save_news(self, news_list: list[dict]) -> int:
        """
        保存新闻列表
        
        Args:
            news_list: 新闻列表
            
        Returns:
            新增的条数
        """
        inserted = 0
        with self._get_conn() as conn:
            for news in news_list:
                try:
                    conn.execute('''
                        INSERT OR IGNORE INTO news 
                        (id, source, title, content, link, publish_time, crawled_at, is_important, extra_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        news.get('id'),
                        news.get('source', 'unknown'),
                        news.get('title', ''),
                        news.get('content', ''),
                        news.get('link', ''),
                        news.get('time', ''),
                        news.get('crawled_at', datetime.now().isoformat()),
                        1 if news.get('isImportant') else 0,
                        json.dumps(news.get('extra', {}), ensure_ascii=False)
                    ))
                    if conn.total_changes > 0:
                        inserted += 1
                except sqlite3.IntegrityError:
                    pass  # 重复数据跳过
        
        return inserted
    
    def get_latest_news(self, limit: int = 20, source: Optional[str] = None) -> list[dict]:
        """
        获取最新新闻
        
        Args:
            limit: 返回条数
            source: 来源筛选（如 'PANews'）
            
        Returns:
            新闻列表
        """
        with self._get_conn() as conn:
            if source:
                cursor = conn.execute('''
                    SELECT * FROM news 
                    WHERE source = ? 
                    ORDER BY crawled_at DESC 
                    LIMIT ?
                ''', (source, limit))
            else:
                cursor = conn.execute('''
                    SELECT * FROM news 
                    ORDER BY crawled_at DESC 
                    LIMIT ?
                ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_news_since(self, since_id: str) -> list[dict]:
        """
        获取某条新闻之后的所有新闻
        
        Args:
            since_id: 起始新闻ID（不包含）
            
        Returns:
            新闻列表
        """
        with self._get_conn() as conn:
            # 先获取该ID的时间
            cursor = conn.execute(
                'SELECT crawled_at FROM news WHERE id = ?', 
                (since_id,)
            )
            row = cursor.fetchone()
            if not row:
                return []
            
            since_time = row['crawled_at']
            
            cursor = conn.execute('''
                SELECT * FROM news 
                WHERE crawled_at > ? 
                ORDER BY crawled_at ASC
            ''', (since_time,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_expired(self) -> int:
        """
        清理过期数据（超过24小时）
        
        Returns:
            删除的条数
        """
        cutoff_time = datetime.now() - timedelta(hours=self.RETENTION_HOURS)
        
        with self._get_conn() as conn:
            cursor = conn.execute(
                'DELETE FROM news WHERE crawled_at < ?',
                (cutoff_time.isoformat(),)
            )
            deleted = cursor.rowcount
        
        if deleted > 0:
            print(f"🧹 清理了 {deleted} 条过期新闻（超过 {self.RETENTION_HOURS} 小时）")
        
        return deleted
    
    def get_stats(self) -> dict:
        """获取存储统计信息"""
        with self._get_conn() as conn:
            cursor = conn.execute('SELECT COUNT(*) as total FROM news')
            total = cursor.fetchone()['total']
            
            cursor = conn.execute('''
                SELECT source, COUNT(*) as count 
                FROM news 
                GROUP BY source
            ''')
            by_source = {row['source']: row['count'] for row in cursor.fetchall()}
            
            cursor = conn.execute('''
                SELECT MIN(crawled_at) as oldest, MAX(crawled_at) as newest 
                FROM news
            ''')
            row = cursor.fetchone()
            
            return {
                'total': total,
                'by_source': by_source,
                'oldest': row['oldest'],
                'newest': row['newest'],
                'retention_hours': self.RETENTION_HOURS
            }


# 全局单例
_storage_instance: Optional[NewsStorage] = None

def get_storage() -> NewsStorage:
    """获取存储单例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = NewsStorage()
    return _storage_instance


if __name__ == "__main__":
    # 测试
    storage = NewsStorage()
    
    # 测试数据
    test_news = [
        {
            'id': 'test001',
            'source': 'PANews',
            'title': '测试新闻标题',
            'content': '这是测试内容',
            'link': 'https://example.com',
            'time': '12:00',
            'crawled_at': datetime.now().isoformat()
        }
    ]
    
    inserted = storage.save_news(test_news)
    print(f"插入 {inserted} 条")
    
    latest = storage.get_latest_news(limit=5)
    print(f"最新 {len(latest)} 条:")
    for n in latest:
        print(f"  - {n['title']}")
    
    stats = storage.get_stats()
    print(f"统计: {stats}")
