# Farside ETF 爬虫服务器

从 Farside Investors 网站爬取 BTC/ETH/SOL ETF 资金流入流出数据。

## 功能特性

- ✅ 支持 BTC、ETH、SOL 三种ETF数据爬取
- ✅ 使用 undetected-chromedriver 绕过 Cloudflare
- ✅ SQLite 本地存储，增量更新
- ✅ 定时爬取（每天 0:00/6:00/12:00/18:00）
- ✅ FastAPI RESTful 查询接口
- ✅ CLI 命令行工具

## 快速开始

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt setuptools

# 爬取BTC数据
python cli.py scrape btc

# 查询数据
python cli.py list btc --days 15
python cli.py date btc 2025-12-26
python cli.py ticker btc IBIT
python cli.py summary btc
```

## 定时爬取

```bash
# 启动定时调度器（后台运行）
nohup python cli.py scheduler -e btc -e eth -e sol --now > scheduler.log 2>&1 &
```

## API 服务

```bash
# 启动API服务
python cli.py serve --host 0.0.0.0 --port 8000
```

接口说明：
- `GET /api/etf/{type}/flows?days=15` - 获取历史数据
- `GET /api/etf/{type}/date/{date}` - 按日期查询
- `GET /api/etf/{type}/ticker/{ticker}` - 按机构查询
- `GET /api/etf/{type}/summary` - 汇总统计

## 项目结构

```
tool/
├── etf_scraper/
│   ├── browser/driver.py      # Selenium驱动
│   ├── parser/table_parser.py # HTML解析
│   ├── scraper/base.py        # 爬虫逻辑
│   ├── storage/database.py    # 数据存储
│   └── api/server.py          # FastAPI服务
├── scheduler/cron.py          # 定时调度器
├── cli.py                     # 命令行工具
├── config.py                  # 配置文件
└── requirements.txt           # 依赖
```
