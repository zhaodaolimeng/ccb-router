# Claude Code 参考

本项目使用的 Claude Code 是 **claude-code-best** 三方实现。

---

## 项目信息

| 项目 | 链接 |
|------|------|
| GitHub | https://github.com/claude-code-best/claude-code |
| 官方文档 | https://ccb.agent-aura.top/ |
| Discord | https://discord.gg/qZU6zS7Q |

---

## 项目介绍

claude-code-best/claude-code 是 Anthropic 官方 Claude Code CLI 工具的逆向还原项目，旨在复现其核心功能与工程化能力，提供可运行、可构建、可调试的版本。

---

## 主要功能特性

| 功能 | 说明 | 文档链接 |
|------|------|----------|
| Claude 群控技术 | Pipe IPC 多实例协作（同机编排+跨机发现），`/pipes` 面板交互 | [文档](https://ccb.agent-aura.top/docs/features/pipes-and-lan) |
| ACP 协议支持 | 接入 Zed、Cursor 等 IDE，会话恢复与权限桥接 | [文档](https://ccb.agent-aura.top/docs/features/acp-zed) |
| Remote Control 部署 | Docker 自托管 RCS+Web UI | [文档](https://ccb.agent-aura.top/docs/features/remote-control-self-hosting) |
| 智能记忆整理 | `/dream` 自动优化记忆文件 | [文档](https://ccb.agent-aura.top/docs/features/auto-dream) |
| 网页搜索工具 | 内置浏览器搜索功能 | [文档](https://ccb.agent-aura.top/docs/features/web-browser-tool) |
| 多模型兼容 | 支持 OpenAI/Anthropic/Gemini/Grok 等 API | [文档](https://ccb.agent-aura.top/docs/features/custom-platform-login) |
| 语音输入模式 | Push-to-Talk 语音交互 | [文档](https://ccb.agent-aura.top/docs/features/voice-mode) |
| 计算机控制 | 屏幕截图与键鼠操作 | [文档](https://ccb.agent-aura.top/docs/features/computer-use) |
| 浏览器自动化 | Chrome 操作、表单填写与数据抓取 | [文档](https://ccb.agent-aura.top/docs/features/chrome-use-mcp) |
| 企业级监控 | Sentry 错误追踪 | [文档](https://ccb.agent-aura.top/docs/internals/sentry-setup) |
| 特性开关管理 | GrowthBook 企业级功能配置 | [文档](https://ccb.agent-aura.top/docs/internals/growthbook-adapter) |
| 全链路追踪 | Langfuse LLM 调用与工具执行监控 | [文档](https://ccb.agent-aura.top/docs/features/langfuse-monitoring) |
| 资源优化模式 | Poor Mode 关闭记忆与建议功能（`/poor` 命令） | - |

---

## 快速启动方式

### 安装版

```bash
# Node.js 版本
bun i -g claude-code-best
ccb

# Bun 运行版本
bun i -g claude-code-best
ccb-bun
```

### 源码版

```bash
bun install
bun run dev  # 开发模式
```

---

## 与本项目的集成

本项目通过 `ccb --print <query>` 命令调用 Claude Code：

- **使用 `--permission-mode dontAsk`** - 避免交互式授权提示
- **支持 `--add-dir`** - 添加允许访问的目录
- **支持 `--working-dir`** - 指定工作目录（本项目通过 `cwd` 参数实现）

### 权限模式选项

| 模式 | 说明 |
|------|------|
| `default` | 默认，需要交互式授权 |
| `dontAsk` | 不询问，直接执行操作（本项目使用） |
| `acceptEdits` | 接受编辑操作 |
| `bypassPermissions` | 绕过所有权限检查 |
| `plan` | 只规划不执行 |

还有 `--dangerously-skip-permissions` 可以完全绕过权限检查（适合沙箱环境）。

---

## 相关链接

- 本项目飞书桥接: [feishu_ws.py](../src/feishu_ws.py)
- CCB 桥接层: [ccb_bridge_v2.py](../src/ccb_bridge_v2.py)
- 官方样例参考: [OFFICIAL_EXAMPLES.md](./OFFICIAL_EXAMPLES.md)

