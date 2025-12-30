"""
Twitter Syndication API 采集器
通过 X 的 Syndication API (匿名/免登录) 采集推文
支持 NitterFallback
"""
import asyncio
import httpx
import re
import json
import random
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.utils import get_random_user_agent, parse_timestamp
from shared.logger import setup_logger

logger = setup_logger("x_alpha.collector")


class NitterCollector:
    """
    Nitter 采集器 (Fallback)
    
    当 Syndication API 失效时，尝试从 Nitter 实例采集
    """
    # 常用 Nitter 实例列表 (随机轮询)
    INSTANCES = [
        "https://nitter.net",
        "https://nitter.cz",
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.x86-64-unknown-linux-gnu.zip",
    ]
    
    @classmethod
    async def fetch_tweets(cls, username: str, timeout: int = 20) -> List[Dict[str, Any]]:
        """从 Nitter 获取推文"""
        instance = random.choice(cls.INSTANCES)
        url = f"{instance}/{username}"
        logger.info(f"正在尝试 Nitter Fallback: {url}")
        
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return cls._parse_nitter_html(response.text, username)
                else:
                    logger.warning(f"Nitter 请求失败 {response.status_code}: {url}")
        except Exception as e:
            logger.warning(f"Nitter 连接异常: {e}")
            
        return []

    @staticmethod
    def _parse_nitter_html(html: str, username: str) -> List[Dict[str, Any]]:
        tweets = []
        soup = BeautifulSoup(html, 'html.parser')
        
        timeline = soup.find_all('div', class_='timeline-item')
        for item in timeline:
            if 'show-more' in item.get('class', []):
                continue
                
            try:
                # 提取正文
                content_div = item.find('div', class_='tweet-content')
                if not content_div:
                    continue
                content = content_div.get_text(strip=True)
                
                # 提取时间
                date_span = item.find('span', class_='tweet-date')
                published_at = datetime.utcnow()
                if date_span:
                    link = date_span.find('a')
                    if link and link.get('title'):
                        # Nitter 时间格式: "Dec 30, 2025 · 4:20 PM UTC"
                        try:
                            t_str = link['title']
                            # 简化处理，直接用 UTC now 兜底，或者解析标准格式
                            # 这里简单起见暂时用当前时间，因为 Nitter 格式多变
                            pass 
                        except:
                            pass
                
                # 提取链接/ID
                link = item.find('a', class_='tweet-link')
                if not link:
                    continue
                tweet_url = link['href']  # e.g., /username/status/123456
                tweet_id_match = re.search(r'/status/(\d+)', tweet_url)
                if not tweet_id_match:
                    continue
                tweet_id = tweet_id_match.group(1)
                
                # 提取图片/头像
                avatar_url = None
                avatar_img = item.find('a', class_='tweet-avatar').find('img')
                if avatar_img:
                    src = avatar_img.get('src')
                    if src:
                        avatar_url = f"https://nitter.net{src}" if src.startswith('/') else src

                tweets.append({
                    "id": tweet_id,
                    "author": username,
                    "avatar_url": avatar_url,
                    "content": content,
                    "tweet_url": f"https://x.com/{username}/status/{tweet_id}",
                    "published_at": published_at,
                })
            except Exception as e:
                continue
                
        return tweets


