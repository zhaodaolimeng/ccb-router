#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 ↔ Claude Code 桥接 - WebSocket 长连接版本
使用 lark_oapi SDK 的 WebSocket 方式，无需 ngrok！
严格按照飞书官方文档实现
"""

import json
import os
import time

# 导入 CCB 桥接 - 稳定版本
from ccb_bridge_v2 import get_bridge

# 导入飞书 SDK
import lark_oapi as lark
from lark_oapi.api.im.v1 import *


# 配置
CONFIG = {
    'feishu': {
        'app_id': os.environ.get('FEISHU_APP_ID', ''),
        'app_secret': os.environ.get('FEISHU_APP_SECRET', ''),
    }
}

# 从 config.json 加载配置
CONFIG_PATH = 'config.json'
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
            if 'feishu' in file_config:
                CONFIG['feishu'].update(file_config['feishu'])
    except Exception as e:
        print(f"Warning: Could not load config.json: {e}")


# 全局变量
bridge = get_bridge()
client = None
processed_event_ids = set()  # 记录已处理的事件 ID，避免重复


def send_message_to_user(user_id: str, text: str):
    """发送消息给用户"""
    global client
    if not client:
        print(f"[模拟发送] 给 {user_id}:")
        print("-" * 40)
        print(text[:500] + "..." if len(text) > 500 else text)
        print("-" * 40)
        return True

    try:
        # 分割长消息
        max_len = 2000
        parts = []
        if len(text) <= max_len:
            parts = [text]
        else:
            remaining = text
            while remaining:
                if len(remaining) <= max_len:
                    parts.append(remaining)
                    break
                split_idx = remaining.rfind('\n', 0, max_len)
                if split_idx == -1:
                    split_idx = max_len
                parts.append(remaining[:split_idx])
                remaining = remaining[split_idx:]

        success = True
        for i, part in enumerate(parts):
            send_text = part
            if len(parts) > 1:
                send_text = f"({i+1}/{len(parts)})\n{send_text}"

            # 构造请求 - 严格按照 SDK 规范
            request = CreateMessageRequest.builder() \
                .receive_id_type("open_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("text")
                    .content(json.dumps({"text": send_text}))
                    .build()) \
                .build()

            # 发送请求
            response = client.im.v1.message.create(request)

            if response.success():
                print(f"[OK] 消息 {i+1} 发送成功")
            else:
                print(f"[ERROR] 消息 {i+1} 发送失败: {response.code}, {response.msg}")
                success = False

            if len(parts) > 1:
                import time
                time.sleep(0.5)

        return success

    except Exception as e:
        print(f"[ERROR] 发送消息异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理收到的消息 - 严格按照官方文档命名"""
    print(f"\n{'='*60}")
    print("收到飞书消息事件")
    print(f"{'='*60}")

    # 打印完整事件数据用于调试
    print(f"[DEBUG] 完整事件数据: {lark.JSON.marshal(data)}")

    try:
        # 1. 先用 event_id 去重（最优先）
        event_id = None
        if hasattr(data, 'header') and hasattr(data.header, 'event_id'):
            event_id = data.header.event_id

        if event_id:
            if event_id in processed_event_ids:
                print(f"[跳过] 事件已处理: {event_id}")
                return
            processed_event_ids.add(event_id)

            # 保留最近 1000 个事件 ID，防止内存泄漏
            if len(processed_event_ids) > 1000:
                processed_event_ids.clear()
                print("[INFO] 清空已处理事件 ID 缓存")

        # 获取发送者 ID
        sender = data.event.sender
        sender_id = sender.sender_id.open_id

        # 获取消息内容
        message = data.event.message
        message_id = message.message_id
        content = message.content

        # 检查是否是历史消息（通过时间戳判断）
        import time
        current_time = int(time.time())
        # create_time 是字符串类型的毫秒时间戳
        create_time_ms = 0
        if hasattr(message, 'create_time') and message.create_time:
            try:
                create_time_ms = int(message.create_time)
            except (ValueError, TypeError):
                pass
        create_time_sec = create_time_ms // 1000 if create_time_ms > 0 else 0
        time_diff = current_time - create_time_sec if create_time_sec > 0 else 0
        if time_diff > 300:  # 超过 5 分钟的消息跳过
            print(f"[跳过] 历史消息，创建于 {time_diff} 秒前 (event_id: {event_id}, message_id: {message_id})")
            return

        # 解析文本
        try:
            content_dict = json.loads(content)
            text = content_dict.get('text', '').strip()
        except:
            text = content.strip()

        if not text:
            print("[WARN] 空消息")
            return

        print(f"来自: {sender_id}")
        print(f"消息: {text[:100]}...")

        # 处理特殊命令
        if text.startswith('/dir '):
            # 切换目录命令: /dir xxx
            dir_path = text[5:].strip()
            response = bridge.set_working_dir(sender_id, dir_path)
        elif text == '/dir':
            # 查看当前目录
            current_dir = bridge.get_working_dir(sender_id)
            if current_dir:
                response = f"当前工作目录: {current_dir}"
            else:
                response = "当前未设置工作目录，使用默认目录"
        elif text.startswith('/auth '):
            # 设置权限模式: /auth 2 或 /auth dontAsk
            mode = text[6:].strip()
            response = bridge.set_permission_mode(sender_id, mode)
        elif text == '/auth':
            # 查看当前权限模式并显示选项
            current_mode = bridge.get_permission_mode(sender_id)
            response = f"""当前权限模式: {current_mode}

可用权限模式:
1 - default (默认，需要交互式授权)
2 - dontAsk (不询问，直接执行) ⭐
3 - acceptEdits (仅接受编辑)
4 - bypassPermissions (绕过所有权限)
5 - plan (仅规划不执行)

使用 /auth <数字/名称> 来切换，例如:
/auth 2
/auth dontAsk"""
        elif text == '/reset':
            # 重置会话
            response = bridge.reset_session(sender_id)
        elif text == '/help':
            # 帮助命令
            response = """可用命令:
/dir <路径> - 切换工作目录
/dir - 查看当前工作目录
/auth <模式> - 设置权限模式
/auth - 查看权限模式选项
/reset - 重置会话，开始新对话
/help - 显示帮助信息"""
        else:
            # 调用 Claude Code - 支持实时进度推送
            last_send_time = time.time()
            send_interval = 3.0  # 每 3 秒推送一次
            has_sent_progress = False
            last_text_length = 0

            def progress_callback(current_text):
                nonlocal last_send_time, has_sent_progress, last_text_length

                if current_text == "started":
                    # 开始处理
                    send_message_to_user(sender_id, "[正在处理...]\n请稍候，任务执行中...")
                    has_sent_progress = True

                elif current_text == "":
                    # 结束，不做额外处理
                    pass

                elif current_text:
                    # 有新内容
                    current_time = time.time()
                    new_content = current_text[last_text_length:]

                    # 满足条件时发送进度更新
                    if (current_time - last_send_time >= send_interval and
                        len(new_content) >= 100):  # 至少 100 新字符
                        # 只显示新增的内容
                        status_msg = f"[进行中...]\n{new_content}"
                        send_message_to_user(sender_id, status_msg)

                        last_send_time = current_time
                        last_text_length = len(current_text)

            response = bridge.send_query(sender_id, text, progress_callback=progress_callback)

        # 发送最终回复
        print(f"\n回复长度: {len(response)} 字符")
        send_message_to_user(sender_id, response)

    except Exception as e:
        print(f"[ERROR] 处理消息异常: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数 - 严格按照官方文档结构"""
    global client

    print("="*60)
    print("飞书 ↔ Claude Code 桥接 - WebSocket 长连接版本")
    print("="*60)

    app_id = CONFIG['feishu'].get('app_id', '')
    app_secret = CONFIG['feishu'].get('app_secret', '')

    # 检查配置
    if not app_id or app_id == 'cli_xxxxxxxxxx':
        print("[ERROR] 请先配置 config.json 中的飞书 App ID 和 App Secret")
        return

    # 创建 SDK 客户端（用于发送消息）
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    # 创建事件处理器 - 严格按照官方文档，两个参数留空
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    # 创建 WebSocket 客户端
    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )

    print("\n[OK] WebSocket 客户端已创建")
    print("[OK] 无需 ngrok，直接连接飞书服务器")
    print("\n" + "="*60)
    print("正在启动长连接...")
    print("="*60)
    print("\n提示: 在飞书中给机器人发消息即可开始对话\n")

    # 启动 WebSocket
    try:
        ws_client.start()
    except KeyboardInterrupt:
        print("\n\n正在停止...")
    except Exception as e:
        print(f"\n[ERROR] WebSocket 连接异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

