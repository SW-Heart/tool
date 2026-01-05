# Crypto 工具箱 (Crypto Toolkit)

一套加密货币数据采集与分析工具，包含 ETF 数据爬虫和实时新闻聚合服务。

## 🛠️ 工具概览

| 工具 | 说明 | 数据源 | 更新频率 |
|------|------|--------|----------|
| **ETF 爬虫** | BTC/ETH/SOL ETF 资金流入流出数据 | Farside Investors | 每天 4 次 |
| **新闻爬虫** | Crypto 重要快讯聚合 | PANews | 每 15 分钟 |

---

## 📁 项目结构

```
tool/
├── etf_scraper/           # ETF 数据爬虫模块
│   ├── browser/           # Selenium 驱动
│   ├── parser/            # HTML 解析
│   ├── scraper/           # 爬虫逻辑
│   ├── storage/           # 数据存储
│   └── api/               # ETF API 服务
│
├── crawlers/              # 新闻爬虫模块
│   ├── panews.py          # PANews 爬虫
│   ├── storage.py         # SQLite 存储 (24小时滚动)
│   └── api.py             # 新闻 API 服务
│
├── scheduler/             # 定时任务调度
│   ├── cron.py            # ETF 定时任务
│   └── news_scheduler.py  # 新闻定时任务
│
├── cli.py                 # ETF 命令行工具
├── run_service.py         # 新闻服务入口
├── start_news_service.sh  # 新闻服务启动脚本
└── requirements.txt       # 依赖
```

---

## 🚀 快速开始

### 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install playwright schedule fastapi uvicorn
playwright install chromium
```

---

## 📊 工具1: ETF 数据爬虫

从 Farside Investors 爬取 BTC/ETH/SOL ETF 资金流入流出数据。

### 功能特性

- ✅ 支持 BTC、ETH、SOL 三种 ETF
- ✅ 使用 undetected-chromedriver 绕过 Cloudflare
- ✅ SQLite 本地存储，增量更新
- ✅ 定时爬取（每天 0:00/6:00/12:00/18:00）

### 使用方法

```bash
# 爬取数据
python cli.py scrape btc

# 查询数据
python cli.py list btc --days 15
python cli.py date btc 2025-12-26
python cli.py ticker btc IBIT
python cli.py summary btc

# 启动定时调度器
python cli.py scheduler -e btc -e eth -e sol --now

# 启动 API 服务 (端口 8000)
python cli.py serve --host 0.0.0.0 --port 8000
```

### API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/etf/{type}/flows?days=15` | 获取历史数据 |
| `GET /api/etf/{type}/date/{date}` | 按日期查询 |
| `GET /api/etf/{type}/ticker/{ticker}` | 按机构查询 |
| `GET /api/etf/{type}/summary` | 汇总统计 |

---

## 📰 工具2: 新闻爬虫

实时抓取 PANews 重要快讯，自动去重，24小时滚动存储。

### 功能特性

- ✅ 自动筛选"只看重要"资讯
- ✅ 每 15 分钟自动抓取
- ✅ 24 小时滚动存储，过期自动清理
- ✅ RESTful API 供外部服务调用

### 使用方法

```bash
# 单次抓取测试
python3 -m crawlers.panews --all

# 启动定时爬虫 (每15分钟)
python3 -m scheduler.news_scheduler --interval 15

# 启动完整服务 (爬虫 + API)
python3 run_service.py --interval 15 --port 8080

# 或使用启动脚本
./start_news_service.sh --both
```

### API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/news?limit=20` | 获取最新新闻 |
| `GET /api/news/latest` | 获取最新一条 |
| `GET /api/news/since/{id}` | 增量获取 |
| `GET /api/stats` | 统计信息 |
| `POST /api/cleanup` | 清理过期数据 |

### Python 调用

```python
from crawlers import PANewsCrawler, get_storage

# 抓取新闻
crawler = PANewsCrawler()
news = crawler.fetch_sync(only_new=True, save_to_db=True)

# 查询存储
storage = get_storage()
latest = storage.get_latest_news(limit=10)
```

---

## 🖥️ 生产部署

### 后台运行

```bash
# ETF 定时爬虫
nohup python cli.py scheduler -e btc -e eth -e sol --now > logs/etf.log 2>&1 &

# 新闻完整服务
nohup python3 run_service.py --interval 15 --port 8080 > logs/news.log 2>&1 &
```

### 一起部署

```bash
#!/bin/bash
# deploy.sh

mkdir -p logs

# 启动 ETF 定时爬虫 (端口 8000)
nohup python cli.py scheduler -e btc --now > logs/etf.log 2>&1 &
echo "ETF 服务已启动 (PID: $!)"

# 启动新闻服务 (端口 8080)
nohup python3 run_service.py --port 8080 > logs/news.log 2>&1 &
echo "新闻服务已启动 (PID: $!)"

echo "所有服务已部署完成"
```

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| ETF API | 8000 | ETF 数据查询 |
| 新闻 API | 8080 | 新闻数据查询 |

---

## 📋 数据存储

| 工具 | 存储位置 | 保留策略 |
|------|----------|----------|
| ETF 爬虫 | `data/etf.db` | 永久保留 |
| 新闻爬虫 | `data/news.db` | 24 小时滚动 |

---

## 🔧 开发扩展

添加新的数据源只需：

1. 在 `crawlers/` 下创建新爬虫文件
2. 在 `scheduler/` 下创建对应的定时任务
3. 更新 `crawlers/__init__.py` 导出

```python
# 示例：添加 CoinDesk 爬虫
from crawlers import CoinDeskCrawler  # 新增
```
