"""
Playwright 浏览器驱动
替代 Selenium/Undetected-Chromedriver
"""
import logging
import time
from typing import Optional, Any
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Browser, Page

from config import SCRAPER_CONFIG

logger = logging.getLogger(__name__)


class PlaywrightDriver:
    """Playwright 驱动适配器 (同步版)"""
    
    def __init__(self, headless: bool = None):
        self.headless = headless if headless is not None else SCRAPER_CONFIG["headless"]
        self.timeout = SCRAPER_CONFIG["timeout"] * 1000  # Playwright uses ms
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context = None
        self._page: Optional[Page] = None
        
    def start(self):
        """启动浏览器"""
        if self._playwright:
            return

        self._playwright = sync_playwright().start()
        
        # 启动浏览器
        # args 添加防检测参数
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 创建上下文，设置 User-Agent 和 Viewport
        self._context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 增加防止被检测的脚本
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout)
            
    def get(self, url: str, wait_for_selector: str = None) -> bool:
        """访问页面"""
        if not self._page:
            self.start()
            
        try:
            logger.info(f"正在访问: {url}")
            # 使用 networkidle 等待网络请求完成 (更稳，但要注意有些页面一直有请求)
            # 或者先 domcontentloaded 然后手动 scroll
            response = self._page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            
            if not response:
                logger.error("页面无响应")
                return False
                
            # 模拟用户滚动到底部以触发懒加载
            try:
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                self._page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
                
            # 简单的反爬虫绕过等待
            time.sleep(5)  # 增加等待时间到 5 秒
            
            if wait_for_selector:
                self._page.wait_for_selector(wait_for_selector, state='attached', timeout=self.timeout)
                
            logger.info("页面加载成功")
            return True
            
        except Exception as e:
            logger.error(f"页面加载失败: {e}")
            return False
            
    def get_page_source(self) -> str:
        """获取页面源码"""
        if self._page:
            return self._page.content()
        return ""
        
    def save_screenshot(self, path: str) -> bool:
        """保存截图"""
        try:
            if self._page:
                self._page.screenshot(path=path)
                return True
        except Exception as e:
            logger.error(f"截图失败: {e}")
        return False

    def save_page_source(self, path: str) -> bool:
        """保存源码文件"""
        try:
            content = self.get_page_source()
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"保存源码失败: {e}")
        return False
        
    def close(self):
        """关闭资源"""
        if self._context:
            self._context.close()
            self._context = None
            
        if self._browser:
            self._browser.close()
            self._browser = None
            
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@contextmanager
def get_browser(headless: bool = True):
    """获取浏览器上下文"""
    driver = PlaywrightDriver(headless=headless)
    try:
        yield driver
    finally:
        driver.close()
