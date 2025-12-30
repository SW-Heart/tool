
import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.x_alpha.collector.syndication import TwitterSyndicationCollector

class TestRetweetExtraction(unittest.TestCase):
    def test_global_objects_retweet(self):
        """测试从 globalObjects 中正确提取转推的原作者和ID"""
        collector = TwitterSyndicationCollector()
        
        # 模拟数据：ethereum (id: 111) 转推了 Celo (id: 222)
        mock_data = {
            "globalObjects": {
                "tweets": {
                    "111": {
                        "id_str": "111",
                        "full_text": "RT @Celo: Celo is great",
                        "user_id_str": "999", # ethereum
                        "retweeted_status_id_str": "222",
                        "created_at": "Wed Dec 30 12:00:00 +0000 2025"
                    },
                    "222": {
                        "id_str": "222",
                        "full_text": "Celo is great",
                        "user_id_str": "888", # Celo
                        "created_at": "Wed Dec 30 10:00:00 +0000 2025"
                    }
                },
                "users": {
                    "999": {"screen_name": "ethereum"},
                    "888": {"screen_name": "Celo"}
                }
            }
        }
        
        # 即使我们尝试采集 ethereum，期望也能提取到 Celo 的原始推文
        tweets = collector._extract_from_json(mock_data, default_username="ethereum")
        
        self.assertEqual(len(tweets), 1)
        tweet = tweets[0]
        
        print(f"Extracted Tweet: {tweet}")
        
        # 验证: 应该是 Celo 的推文，ID 为 222
        self.assertEqual(tweet['id'], "222")
        self.assertEqual(tweet['author'], "Celo")
        self.assertEqual(tweet['tweet_url'], "https://x.com/Celo/status/222")
        self.assertIn("Celo is great", tweet['content'])

if __name__ == '__main__':
    unittest.main()
