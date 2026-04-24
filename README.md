# 飞书 ↔ Claude Code 桥接

## 项目目标

通过飞书（Lark）机器人与本地运行的 Claude Code 进行交互，实现在飞书聊天中直接操作 Claude Code 的功能。

## 关于 Claude Code

本项目使用的是 **claude-code-best** 三方实现：

- GitHub: https://github.com/claude-code-best/claude-code
- 官方文档: https://ccb.agent-aura.top/
- Discord: https://discord.gg/qZU6zS7Q

这是 Anthropic 官方 Claude Code CLI 工具的逆向还原项目，提供了丰富的增强功能：
- Claude 群控技术（多实例协作）
- ACP 协议支持（接入 Zed、Cursor 等 IDE）
- 智能记忆整理（`/dream` 命令）
- 网页搜索工具
- 多模型兼容（OpenAI/Anthropic/Gemini/Grok）
- 语音输入模式
- 计算机控制（屏幕截图与键鼠操作）
- 浏览器自动化
- 更多企业级特性...

### 核心功能

- ✅ 在飞书中给机器人发送消息
- ✅ 消息自动转发到本地 Claude Code
- ✅ Claude Code 的响应自动返回给飞书用户
- ✅ 支持长消息自动分割
- ✅ **无需 ngrok/内网穿透**（使用 WebSocket 长连接）
- ✅ 无需手动复制粘贴，完全在飞书中完成对话

---

## 设计方案

### 架构图

```
┌─────────────┐
│   飞书用户   │
│  (发送消息)  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  飞书服务器     │
│  (WebSocket)    │
└──────┬──────────┘
       │ WSS (双向长连接)
       ▼
┌─────────────────────────────┐
│  feishu_ws.py (本地服务)    │
│  - WebSocket 客户端         │
│  - 飞书 SDK 消息解析/发送   │
└──────┬──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  ccb_bridge_v2.py    │
│  Claude Code 桥接     │
└──────┬───────────────┘
       │
       ▼
┌─────────────────────────┐
│  Claude Code (本地进程) │
│  (实际执行代码/任务)    │
└─────────────────────────┘
```

### 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 事件接收 | WebSocket 长连接 | 飞书官方 `lark_oapi.ws.Client`，无需公网 IP |
| 飞书集成 | lark-oapi | 官方 SDK，支持 WebSocket 和 API 调用 |
| Claude Code 交互 | 子进程 + stdin/stdout | 通过命令行调用 Claude Code |

### 为什么选择 WebSocket 长连接？

| 对比项 | WebSocket 方案 | Webhook 方案 |
|--------|----------------|--------------|
| 需要公网 IP | ❌ 不需要 | ✅ 需要 |
| 需要 ngrok | ❌ 不需要 | ✅ 需要 |
| 配置复杂度 | 简单（只需 App ID/Secret） | 复杂（需配置事件订阅地址） |
| 网络要求 | 能上网即可 | 需要端口映射/内网穿透 |
| 飞书后台配置 | 无需配置事件订阅 | 需要配置 Webhook URL |

---

## 快速开始

### 1. 安装依赖

```bash
pip install lark-oapi
```

### 2. 配置飞书应用

编辑 `src/config.json`：

```json
{
  "feishu": {
    "app_id": "cli_xxxxxxxxxx",
    "app_secret": "xxxxxxxxxx"
  }
}
```

### 3. 启动服务

```bash
cd src
python feishu_ws.py
```

### 4. 开始使用

在飞书中给机器人发消息，即可与 Claude Code 对话！

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `README.md` | 本文件 - 项目目标与设计方案 |
| `src/feishu_ws.py` | **推荐使用** - WebSocket 长连接版本 |
| `src/webhook_sdk.py` | Webhook 版本（需要 ngrok） |
| `src/ccb_bridge_v2.py` | Claude Code 桥接层 |
| `src/config.json` | 配置文件 |
| `docs/SDK_GUIDE.md` | SDK 详细使用指南 |
| `docs/OFFICIAL_EXAMPLES.md` | **重要** - 飞书官方样例参考，修改代码前请比对 |
| `docs/CLAUDE_CODE_REF.md` | **重要** - Claude Code 三方实现参考 |

---

## 飞书应用配置（仅首次）

1. 进入 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 App ID 和 App Secret，填入 `config.json`
4. 权限管理：添加以下权限
   - `im:message` - 发送消息
   - `im:message.group_at_msg` - 接收群消息
   - `im:message.p2p_msg` - 接收私聊消息
5. 版本管理与发布：发布版本
6. 无需配置事件订阅（WebSocket 自动接收）

---

## 注意事项

1. **WebSocket 优势**：无需 ngrok，无需公网 IP，配置简单
2. **消息长度限制**：飞书单条消息限制 2000 字符，超长自动分割
3. **飞书应用权限**：确保已申请所需权限并发布版本

