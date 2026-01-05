"""
PANews Crawler - 获取 PANews 重要快讯
https://www.panewslab.com/zh/newsflash
"""

import asyncio
import json
import hashlib
from datetime import datetime
from typing import Optional
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Browser, Page
except ImportError:
    raise ImportError("请安装 playwright: pip install playwright && playwright install chromium")


class PANewsCrawler:
    """PANews 重要资讯爬虫"""
    
    BASE_URL = "https://www.panewslab.com/zh/newsflash"
    
    def __init__(self, headless: bool = True, cache_dir: Optional[str] = None):
        """
        初始化爬虫
        
        Args:
            headless: 是否无头模式运行浏览器
            cache_dir: 缓存目录，用于去重
        """
        self.headless = headless
        self.cache_dir = Path(cache_dir) if cache_dir else Path("./data/panews_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._seen_ids_file = self.cache_dir / "seen_ids.json"
        self._seen_ids: set = self._load_seen_ids()
    
    def _load_seen_ids(self) -> set:
        """加载已爬取的新闻ID"""
        if self._seen_ids_file.exists():
            with open(self._seen_ids_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def _save_seen_ids(self):
        """保存已爬取的新闻ID"""
        with open(self._seen_ids_file, 'w') as f:
            json.dump(list(self._seen_ids), f)
    
    def _generate_id(self, title: str, time_str: str, link: str = '') -> str:
        """
        生成新闻唯一ID
        优先使用 link (文章URL) 作为唯一标识
        """
        # 优先使用 link，这是最可靠的唯一标识
        if link:
            # 从 link 中提取文章 ID
            # 例如: https://www.panewslab.com/zh/articles/abc123 -> abc123
            article_id = link.rstrip('/').split('/')[-1]
            if article_id and len(article_id) > 5:
                return hashlib.md5(article_id.encode()).hexdigest()[:12]
        
        # 备用：使用 title + time
        content = f"{title}_{time_str}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _close_popups(self, page: Page):
        """关闭各种弹窗"""
        try:
            # 关闭 OneSignal 订阅弹窗
            cancel_btn = await page.query_selector('#onesignal-slidedown-cancel-button')
            if cancel_btn:
                await cancel_btn.click()
                await asyncio.sleep(0.5)
            
            # 关闭公告弹窗 (点击关闭按钮或背景)
            close_btns = await page.query_selector_all('button[aria-label="close"], .close-btn, [class*="close"]')
            for btn in close_btns:
                try:
                    await btn.click()
                    await asyncio.sleep(0.3)
                except:
                    pass
        except Exception as e:
            print(f"关闭弹窗时出错: {e}")
    
    async def _enable_important_filter(self, page: Page):
        """启用"只看重要"筛选"""
        try:
            # 方法1: 直接点击筛选按钮 (根据 DOM 分析结果)
            result = await page.evaluate('''
                () => {
                    // 方法1: 使用 button#v-0-0 (只看重要按钮)
                    const filterBtn = document.querySelector('button#v-0-0');
                    if (filterBtn) {
                        filterBtn.click();
                        return "button_clicked";
                    }
                    
                    // 方法2: 查找包含"只看重要"文本的元素
                    const elements = document.querySelectorAll('label, span, div, button');
                    for (const el of elements) {
                        if (el.textContent?.trim() === '只看重要') {
                            el.click();
                            return "text_clicked";
                        }
                    }
                    
                    // 方法3: 查找 checkbox
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    for (const cb of checkboxes) {
                        const label = cb.closest('label') || cb.nextElementSibling;
                        if (label?.textContent?.includes('只看重要')) {
                            if (!cb.checked) cb.click();
                            return "checkbox_clicked";
                        }
                    }
                    
                    return "not_found";
                }
            ''')
            print(f"筛选器状态: {result}")
            await asyncio.sleep(2)  # 等待筛选生效
        except Exception as e:
            print(f"启用筛选器失败: {e}")
    
    async def _extract_news(self, page: Page) -> list[dict]:
        """从页面提取新闻列表 - 只抓取有时间的快讯，按日期+时间排序"""
        news_list = await page.evaluate(r'''
            () => {
                const results = [];
                const timeRegex = /^\d{1,2}:\d{2}$/;
                
                // 找到所有时间元素
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length > 0) continue;
                    const timeText = el.textContent?.trim();
                    if (!timeText || !timeRegex.test(timeText)) continue;
                    if (el.closest('aside') || el.closest('nav') || el.closest('[class*="sidebar"]')) continue;
                    
                    const time = timeText;
                    
                    // 向上查找新闻内容
                    let container = el.parentElement;
                    for (let i = 0; i < 5 && container; i++) {
                        const link = container.querySelector('a[href*="/articles/"], a[href*="/newsflash/"]');
                        if (link) {
                            const title = link.textContent?.trim();
                            const href = link.href || link.getAttribute('href') || '';
                            
                            if (!title || title.length < 5) {
                                container = container.parentElement;
                                continue;
                            }
                            
                            const descEl = container.querySelector('div.text-neutrals-60, div.line-clamp-3, div.line-clamp-2, p');
                            let description = descEl?.textContent?.trim() || '';
                            if (description.startsWith(title)) {
                                description = description.slice(title.length).trim();
                            }
                            
                            // 从摘要中提取日期 (PANews 1月5日消息 -> 1月5日)
                            let dateNum = 0;  // 用于排序的日期数值
                            const dateMatch = description.match(/(\d{1,2})月(\d{1,2})日/);
                            if (dateMatch) {
                                const month = parseInt(dateMatch[1]);
                                const day = parseInt(dateMatch[2]);
                                dateNum = month * 100 + day;  // 105 = 1月5日
                            }
                            
                            const hasImportantTag = container.querySelector('span.bg-brand-primary, [class*="tag"]') !== null;
                            
                            if (results.some(r => r.link === href)) break;
                            
                            const [h, m] = time.split(':').map(Number);
                            
                            results.push({
                                time,
                                title,
                                content: description,
                                link: href,
                                isImportant: hasImportantTag,
                                _dateNum: dateNum,
                                _timeNum: h * 60 + m
                            });
                            break;
                        }
                        container = container.parentElement;
                    }
                }
                
                // 排序：日期降序（大的在前），同日时间降序
                results.sort((a, b) => {
                    if (a._dateNum !== b._dateNum) {
                        return b._dateNum - a._dateNum;  // 日期大的在前 (1月5日 > 1月4日)
                    }
                    return b._timeNum - a._timeNum;  // 时间大的在前 (12:45 > 11:00)
                });
                
                // 移除排序键
                results.forEach(r => {
                    delete r._dateNum;
                    delete r._timeNum;
                });
                
                return results;
            }
        ''')
        return news_list
    
    async def fetch_important_news(self, only_new: bool = True, save_to_db: bool = True) -> list[dict]:
        """
        获取重要快讯
        
        Args:
            only_new: 是否只返回新的（未见过的）新闻
            save_to_db: 是否保存到数据库
            
        Returns:
            新闻列表，每条包含 time, title, content, link, id
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                print(f"正在访问 {self.BASE_URL}...")
                await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(5)  # 等待JS渲染完成
                
                # 关闭弹窗
                await self._close_popups(page)
                
                # 启用"只看重要"筛选
                await self._enable_important_filter(page)
                
                # 等待内容加载
                await asyncio.sleep(2)
                
                # 提取新闻
                news_list = await self._extract_news(page)
                print(f"共抓取到 {len(news_list)} 条资讯")
                
                # 处理结果
                results = []
                for news in news_list:
                    news_id = self._generate_id(news['title'], news.get('time', ''), news.get('link', ''))
                    
                    if only_new and news_id in self._seen_ids:
                        continue
                    
                    news['id'] = news_id
                    news['crawled_at'] = datetime.now().isoformat()
                    news['source'] = 'PANews'
                    results.append(news)
                    
                    self._seen_ids.add(news_id)
                
                # 保存已见ID
                self._save_seen_ids()
                
                # 保存到数据库
                if save_to_db and results:
                    from .storage import get_storage
                    storage = get_storage()
                    inserted = storage.save_news(results)
                    print(f"💾 保存 {inserted} 条新资讯到数据库")
                    # 清理过期数据
                    storage.cleanup_expired()
                
                print(f"其中 {len(results)} 条为新资讯")
                return results
                
            except Exception as e:
                print(f"爬取失败: {e}")
                raise
            finally:
                await browser.close()
    
    def fetch_sync(self, only_new: bool = True, save_to_db: bool = True) -> list[dict]:
        """
        同步版本的获取方法
        
        Args:
            only_new: 只返回新资讯
            save_to_db: 是否保存到数据库
        """
        return asyncio.run(self.fetch_important_news(only_new, save_to_db))


# 命令行测试
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='PANews 重要资讯爬虫')
    parser.add_argument('--no-headless', action='store_true', help='显示浏览器窗口')
    parser.add_argument('--all', action='store_true', help='获取所有资讯，不去重')
    args = parser.parse_args()
    
    crawler = PANewsCrawler(headless=not args.no_headless)
    news = crawler.fetch_sync(only_new=not args.all)
    
    print("\n" + "="*60)
    print(f"获取到 {len(news)} 条重要资讯:")
    print("="*60)
    
    for item in news:
        print(f"\n⏰ {item['time']}")
        print(f"📰 {item['title']}")
        if item['content']:
            print(f"   {item['content'][:100]}...")
        print(f"🔗 {item['link']}")
