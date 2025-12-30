# Farside ETF 爬虫服务器 - 使用说明书

## 📖 目录

1. [功能概述](#功能概述)
2. [API接口说明](#api接口说明)
3. [命令行工具](#命令行工具)
4. [定时爬取](#定时爬取)
5. [服务器管理](#服务器管理)
6. [常见问题](#常见问题)

---

## 功能概述

本工具从 [Farside Investors](https://farside.co.uk) 网站爬取加密货币ETF资金流入流出数据。

### 支持的ETF类型

| ETF类型 | 包含机构 |
|---------|---------|
| **BTC** | IBIT, FBTC, BITB, ARKB, BTCO, EZBC, BRRR, HODL, BTCW, GBTC, BTC |
| **ETH** | ETHA, FETH, ETHW, CETH, ETHV, QETH, EZET, ETHE, ETH |
| **SOL** | BSOL, VSOL, FSOL, TSOL, SOEZ, GSOL |

### 核心功能

- ✅ **数据爬取** - 从Farside网站获取最新ETF流入流出数据
- ✅ **增量更新** - 只存储新数据，避免重复
- ✅ **定时任务** - 每天自动爬取4次（0:00/6:00/12:00/18:00）
- ✅ **API服务** - RESTful接口供其他服务调用
- ✅ **命令行工具** - 方便手动查询和管理

---

## API接口说明

**服务地址**: `http://142.171.245.211:8000`

### 1. 获取历史数据

```http
GET /api/etf/{type}/flows?days=15
```

**参数**:
- `type`: ETF类型 (btc/eth/sol)
- `days`: 查询天数 (1-365)

**示例**:
```bash
curl "http://142.171.245.211:8000/api/etf/btc/flows?days=5"
```

**返回**:
```json
[
  {
    "etf_type": "btc",
    "date": "2025-12-26",
    "total_flow": -275.9,
    "price_usd": null,
    "ticker_flows": {
      "IBIT": -192.6,
      "FBTC": -74.4,
      "GBTC": -8.9
    }
  }
]
```

---

### 2. 按日期查询

```http
GET /api/etf/{type}/date/{date}
```

**示例**:
```bash
curl "http://142.171.245.211:8000/api/etf/btc/date/2025-12-26"
```

**返回**:
```json
{
  "etf_type": "btc",
  "date": "2025-12-26",
  "total_flow": -275.9,
  "ticker_flows": {"IBIT": -192.6, "FBTC": -74.4, "GBTC": -8.9}
}
```

---

### 3. 按机构查询

```http
GET /api/etf/{type}/ticker/{ticker}?days=30
```

**示例**:
```bash
curl "http://142.171.245.211:8000/api/etf/btc/ticker/IBIT?days=10"
```

**返回**:
```json
[
  {"date": "2025-12-26", "flow_usd": -192.6},
  {"date": "2025-12-24", "flow_usd": -91.4}
]
```

---

### 4. 汇总统计

```http
GET /api/etf/{type}/summary
```

**示例**:
```bash
curl "http://142.171.245.211:8000/api/etf/btc/summary"
```

**返回**:
```json
{
  "etf_type": "btc",
  "start_date": "2025-12-10",
  "end_date": "2025-12-29",
  "total_inflow": 729.9,
  "total_outflow": 1813.9,
  "net_flow": -1084.0,
  "avg_daily_flow": -83.38,
  "trading_days": 13,
  "ticker_totals": {
    "IBIT": -354.9,
    "FBTC": -152.6,
    "BITB": -160.7
  }
}
```

---

### 5. 各机构累计

```http
GET /api/etf/{type}/tickers
```

**示例**:
```bash
curl "http://142.171.245.211:8000/api/etf/btc/tickers"
```

---

### 6. 手动触发爬取

```http
POST /api/scrape/{type}
```

**示例**:
```bash
curl -X POST "http://142.171.245.211:8000/api/scrape/btc"
```

---

## 命令行工具

在服务器上通过CLI进行操作：

```bash
cd /opt/etf-scraper
source venv/bin/activate
```

### 爬取数据

```bash
# 爬取BTC数据
python cli.py scrape btc

# 无头模式爬取（后台）
python cli.py scrape btc --headless

# 显示浏览器窗口爬取
python cli.py scrape btc --no-headless
```

### 查询数据

```bash
# 列出最近15天数据
python cli.py list btc --days 15

# 按日期查询
python cli.py date btc 2025-12-26

# 按机构查询
python cli.py ticker btc IBIT --days 30

# 汇总统计
python cli.py summary btc
```

### 启动服务

```bash
# 启动API服务
python cli.py serve --host 0.0.0.0 --port 8000

# 启动定时爬虫
python cli.py scheduler -e btc -e eth -e sol

# 立即执行一次并启动定时
python cli.py scheduler -e btc --now
```

---

## 定时爬取

定时调度器在以下时间自动爬取：

| 时间 | 说明 |
|------|------|
| 00:00 | 凌晨爬取 |
| 06:00 | 早间爬取 |
| 12:00 | 中午爬取 |
| 18:00 | 晚间爬取 |

### 启动调度器

```bash
# 后台启动
nohup python cli.py scheduler -e btc -e eth -e sol --now > logs/scheduler.log 2>&1 &

# 查看日志
tail -f logs/scheduler.log
```

### 增量更新机制

- **新日期** → 直接保存
- **已有日期数据变化** → 更新覆盖
- **数据无变化** → 跳过

---

## 服务器管理

### 启动服务

```bash
./scripts/start.sh
```

### 停止服务

```bash
./scripts/stop.sh
```

### 更新代码

```bash
./scripts/update.sh
```

### 查看日志

```bash
# 调度器日志
tail -f logs/scheduler.log

# API日志
tail -f logs/api.log
```

### 检查服务状态

```bash
# 检查进程
ps aux | grep cli.py

# 检查端口
netstat -tlnp | grep 8000
```

---

## 常见问题

### Q: 爬取失败怎么办？

Cloudflare可能会拦截。系统会自动重试5次，每次间隔5秒。如果仍然失败：

```bash
# 尝试显示浏览器窗口模式
python cli.py scrape btc --no-headless
```

### Q: 如何查看数据库内容？

```bash
sqlite3 data/etf_data.db
.tables
SELECT * FROM daily_summary LIMIT 10;
```

### Q: API返回404？

确保服务正在运行：
```bash
curl http://142.171.245.211:8000/
```

### Q: 如何只爬取特定ETF？

```bash
python cli.py scheduler -e btc  # 只爬BTC
python cli.py scheduler -e btc -e eth  # 爬BTC和ETH
```

---

## 数据说明

- **单位**: 所有金额单位为 **百万美元 (US$m)**
- **正数**: 资金流入
- **负数**: 资金流出
- **数据来源**: [Farside Investors](https://farside.co.uk)
