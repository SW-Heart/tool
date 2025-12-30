# X-Alpha API 接口文档

X-Alpha 是一个智能舆情服务，监控 Twitter 上关键 KOL 的动态，通过 AI 分析提取金融信号。

## 服务地址

- **默认端口**: `8002`
- **Base URL**: `http://<your-server-ip>:8002`

> 注意: 请确保服务器防火墙已放行 8002 端口，或配置 Nginx 反向代理。

## 鉴权 (Authentication)

如果设置了 `X_ALPHA_API_KEY` 环境变量，则需要在所有请求的 Header 中携带该 Key。

- **Header Key**: `X-API-Key`
- **Header Value**: `<your-api-key>`

## 接口列表

### 1. 健康检查 (Health Check)

检查服务运行状态、数据库连接情况以及监控的用户列表。

- **Endpoint**: `GET /health`
- **Auth**: 不需要

**响应示例**:
```json
{
  "status": "ok",
  "db_connected": true,
  "last_scan_time": "2023-12-25 10:00:00",
  "monitored_users": ["elonmusk", "binance", ...],
  "total_signals": 150
}
```

### 2. 获取信号 (Get Signals)

获取最新分析出的舆情信号。

- **Endpoint**: `GET /api/v1/signals`
- **Auth**: 需要
- **Query Parameters**:
  - `limit`: 返回条数 (默认为 20, 最大 100)
  - `min_sentiment`: 筛选最低情绪分 (0-10)
  - `symbol`: 筛选特定币种/资产 (如 "BTC", "DOGE")
  - `signal_type`: 筛选信号类型 (`BUY`, `SELL`, `WATCH`, `NEUTRAL`)
  - `author`: 筛选特定博主 (如 "elonmusk")

**请求示例**:
```bash
curl -H "X-API-Key: your_secret_key" \
     "http://localhost:8002/api/v1/signals?limit=10&symbol=BTC&min_sentiment=7"
```

**响应示例**:
```json
{
  "status": "success",
  "timestamp": 1703491200,
  "data": [
    {
      "id": "tweet_1234567890",
      "author": "elonmusk",
      "avatar_url": "https://...",
      "summary": "Elon 提到 Dogecoin 将集成到 X 支付中...",
      "original_text": "Dogecoin is the people's crypto...",
      "signal": "BUY",
      "sentiment": 9,
      "assets": ["DOGE"],
      "tweet_url": "https://twitter.com/elonmusk/status/...",
      "time_ago": "5 mins ago",
      "publish_timestamp": 1703491000,
      "tags": ["大佬", "DOGE"]
    }
  ]
}
```

### 3. 获取监控用户 (Get Users)

获取当前正在监控的 Twitter 用户列表及其标签信息。

- **Endpoint**: `GET /api/v1/users`
- **Auth**: 需要

### 4. 获取统计信息 (Get Stats)

获取系统运行统计数据。

- **Endpoint**: `GET /api/v1/stats`
- **Auth**: 需要

## 集成指南

如果您有外部服务（如量化交易机器人、行情看板）需要使用 X-Alpha 的数据：

1. **部署**: 确保 X-Alpha 服务已启动 (`./start.sh`).
2. **网络**: 确保可以访问服务器的 8002 端口.
3. **轮询**: 建议每 1-5 分钟调用一次 `/api/v1/signals` 接口获取最新信号.
4. **过滤**: 根据 `signal_type` 和 `sentiment` (情绪分) 过滤出高价值信号.
   - 建议重点关注 `signal_type="BUY"` 或 `signal_type="SELL"` 且 `sentiment >= 7` (或 `<= 3` 对于做空) 的信号.
