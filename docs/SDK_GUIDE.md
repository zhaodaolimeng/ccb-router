# 飞书 SDK 使用说明

## 架构说明

飞书事件接收方式：
- **Webhook（HTTP POST）** - 唯一官方支持的方式
- **无 WebSocket/长连接** - 飞书不提供这种方式

本项目使用 **Webhook + SDK** 混合方案：
- Webhook 接收事件推送
- SDK 发送消息和解析事件

## 依赖安装

```bash
pip install flask larksuite-oapi
```

## 启动服务

```bash
cd src
python webhook_sdk.py
```

服务默认运行在 `http://0.0.0.0:8000`

## 配置公网访问

### 使用 ngrok

```bash
ngrok http 8000
```

ngrok 会提供一个公网 URL，如：`https://abc123.ngrok.io`

### 飞书后台配置

1. 进入飞书开放平台后台
2. 进入你的应用 → 事件订阅
3. 请求地址：填入 `https://abc123.ngrok.io/webhook`
4. 点击「验证」按钮完成 URL 验证
5. 订阅事件：添加 `接收消息` (im.message.receive_v1)
6. 点击「保存」

## 端点说明

| 端点 | 说明 |
|------|------|
| `/webhook` | 飞书事件接收地址 |
| `/health` | 健康检查 |
| `/test?q=hello` | 测试桥接功能 |

## 测试

1. 启动服务：`python webhook_sdk.py`
2. 访问 `http://localhost:8000/test?q=你好`
3. 配置好 ngrok 和飞书后台后，直接在飞书中给机器人发消息

