"""
浏览器驱动管理
使用 undetected-chromedriver 绕过 Cloudflare 保护
"""
import time
import logging
from typing import Optional, TYPE_CHECKING, Any
from contextlib import contextmanager

# 为了type hint
if TYPE_CHECKING:
    import undetected_chromedriver as uc

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    UC_AVAILABLE = True
except ImportError:
    uc = None
    UC_AVAILABLE = False
    # 延迟导入selenium组件
    By = None
    WebDriverWait = None
    EC = None
    TimeoutException = Exception
    WebDriverException = Exception

import sys
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])
from config import SCRAPER_CONFIG

logger = logging.getLogger(__name__)


class BrowserDriver:
    """浏览器驱动管理器"""
    
    def __init__(self, headless: bool = None):
        """
        初始化浏览器驱动
        
        Args:
            headless: 是否使用无头模式，默认从配置读取
        """
        self.headless = headless if headless is not None else SCRAPER_CONFIG["headless"]
        self.timeout = SCRAPER_CONFIG["timeout"]
        self._driver: Optional[Any] = None
    
    def _create_driver(self) -> Any:
        """创建浏览器驱动实例"""
        if uc is None:
            raise ImportError("undetected-chromedriver 未安装")
        
        options = uc.ChromeOptions()
        
        if self.headless:
            # 使用 headless=new 是正确的，但有时候需要在 arguments 里也加一下
            options.add_argument('--headless=new')
        
        # 反检测配置
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage') # 关键：容器/Linux环境必须
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        
        # 显式添加 headless 参数，以防 headless=new 也没生效
        if self.headless:
             options.add_argument('--headless')

        # 设置用户代理
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            # 尝试最稳健的初始化方式
            # use_subprocess=True 可以解决很多 'RemoteDisconnected' 和版本补丁问题
            # version_main=143 依然保留以匹配你的环境，如果还不行可能需要去掉让它自适应
            driver = uc.Chrome(
                options=options, 
                version_main=143,
                use_subprocess=True,
                driver_executable_path=None,
                browser_executable_path=None
            )
        except Exception as e:
            logger.warning(f"常规启动失败，尝试不指定 version_main: {e}")
            # 备选方案：不仅指定版本，让它自动查找最新
            driver = uc.Chrome(
                options=options,
                use_subprocess=True
            )
            
        driver.set_page_load_timeout(self.timeout)
        
        return driver
    
    @property
    def driver(self) -> Any:
        """获取驱动实例（懒加载）"""
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver
    
    def get(self, url: str, wait_for_selector: str = None) -> bool:
        """
        访问URL并等待页面加载
        
        Args:
            url: 目标URL
            wait_for_selector: 等待的元素选择器
            
        Returns:
            是否成功加载
        """
        try:
            logger.info(f"正在访问: {url}")
            self.driver.get(url)
            
            # 等待Cloudflare检查通过
            time.sleep(3)
            
            if wait_for_selector:
                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                )
            
            logger.info("页面加载成功")
            return True
            
        except TimeoutException:
            logger.error(f"页面加载超时: {url}")
            return False
        except WebDriverException as e:
            logger.error(f"浏览器错误: {e}")
            return False
    
    def get_page_source(self) -> str:
        """获取页面源码"""
        return self.driver.page_source
    
    def find_element(self, selector: str, by = None):
        """查找单个元素"""
        if by is None:
            by = By.CSS_SELECTOR
        return self.driver.find_element(by, selector)
    
    def find_elements(self, selector: str, by = None):
        """查找多个元素"""
        if by is None:
            by = By.CSS_SELECTOR
        return self.driver.find_elements(by, selector)
    
    def wait_for_element(self, selector: str, timeout: int = None):
        """等待元素出现"""
        timeout = timeout or self.timeout
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
    
    def save_screenshot(self, path: str) -> bool:
        """保存截图"""
        try:
            return self.driver.save_screenshot(str(path))
        except Exception as e:
            logger.error(f"保存截图失败: {e}")
            return False

    def save_page_source(self, path: str) -> bool:
        """保存页面源码"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            return True
        except Exception as e:
            logger.error(f"保存源码失败: {e}")
            return False

    def close(self):
        """关闭浏览器"""
        if self._driver:
            try:
                self._driver.quit()
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
            finally:
                self._driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@contextmanager
def get_browser(headless: bool = True):
    """
    上下文管理器方式获取浏览器
    
    Usage:
        with get_browser() as browser:
            browser.get("https://example.com")
            html = browser.get_page_source()
    """
    browser = BrowserDriver(headless=headless)
    try:
        yield browser
    finally:
        browser.close()
