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
    from playwright.async_api import async_playwright, Browser, Page, Locator
except ImportError:
    raise ImportError("请安装 playwright: pip install playwright && playwright install chromium")


class PANewsCrawler:
    """PANews 重要资讯爬虫"""
    
    BASE_URL = "https://www.panewslab.com/zh/newsflash"
    
    # Selectors
    SEL_NEWS_ITEM_CONTAINER = '.news-item-container, .panews-flash-item'  # Generic fallback
    SEL_IMPORTANT_FILTER_BTN = 'text="只看重要"'
    SEL_POPUP_CLOSE_BTN = 'button[aria-label="close"], .close-btn, [class*="close"]'
    SEL_ONESIGNAL_CANCEL = '#onesignal-slidedown-cancel-button'
    
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
                # Remove query params if any
                article_id = article_id.split('?')[0]
                return hashlib.md5(article_id.encode()).hexdigest()[:12]
        
        # 备用：使用 title + time
        content = f"{title}_{time_str}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _close_popups(self, page: Page):
        """关闭各种弹窗 (带超时保护)"""
        try:
            # 1. OneSignal
            try:
                # Using locator instead of query_selector for auto-waiting if needed, 
                # but for popups we usually want short timeout.
                os_btn = page.locator(self.SEL_ONESIGNAL_CANCEL)
                if await os_btn.is_visible(timeout=2000):
                    await os_btn.click()
            except Exception:
                pass

            # 2. Generic Popups
            # Try finding close buttons
            for _ in range(3): # Retry a few times quickly
                try:
                    # Look for common close buttons
                    close_btn = page.locator(self.SEL_POPUP_CLOSE_BTN).first
                    if await close_btn.is_visible(timeout=1000):
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                    else:
                        break
                except Exception:
                    break
        except Exception as e:
            print(f"关闭弹窗时警告: {e}")
    
    async def _enable_important_filter(self, page: Page):
        """启用"只看重要"筛选"""
        print("尝试点击 '只看重要'...")
        try:
            # 使用 Playwright 的 text selector，非常健壮
            # We wait a bit longer here because the filter button might render late
            filter_btn = page.locator(self.SEL_IMPORTANT_FILTER_BTN).first
            
            # Check if already active? Hard to tell without specific class. 
            # Usually clicking it enables it.
            
            if await filter_btn.is_visible(timeout=5000):
                await filter_btn.click()
                print("已点击筛选按钮")
                # Wait for list to update - hard to detect, just wait a bit or wait for network idle
                await page.wait_for_load_state("networkidle", timeout=3000)
                await asyncio.sleep(1.0) 
            else:
                print("⚠️ 未找到 '只看重要' 按钮，可能已改版或默认已选")
                
                # Fallback: Try button id "v-0-0" seen in old code
                fallback_btn = page.locator("button#v-0-0")
                if await fallback_btn.is_visible(timeout=2000):
                     await fallback_btn.click()
                     print("已点击 fallback 筛选按钮")

        except Exception as e:
            print(f"启用筛选器失败: {e}")
    
    async def _extract_news(self, page: Page) -> list[dict]:
        """从页面提取新闻列表 - 只抓取有时间的快讯，按日期+时间排序"""
        # We define the evaluation script separately for cleanliness
        # This script runs in the browser context
        extract_script = r'''
            () => {
                const results = [];
                const timeRegex = /^\d{1,2}:\d{2}$/;
                
                // Helper to finding the news container
                // PANews structure usually: ... -> div.item -> [ time, content... ]
                // We scan for time elements as anchors
                
                const allElements = document.querySelectorAll('*');
                
                for (const el of allElements) {
                    // Optimization: Skip container elements immediately
                    if (el.tagName === 'DIV' || el.tagName === 'SECTION' || el.tagName === 'MAIN') {
                        if (el.children.length > 5) continue; // heuristic
                    }
                    if (el.children.length > 1) continue; // leaf nodes or close to leaf

                    const text = el.textContent?.trim();
                    if (!text || !timeRegex.test(text)) continue;
                    
                    // Exclude sidebars
                    if (el.closest('aside') || el.closest('nav') || el.closest('.footer')) continue;
                    
                    const timeStr = text;
                    
                    // Found a time string (e.g. "14:24"). logic triggers.
                    // Walk up to find the container
                    let container = el.parentElement;
                    let foundNews = false;
                    
                    for (let i = 0; i < 6 && container; i++) {
                        // Look for links inside this container
                        const linkEl = container.querySelector('a[href*="/newsflash/"], a[href*="/articles/"]');
                        if (!linkEl) {
                            container = container.parentElement;
                            continue;
                        }

                        const title = linkEl.textContent?.trim();
                        if (!title || title.length < 2) {
                             container = container.parentElement;
                             continue;
                        }
                        
                        const href = linkEl.href;
                        
                        // Extract content/desc
                        // Heuristic: sibling of title, or inside container but not title/time
                        // Often text-neutrals-60 or similar
                        let content = "";
                        const contentEl = container.querySelector('.line-clamp-3, .line-clamp-2, p, [class*="content"]');
                        if (contentEl && contentEl !== linkEl) {
                            content = contentEl.textContent?.trim() || "";
                        }
                        
                        // Clean content if it starts with title
                        if (content.startsWith(title)) {
                            content = content.slice(title.length).trim();
                        }

                        // Determine Date
                        // Try to find date in the text (e.g. description often starts with "PANews 1月16日消息")
                        let dateMatch = content.match(/(\d{1,2})月(\d{1,2})日/);
                        if (!dateMatch) {
                            // Try container text
                            dateMatch = container.textContent.match(/(\d{1,2})月(\d{1,2})日/);
                        }
                        
                        const now = new Date();
                        let year = now.getFullYear();
                        let month = now.getMonth() + 1;
                        let day = now.getDate();
                        
                        if (dateMatch) {
                            month = parseInt(dateMatch[1]);
                            day = parseInt(dateMatch[2]);
                            
                            // Year transition logic
                            // If news month is 12 and current month is 1, assume last year
                            // Or more generally, if news date is "in the future" by more than a day, it's likely last year
                            const currentTs = now.getTime();
                            const newsDateCurrentYear = new Date(year, month - 1, day);
                            
                            // 30 days buffer for safe check (e.g. clock skew or timezone)
                            // If news date (current year) is > now + 2 days, it's probably last year
                            if (newsDateCurrentYear.getTime() > currentTs + 86400000 * 2) {
                                year -= 1;
                            }
                        }
                        
                        const fullDateTime = `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')} ${timeStr}`;
                        
                        // Check exact important tag
                        const isImportant = container.querySelector('.bg-brand-primary, [class*="important"]') !== null || 
                                          (container.textContent && container.textContent.includes('重要')); 

                        // Avoid duplicates in this batch
                        if (!results.some(r => r.link === href)) {
                            results.push({
                                time: timeStr,
                                title: title,
                                content: content,
                                link: href,
                                isImportant: isImportant,
                                publishDateTime: fullDateTime
                            });
                        }
                        
                        foundNews = true;
                        break; // Found for this time element
                    }
                    if (foundNews) continue;
                }
                return results;
            }
        '''
        try:
            # Wait for content to actually be there specifically
            # We look for something that looks like news content
            await page.wait_for_selector('a[href*="/newsflash/"]', timeout=5000)
        except:
            print("⚠️超时: 页面可能未加载完全")

        news_list = await page.evaluate(extract_script)
        return news_list
    
    async def fetch_important_news(self, only_new: bool = True, save_to_db: bool = True, timeout: int = 300) -> list[dict]:
        """
        获取重要快讯 (带超时保护)
        
        Args:
            only_new: 是否只返回新的（未见过的）新闻
            save_to_db: 是否保存到数据库
            timeout: 最大执行时间（秒），默认5分钟
            
        Returns:
            新闻列表，每条包含 time, title, content, link, id
        """
        try:
            return await asyncio.wait_for(
                self._fetch_important_news_impl(only_new, save_to_db),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print(f"⚠️ 爬取超时 (超过 {timeout} 秒)，强制终止")
            return []
        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            return []
    
    async def _fetch_important_news_impl(self, only_new: bool = True, save_to_db: bool = True) -> list[dict]:
        """实际执行爬取操作的内部方法"""
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--disable-blink-features=AutomationControlled'] # 防止被检测
                )
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                print(f"正在访问 {self.BASE_URL}...")
                response = await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
                if not response:
                    print("❌ 无法加载页面 (Response is None)")
                    return []
                    
                # 等待基本的快讯元素出现，而不是死等sleep
                try:
                    await page.wait_for_selector('.list-content, .news-list, body', state='visible', timeout=10000)
                except:
                    pass

                # 关闭弹窗
                await self._close_popups(page)
                
                # 启用"只看重要"筛选
                await self._enable_important_filter(page)
                
                # 再次等待，确保列表刷新
                await asyncio.sleep(1.0) # Small buffer
                
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
                
        except asyncio.CancelledError:
            print("⚠️ 爬取任务被取消")
            raise
        except Exception as e:
            print(f"爬取失败: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # 确保浏览器被关闭
            if browser:
                try:
                    await browser.close()
                    print("🧹 浏览器已关闭")
                except Exception:
                    pass
    
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
        print(f"\n⏰ {item['publishDateTime']}")
        print(f"📰 {item['title']}")
        if item.get('content'):
            print(f"   {item['content'][:100]}...")
        print(f"🔗 {item['link']}")
