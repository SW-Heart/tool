"""
DeepSeek AI 分析器
使用 DeepSeek API 分析推文，提取金融信号
"""
import asyncio
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import sys
from pathlib import Path

# 添加路径以支持导入
CURRENT_DIR = Path(__file__).parent  # analyzer
SERVICE_DIR = CURRENT_DIR.parent     # x_alpha
ROOT_DIR = SERVICE_DIR.parent.parent # tool

# 优先加载服务目录 (x_alpha) 以匹配 config
sys.path.insert(0, str(SERVICE_DIR))
# 加载根目录以支持 shared
sys.path.insert(1, str(ROOT_DIR))

from shared.logger import setup_logger

logger = setup_logger("x_alpha.analyzer")

# System Prompt for DeepSeek
SYSTEM_PROMPT = """你是一个金融情报分析师。分析用户输入的推文。

判断规则：
1. 如果内容与加密货币、股票、宏观经济无关，或仅为闲聊/表情包/日常生活，标记为 irrelevant
2. 如果相关，提取交易信号

信号评分标准 (sentiment_score 0-10):
- 0-2: 极度悲观/看跌
- 3-4: 偏空
- 5: 中性
- 6-7: 偏多
- 8-10: 极度乐观/看涨

信号类型 (signal_type):
- BUY: 明确的买入信号或极度看涨言论
- SELL: 明确的卖出信号或极度看跌言论
- WATCH: 需要关注但不构成交易信号的重要信息
- NEUTRAL: 中性或信息量不足

必须输出纯 JSON 格式，不要包含 Markdown 标记、代码块或任何其他文字。
"""

OUTPUT_FORMAT = """{
  "is_relevant": true或false,
  "sentiment_score": 0-10的整数,
  "related_assets": ["BTC", "ETH"]或其他相关资产代码列表,
  "signal_type": "BUY"或"SELL"或"WATCH"或"NEUTRAL",
  "summary_zh": "中文一句话摘要（15-30字）"
}"""


class DeepSeekAnalyzer:
    """
    使用 DeepSeek API 分析推文
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.model = model
        self.max_retries = max_retries
    
    async def analyze_tweet(self, tweet: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单条推文
        
        Args:
            tweet: 推文数据 {"author": "xxx", "content": "xxx", ...}
            
        Returns:
            分析结果
        """
        author = tweet.get("author", "unknown")
        content = tweet.get("content", "")
        
        if not content or len(content.strip()) < 5:
            return self._default_result(irrelevant=True)
        
        user_prompt = f"KOL: @{author}\n推文内容: {content}\n\n请分析并返回 JSON:"
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n输出格式:\n{OUTPUT_FORMAT}"},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                
                result_text = response.choices[0].message.content.strip()
                result = self._parse_result(result_text)
                
                # [新增] 将推文链接追加到摘要末尾，增加可信度
                if tweet.get("tweet_url"):
                    summary = result.get("summary_zh", "")
                    # 避免重复添加
                    if tweet["tweet_url"] not in summary:
                        result["summary_zh"] = f"{summary} {tweet['tweet_url']}"
                
                logger.debug(f"分析完成 [{author}]: {result.get('signal_type')} / {result.get('sentiment_score')}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}): {e}")
            except Exception as e:
                logger.error(f"分析失败 (尝试 {attempt + 1}): {e}")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2)
        
        return self._default_result(irrelevant=True)
    
    def _parse_result(self, text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 结果"""
        # 移除可能的 markdown 代码块标记
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        # 尝试解析 JSON
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise
        
        # 验证和规范化字段
        return {
            "is_relevant": bool(result.get("is_relevant", False)),
            "sentiment_score": max(0, min(10, int(result.get("sentiment_score", 5)))),
            "related_assets": result.get("related_assets", []) or [],
            "signal_type": result.get("signal_type", "NEUTRAL"),
            "summary_zh": result.get("summary_zh", ""),
        }
    
    def _default_result(self, irrelevant: bool = False) -> Dict[str, Any]:
        """返回默认分析结果"""
        return {
            "is_relevant": not irrelevant,
            "sentiment_score": 5,
            "related_assets": [],
            "signal_type": "NEUTRAL",
            "summary_zh": "",
        }
    
    async def batch_analyze(
        self,
        tweets: List[Dict[str, Any]],
        concurrency: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        批量分析推文
        
        Args:
            tweets: 推文列表
            concurrency: 并发数量
            
        Returns:
            分析结果列表 (与输入顺序对应)
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def analyze_with_semaphore(tweet: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                result = await self.analyze_tweet(tweet)
                # 合并推文原始数据和分析结果
                return {**tweet, **result}
        
        tasks = [analyze_with_semaphore(tweet) for tweet in tweets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量分析异常: {result}")
                final_results.append({**tweets[i], **self._default_result(irrelevant=True)})
            else:
                final_results.append(result)
        
        relevant_count = sum(1 for r in final_results if r.get("is_relevant"))
        logger.info(f"批量分析完成: {len(tweets)} 条推文, {relevant_count} 条相关")
        
        return final_results


# 测试代码
async def test_analyzer():
    from config import DEEPSEEK_CONFIG
    
    analyzer = DeepSeekAnalyzer(
        api_key=DEEPSEEK_CONFIG["api_key"],
        base_url=DEEPSEEK_CONFIG["base_url"],
    )
    
    test_tweet = {
        "author": "elonmusk",
        "content": "Bitcoin is the future of money. HODL strong! 🚀",
        "tweet_url": "https://x.com/elonmusk/status/123456789",
    }
    
    result = await analyzer.analyze_tweet(test_tweet)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(test_analyzer())
