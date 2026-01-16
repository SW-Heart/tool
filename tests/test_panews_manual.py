
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from crawlers.panews import PANewsCrawler

async def main():
    print("🚀 Starting PANews Manual Test...")
    
    # Use a temp cache dir to avoid polluting real data or being affected by it
    crawler = PANewsCrawler(headless=True, cache_dir="./data/panews_test_cache")
    
    print("🕷️ Fetching news...")
    # Fetch all (not only new) to ensure we get data
    news = await crawler.fetch_important_news(only_new=False, save_to_db=False, timeout=60)
    
    print("\n" + "="*60)
    print(f"📊 Result: Fetched {len(news)} items")
    print("="*60)
    
    if not news:
        print("❌ No news fetched!")
        return

    # Print first 3 items
    for item in news[:5]:
        print(f"\nTime: {item.get('time')}")
        print(f"Date: {item.get('publishDateTime')}")
        print(f"Title: {item.get('title')}")
        print(f"Link:  {item.get('link')}")
        print(f"Imp? : {item.get('isImportant')}")
        print("-" * 30)
        
    # Check for Year Logic
    print("\n🔍 Checking Year Logic...")
    from datetime import datetime
    current_year = datetime.now().year
    
    has_last_year = False
    for item in news:
        if str(current_year - 1) in item['publishDateTime']:
            has_last_year = True
            print(f"Found item from last year: {item['publishDateTime']} - {item['title']}")
            break
            
    if not has_last_year:
        print(f"ℹ️ No items from last year found (expected if it's not Jan/Feb or no old news fetched)")

if __name__ == "__main__":
    asyncio.run(main())