class TwitterSyndicationCollector:
    """
    通过 Twitter Syndication API 采集推文
    
    使用匿名 API，无需认证，适合部署在美国服务器直连
    """
    
    BASE_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    
    
    # 请求间隔配置 (秒) - 增大间隔以避免限流
    MIN_REQUEST_DELAY = 8   # 最小请求间隔
    MAX_REQUEST_DELAY = 15  # 最大请求间隔
    BASE_429_DELAY = 60     # 429 基础退避时间
    MAX_429_DELAY = 180     # 429 最大退避时间
    
    def __init__(self, timeout: int = 30, max_retries: int = 3, retry_delay: int = 5, cookies: Optional[str] = None):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cookies = cookies
        self._last_request_time = 0  # 上次请求时间戳
    
    async def _wait_for_rate_limit(self):
        """等待请求间隔，避免触发限流"""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        min_delay = random.uniform(self.MIN_REQUEST_DELAY, self.MAX_REQUEST_DELAY)
        
        if elapsed < min_delay:
            wait_time = min_delay - elapsed
            logger.debug(f"等待 {wait_time:.1f}s 后发起请求...")
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
    
    async def fetch_tweets(self, username: str) -> List[Dict[str, Any]]:
        """
        获取指定用户的推文
        
        Args:
            username: Twitter 用户名
            
        Returns:
            推文列表
        """
        logger.info(f"开始采集 {username} via API...")
        
        # 1. 尝试官方 Syndication API
        tweets = await self._fetch_tweets_api(username)
        
        # 2. 如果 API 失败 (空数据或限流)，尝试 Nitter Fallback
        if not tweets:
            logger.warning(f"Syndication API 返回空，尝试 Nitter Fallback: {username}")
            tweets = await NitterCollector.fetch_tweets(username)
            if tweets:
                logger.info(f"Nitter 成功采集到 {len(tweets)} 条推文")
            else:
                logger.error(f"Nitter 采集也失败: {username}")
        
        return tweets

    async def _fetch_tweets_api(self, username: str) -> List[Dict[str, Any]]:
        """内部方法：通过 Syndication API 采集"""
        # 等待请求间隔
        await self._wait_for_rate_limit()
        
        url = self.BASE_URL.format(username=username)
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        # 如果配置了 Cookie，添加到请求头
        if self.cookies:
            headers["Cookie"] = self.cookies
            try:
                if "ct0=" in self.cookies:
                    ct0 = re.search(r'ct0=([^;]+)', self.cookies).group(1)
                    headers["x-csrf-token"] = ct0
                    headers["x-twitter-active-user"] = "yes"
                    headers["x-twitter-auth-type"] = "OAuth2Session"
            except Exception:
                pass
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        return self._parse_response(response.text, username)
                    elif response.status_code == 404:
                        logger.warning(f"用户不存在: {username}")
                        return []
                    elif response.status_code == 429:
                        # 使用指数退避策略
                        backoff = min(
                            self.BASE_429_DELAY * (2 ** attempt) + random.uniform(0, 10),
                            self.MAX_429_DELAY
                        )
                        logger.warning(f"429 限流，退避 {backoff:.0f}s 后重试: {username} (尝试 {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(f"请求失败 ({response.status_code}): {username}")
                        
            except httpx.TimeoutException:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries}): {username}")
            except Exception as e:
                logger.error(f"采集异常: {username} - {e}")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay)
        
        return []
    
    def _parse_response(self, html: str, username: str) -> List[Dict[str, Any]]:
        """
        解析 Syndication API 返回的 HTML
        
        Args:
            html: HTML 响应内容
            username: 用户名
            
        Returns:
            解析后的推文列表
        """
        tweets = []
        
        try:
            # 1. 优先尝试解析 __NEXT_DATA__ (新版 Syndication API)
            next_data_match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
                html, re.DOTALL
            )
            if next_data_match:
                try:
                    data = json.loads(next_data_match.group(1))
                    tweets = self._extract_from_next_data(data, username)
                    logger.info(f"从 {username} 采集到 {len(tweets)} 条推文")
                    return tweets
                except json.JSONDecodeError as e:
                    logger.warning(f"解析 __NEXT_DATA__ JSON 失败: {e}")
                except Exception as e:
                    logger.error(f"解析 __NEXT_DATA__ 异常: {e}")
            
            # 2. 降级：尝试 __INITIAL_STATE__ (旧版格式)
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.__INITIAL_STATE__' in script.string:
                    json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            tweets = self._extract_from_json(data, username)
                            if tweets:
                                logger.info(f"从 {username} 采集到 {len(tweets)} 条推文 (legacy)")
                                return tweets
                        except json.JSONDecodeError:
                            pass
            
            # 3. 最后降级：查找推文容器 (HTML 刮取)
            tweet_elements = soup.find_all('article') or soup.find_all('div', class_=re.compile(r'timeline-Tweet'))
            
            # 从 HTML 元素中提取
            for element in tweet_elements:
                tweet = self._parse_tweet_element(element, username)
                if tweet:
                    tweets.append(tweet)
            
            # 尝试解析嵌入的 JSON 数据
            if not tweets:
                tweets = self._parse_embedded_data(html, username)
            
            logger.info(f"从 {username} 采集到 {len(tweets)} 条推文")
            
        except Exception as e:
            logger.error(f"解析响应失败: {username} - {e}")
        
        return tweets
    
    def _parse_tweet_element(self, element, username: str) -> Optional[Dict[str, Any]]:
        """解析单个推文 HTML 元素"""
        try:
            # 提取推文 ID
            tweet_link = element.find('a', href=re.compile(r'/status/\d+'))
            if not tweet_link:
                return None
            
            href = tweet_link.get('href', '')
            tweet_id_match = re.search(r'/status/(\d+)', href)
            if not tweet_id_match:
                return None
            
            tweet_id = tweet_id_match.group(1)
            
            # 提取推文内容
            content_elem = element.find('p') or element.find('div', class_=re.compile(r'tweet-text|content'))
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            # 提取时间
            time_elem = element.find('time')
            published_at = None
            if time_elem:
                datetime_str = time_elem.get('datetime') or time_elem.get_text()
                published_at = parse_timestamp(datetime_str)
            
            if not published_at:
                published_at = datetime.utcnow()
            
            # 提取头像
            avatar_elem = element.find('img', class_=re.compile(r'avatar|profile'))
            avatar_url = avatar_elem.get('src') if avatar_elem else None
            
            return {
                "id": tweet_id,
                "author": username,
                "avatar_url": avatar_url,
                "content": content,
                "tweet_url": f"https://x.com/{username}/status/{tweet_id}",
                "published_at": published_at,
            }
            
        except Exception as e:
            logger.debug(f"解析推文元素失败: {e}")
            return None
    
    def _parse_embedded_data(self, html: str, username: str) -> List[Dict[str, Any]]:
        """从嵌入的 JavaScript 数据中提取推文"""
        tweets = []
        
        try:
            # 查找 JSON 数据
            patterns = [
                r'"tweet_results":\s*({.*?})\s*[,}]',
                r'"legacy":\s*({.*?"full_text".*?})\s*[,}]',
                # 移除宽泛正则，防止匹配到 User ID 或错误的上下文
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                for match in matches[:10]:  # 限制数量
                    try:
                        data = json.loads(match)
                        tweet_id = data.get('id_str') or data.get('rest_id')
                        content = data.get('full_text') or data.get('text', '')
                        
                        # 确保 ID 看起来像推文 ID (长度通常 > 10)
                        if tweet_id and content and len(str(tweet_id)) > 10:
                            tweets.append({
                                "id": tweet_id,
                                "author": username,
                                "content": content,
                                "tweet_url": f"https://x.com/{username}/status/{tweet_id}",
                                "published_at": datetime.utcnow(),
                            })
                    except (json.JSONDecodeError, KeyError):
                        continue
                        
        except Exception as e:
            logger.debug(f"解析嵌入数据失败: {e}")
        
        return tweets
    
    def _extract_from_next_data(self, data: dict, default_username: str) -> List[Dict[str, Any]]:
        """从 __NEXT_DATA__ (新版 Syndication API) 中提取推文"""
        tweets = []
        
        try:
            # 提取 timeline.entries
            entries = data.get('props', {}).get('pageProps', {}).get('timeline', {}).get('entries', [])
            
            for entry in entries:
                if entry.get('type') != 'tweet':
                    continue
                
                tweet_data = entry.get('content', {}).get('tweet', {})
                if not tweet_data:
                    continue
                
                tweet_id = tweet_data.get('id_str')
                content = tweet_data.get('full_text') or tweet_data.get('text', '')
                
                if not tweet_id or not content:
                    continue
                
                # 提取作者信息
                user = tweet_data.get('user', {})
                author = user.get('screen_name', default_username)
                avatar_url = user.get('profile_image_url_https')
                
                # 解析时间
                created_at = tweet_data.get('created_at')
                published_at = parse_timestamp(created_at) if created_at else datetime.utcnow()
                
                # 检查是否是转推
                if tweet_data.get('retweeted_status'):
                    rt_data = tweet_data['retweeted_status']
                    tweet_id = rt_data.get('id_str', tweet_id)
                    content = rt_data.get('full_text', content)
                    rt_user = rt_data.get('user', {})
                    author = rt_user.get('screen_name', author)
                    avatar_url = rt_user.get('profile_image_url_https', avatar_url)
                    created_at = rt_data.get('created_at')
                    if created_at:
                        published_at = parse_timestamp(created_at)
                
                tweets.append({
                    "id": tweet_id,
                    "author": author,
                    "avatar_url": avatar_url,
                    "content": content,
                    "tweet_url": f"https://x.com/{author}/status/{tweet_id}",
                    "published_at": published_at,
                })
                
        except Exception as e:
            logger.error(f"解析 __NEXT_DATA__ 异常: {e}")
        
        return tweets
    
    def _extract_from_json(self, data: dict, default_username: str) -> List[Dict[str, Any]]:
        """从 JSON 数据中提取推文 (支持 globalObjects)"""
        tweets = []
        
        # 1. 优先尝试 globalObjects (Redux 风格，包含完整用户信息)
        if 'globalObjects' in data:
            logger.debug(f"Found globalObjects: {data['globalObjects'].keys()}")
            try:
                objects = data['globalObjects']
                users = objects.get('users', {})
                tweets_obj = objects.get('tweets', {})
                
                parsed_tweets = []
                seen_ids = set()
                
                for tweet_id, tweet_data in tweets_obj.items():
                    # 如果是 Retweet，提取原推文
                    if 'retweeted_status_id_str' in tweet_data:
                        original_id = tweet_data['retweeted_status_id_str']
                        # 确保原推文也在数据中
                        if original_id in tweets_obj:
                            tweet_data = tweets_obj[original_id]
                            tweet_id = original_id
                    
                    # 去重
                    if tweet_id in seen_ids:
                        continue
                    seen_ids.add(tweet_id)
                    
                    # 提取作者
                    user_id = tweet_data.get('user_id_str')
                    author = users.get(user_id, {}).get('screen_name', default_username)
                    
                    content = tweet_data.get('full_text') or tweet_data.get('text', '')
                    if not content:
                        continue
                        
                    parsed_tweets.append({
                        "id": tweet_id,
                        "author": author,
                        "content": content,
                        "tweet_url": f"https://x.com/{author}/status/{tweet_id}",
                        "published_at": parse_timestamp(tweet_data.get('created_at')),
                    })
                
                # 按时间倒序
                parsed_tweets.sort(key=lambda x: x['published_at'], reverse=True)
                return parsed_tweets
            except Exception as e:
                logger.debug(f"解析 globalObjects 失败: {e}")

        # 2. 降级方案：递归查找 (GraphQy 风格)
        def extract_tweets(obj):
            if isinstance(obj, dict):
                # GraphQy Tweet Result
                if 'typename' in obj and obj['typename'] == 'Tweet':
                    # 尝试提取 legacy
                    legacy = obj.get('legacy', {})
                    if legacy:
                        tweet_id = legacy.get('id_str')
                        content = legacy.get('full_text')
                        
                        # 尝试提取作者
                        screen_name = default_username
                        try:
                            screen_name = obj['core']['user_results']['result']['legacy']['screen_name']
                        except (KeyError, TypeError):
                            pass
                            
                        # 处理 Retweet (legacy 中包含 retweeted_status_result)
                        if 'retweeted_status_result' in legacy:
                            try:
                                result = legacy['retweeted_status_result']['result']
                                legacy = result['legacy']
                                tweet_id = legacy.get('id_str')
                                content = legacy.get('full_text')
                                screen_name = result['core']['user_results']['result']['legacy']['screen_name']
                            except (KeyError, TypeError):
                                pass

                        if tweet_id and content:
                            tweets.append({
                                "id": tweet_id,
                                "author": screen_name,
                                "content": content,
                                "tweet_url": f"https://x.com/{screen_name}/status/{tweet_id}",
                                "published_at": parse_timestamp(legacy.get('created_at')),
                            })
                            return # 找到即返回，不再深挖内部

                # 旧的通用查找 (最后一道防线)
                if ('full_text' in obj or 'text' in obj) and ('id_str' in obj or 'rest_id' in obj):
                    tweet_id = obj.get('id_str') or obj.get('rest_id')
                    content = obj.get('full_text') or obj.get('text', '')
                    
                    # 简单的推文对象通常不包含用户信息，只能用默认 username
                    # 但这会导致 Retweet 归属错误，所以仅作为 fallback
                    if tweet_id and content and len(str(tweet_id)) > 10:
                         # 避免重复 (如果上面 GraphQy 已经处理了)
                        if not any(t['id'] == tweet_id for t in tweets):
                            tweets.append({
                                "id": tweet_id,
                                "author": default_username,
                                "content": content,
                                "tweet_url": f"https://x.com/{default_username}/status/{tweet_id}",
                                "published_at": datetime.utcnow(), # 无法解析时间
                            })

                for value in obj.values():
                    extract_tweets(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_tweets(item)
        
        extract_tweets(data)
        return tweets
    
    async def fetch_all_users(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        串行采集多个用户的推文 (带限流保护)
        
        Args:
            users: 用户配置列表 [{"username": "xxx", "tags": [...]}]
            
        Returns:
            所有推文列表 (包含用户标签)
        """
        all_tweets = []
        success_count = 0
        fail_count = 0
        
        # 按优先级排序 (优先级低的数字先采集)
        sorted_users = sorted(users, key=lambda x: x.get("priority", 3))
        
        logger.info(f"开始串行采集 {len(sorted_users)} 个用户 (带限流保护)...")
        
        for i, user in enumerate(sorted_users):
            username = user["username"]
            
            try:
                logger.info(f"采集 [{i+1}/{len(sorted_users)}]: @{username}")
                tweets = await self.fetch_tweets(username)
                
                if tweets:
                    success_count += 1
                    for tweet in tweets:
                        tweet["tags"] = user.get("tags", [])
                        tweet["priority"] = user.get("priority", 3)
                        all_tweets.append(tweet)
                else:
                    fail_count += 1
                    
            except Exception as e:
                fail_count += 1
                logger.error(f"采集失败: {username} - {e}")
        
        logger.info(f"采集完成: 成功 {success_count}/{len(sorted_users)}, 共 {len(all_tweets)} 条推文")
        return all_tweets


# 测试代码
async def test_collector():
    # 测试官方
    # collector = TwitterSyndicationCollector()
    
    # 测试 Fallback
    print("Testing Nitter...")
    tweets = await NitterCollector.fetch_tweets("elonmusk")
    print(f"Got {len(tweets)} tweets from Nitter")
    for tweet in tweets[:3]:
        print(f"[{tweet['id']}] {tweet['content'][:50]}...")


if __name__ == "__main__":
    asyncio.run(test_collector())
