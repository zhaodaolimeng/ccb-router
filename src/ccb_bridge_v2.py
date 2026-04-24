#!/usr/bin/env python3
"""
CCB (Claude Code) 桥接 - 最终版
修复编码问题
"""

import subprocess
import json
import threading
import time
import sys
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class UserSession:
    """用户会话"""
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    working_dir: Optional[str] = None  # 用户的工作目录
    permission_mode: str = "dontAsk"  # 权限模式
    has_continued: bool = False  # 是否已使用过 --continue
    ccb_session_id: Optional[str] = None  # CCB 会话 ID，用于恢复对话


class CCBSimpleBridge:
    """CCB 桥接 - 使用 --print 模式"""

    def __init__(self, timeout_seconds: int = 120, config_dir: str = None):
        self.timeout = timeout_seconds
        self.sessions: Dict[str, UserSession] = {}
        self.lock = threading.Lock()

        # 配置目录
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), '..', '.user_configs')
        self.config_dir = os.path.abspath(config_dir)
        os.makedirs(self.config_dir, exist_ok=True)

        # 加载已保存的用户配置
        self._load_all_user_configs()

    def _get_user_config_path(self, user_id: str) -> str:
        """获取用户配置文件路径"""
        safe_filename = user_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self.config_dir, f'{safe_filename}.json')

    def _save_user_config(self, session: UserSession):
        """保存用户配置到文件"""
        config_path = self._get_user_config_path(session.user_id)
        config = {
            'user_id': session.user_id,
            'working_dir': session.working_dir,
            'permission_mode': session.permission_mode,
            'ccb_session_id': session.ccb_session_id,
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[CCB] Saved config for {session.user_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")

    def _load_all_user_configs(self):
        """加载所有已保存的用户配置"""
        if not os.path.exists(self.config_dir):
            return

        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                try:
                    config_path = os.path.join(self.config_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        user_id = config.get('user_id')
                        if user_id:
                            session = UserSession(user_id=user_id)
                            session.working_dir = config.get('working_dir')
                            session.permission_mode = config.get('permission_mode', 'dontAsk')
                            session.ccb_session_id = config.get('ccb_session_id')
                            # 如果有 session_id，设置 has_continued 为 True
                            if session.ccb_session_id:
                                session.has_continued = True
                            self.sessions[user_id] = session
                            print(f"[CCB] Loaded config for {user_id}" + (f" (session: {session.ccb_session_id[:8]}...)" if session.ccb_session_id else ""))
                except Exception as e:
                    print(f"[ERROR] Failed to load config file {filename}: {e}")

    def get_session(self, user_id: str) -> UserSession:
        """获取或创建会话"""
        with self.lock:
            if user_id in self.sessions:
                session = self.sessions[user_id]
                session.last_active = datetime.now()
                session.request_count += 1
                return session

            session = UserSession(user_id=user_id)
            self.sessions[user_id] = session
            return session

    def set_working_dir(self, user_id: str, dir_path: str) -> str:
        """设置用户的工作目录"""
        session = self.get_session(user_id)
        if dir_path and os.path.isdir(dir_path):
            session.working_dir = os.path.abspath(dir_path)
            self._save_user_config(session)
            return f"[OK] 工作目录已切换到: {session.working_dir}\n(配置已保存)"
        else:
            return f"[ERROR] 目录不存在: {dir_path}"

    def get_working_dir(self, user_id: str) -> Optional[str]:
        """获取用户的工作目录"""
        with self.lock:
            if user_id in self.sessions:
                return self.sessions[user_id].working_dir
            return None

    def set_permission_mode(self, user_id: str, mode: str) -> str:
        """设置用户的权限模式"""
        valid_modes = ["default", "dontAsk", "acceptEdits", "bypassPermissions", "plan"]
        session = self.get_session(user_id)

        # 支持数字选择
        mode_map = {
            "1": "default",
            "2": "dontAsk",
            "3": "acceptEdits",
            "4": "bypassPermissions",
            "5": "plan"
        }

        if mode in mode_map:
            mode = mode_map[mode]

        if mode not in valid_modes:
            return f"[ERROR] 无效的权限模式: {mode}\n可用模式: {', '.join(valid_modes)}"

        session.permission_mode = mode
        self._save_user_config(session)
        return f"[OK] 权限模式已设置为: {mode}\n(配置已保存)"

    def get_permission_mode(self, user_id: str) -> str:
        """获取用户的权限模式"""
        with self.lock:
            if user_id in self.sessions:
                return self.sessions[user_id].permission_mode
            return "dontAsk"

    def reset_session(self, user_id: str) -> str:
        """重置用户会话（清除 --continue 状态和会话 ID）"""
        with self.lock:
            if user_id in self.sessions:
                self.sessions[user_id].has_continued = False
                self.sessions[user_id].ccb_session_id = None
                self._save_user_config(self.sessions[user_id])
                return "[OK] 会话已重置，将开始新对话"
            return "[OK] 会话已重置"

    def _run_query_once(self, session, query: str, progress_callback, use_session: bool = True):
        """运行一次查询，返回 (output, success)"""
        cwd = session.working_dir
        permission_mode = session.permission_mode

        # 构建命令 - 使用 stream-json 格式实现实时输出
        cmd = [
            'ccb',
            '--print',
            '--verbose',
            '--output-format', 'stream-json',
            '--include-partial-messages',
            '--permission-mode', permission_mode
        ]

        # 使用 --resume 恢复会话（如果有保存的 session_id），否则用 --continue
        if use_session and session.ccb_session_id:
            cmd.append('--resume')
            cmd.append(session.ccb_session_id)
            print(f"[CCB] Resuming session: {session.ccb_session_id[:8]}...")
        elif use_session and session.has_continued:
            cmd.append('--continue')
        elif use_session:
            session.has_continued = True

        cmd.append(query)

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            bufsize=0,
            universal_newlines=False
        )

        # 用于累积输出的变量
        full_output = ""
        accumulated_text = ""
        buffer = bytearray()
        session_failed = False

        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break

                buffer.extend(chunk)

                # 尝试按行解析 JSON
                try:
                    text = buffer.decode('utf-8')
                    lines = text.split('\n')

                    # 处理完整的行
                    for line in lines[:-1]:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                msg_type = data.get('type')

                                # 捕获 session_id
                                sid = data.get('session_id')
                                if sid and session.ccb_session_id != sid:
                                    session.ccb_session_id = sid
                                    self._save_user_config(session)
                                    print(f"[CCB] Saved session ID: {sid[:8]}...")

                                if msg_type == 'stream_event':
                                    event = data.get('event', {})
                                    event_type = event.get('type')

                                    if event_type == 'content_block_delta':
                                        delta = event.get('delta', {})
                                        # 处理 text_delta 和 thinking_delta 两种类型
                                        delta_text = delta.get('text', '') or delta.get('thinking', '')
                                        if delta_text:
                                            # 只有 text 类型的内容才展示给用户
                                            delta_type = delta.get('type', '')
                                            if delta_type == 'text_delta' or (not delta_type and delta.get('text')):
                                                accumulated_text += delta_text
                                                # 调用进度回调
                                                if progress_callback:
                                                    try:
                                                        progress_callback(accumulated_text)
                                                    except:
                                                        pass

                                elif msg_type == 'assistant':
                                    # 完整的助手消息
                                    message = data.get('message', {})
                                    content = message.get('content', [])
                                    # 查找 text 类型的内容块（可能有多个，比如 thinking 和 text）
                                    for block in content:
                                        if block.get('type') == 'text' or block.get('text'):
                                            full_output = block.get('text', '')
                                            break

                                elif msg_type == 'result':
                                    # 最终结果
                                    subtype = data.get('subtype', '')
                                    is_error = data.get('is_error', False)

                                    if subtype == 'error_during_execution' or is_error:
                                        session_failed = True
                                        print(f"[CCB] Session failed during execution")

                                    result = data.get('result', '')
                                    if result:
                                        full_output = result

                            except json.JSONDecodeError:
                                # 不是 JSON，可能是调试输出，忽略
                                pass

                    # 保留不完整的行
                    if lines[-1]:
                        buffer = bytearray(lines[-1], 'utf-8')
                    else:
                        buffer = bytearray()

                except UnicodeDecodeError:
                    # 继续累积
                    pass

            # 等待进程结束
            process.wait(timeout=self.timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return f"Error: Request timed out ({self.timeout}s)", False

        # 读取 stderr
        stderr_data = process.stderr.read()
        err_output = ""
        if stderr_data:
            for encoding in ['utf-8', 'gbk', 'latin-1']:
                try:
                    err_output = stderr_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                err_output = stderr_data.decode('utf-8', errors='replace')

        if err_output:
            full_output += "\n[stderr]\n" + err_output

        # 如果没有通过 JSON 获取到输出，回退到传统方式
        if not full_output and buffer:
            for encoding in ['utf-8', 'gbk', 'latin-1']:
                try:
                    full_output = buffer.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                full_output = buffer.decode('utf-8', errors='replace')

        success = not (process.returncode != 0 and not full_output)
        if not success:
            full_output = f"Command failed, return code: {process.returncode}"

        return full_output, success, session_failed

    def send_query(self, user_id: str, query: str, progress_callback=None) -> str:
        """发送查询给 CCB - 使用 --continue 保持会话，支持 stream-json 实时输出

        Args:
            user_id: 用户 ID
            query: 查询内容
            progress_callback: 回调函数，签名为 callback(text: str) -> None
                              特殊值 "started" 表示开始，空字符串表示结束
        """
        session = self.get_session(user_id)

        try:
            print(f"[CCB] User {user_id} query: {query[:80]}...")

            # 通知开始处理
            if progress_callback:
                try:
                    progress_callback("started")
                except:
                    pass

            # 第一次尝试：使用 session（如果有）
            full_output, success, session_failed = self._run_query_once(
                session, query, progress_callback, use_session=True
            )

            # 如果 session 失败了，清除 session 并重试一次
            if not success or session_failed:
                print(f"[CCB] First attempt failed, retrying without session...")
                session.ccb_session_id = None
                session.has_continued = False
                self._save_user_config(session)

                # 重试，不使用 session
                full_output, success, _ = self._run_query_once(
                    session, query, progress_callback, use_session=False
                )

            # 通知结束
            if progress_callback:
                try:
                    progress_callback("")
                except:
                    pass

            print(f"[CCB] Response: {len(full_output)} chars")
            return full_output

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"


# 单例
_bridge_instance = None


def get_bridge() -> CCBSimpleBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = CCBSimpleBridge()
    return _bridge_instance
