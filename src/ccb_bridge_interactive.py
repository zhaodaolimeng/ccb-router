#!/usr/bin/env python3
"""
CCB (Claude Code) 桥接 - 持久交互式版本
为每个用户保持一个持久的 ccb 进程，可以随时补充消息
支持用户配置持久化
"""

import subprocess
import threading
import time
import sys
import os
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class UserSession:
    """用户会话 - 交互式版本"""
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    working_dir: Optional[str] = None
    permission_mode: str = "dontAsk"
    # 交互式进程相关
    process: Optional[subprocess.Popen] = None
    output_thread: Optional[threading.Thread] = None
    output_buffer: str = ""
    output_lock: threading.Lock = field(default_factory=threading.Lock)
    is_running: bool = False


class CCBInteractiveBridge:
    """CCB 桥接 - 持久交互式模式"""

    def __init__(self, timeout_seconds: int = 300, config_dir: str = None):
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
        # 使用安全的文件名
        safe_filename = user_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self.config_dir, f'{safe_filename}.json')

    def _save_user_config(self, session: UserSession):
        """保存用户配置到文件"""
        config_path = self._get_user_config_path(session.user_id)
        config = {
            'user_id': session.user_id,
            'working_dir': session.working_dir,
            'permission_mode': session.permission_mode,
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[CCB] Saved config for {session.user_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")

    def _load_user_config(self, user_id: str) -> Optional[Dict]:
        """从文件加载用户配置"""
        config_path = self._get_user_config_path(user_id)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] Failed to load config: {e}")
        return None

    def _load_all_user_configs(self):
        """加载所有已保存的用户配置（不启动进程）"""
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
                            # 创建会话对象但不启动进程
                            session = UserSession(user_id=user_id)
                            session.working_dir = config.get('working_dir')
                            session.permission_mode = config.get('permission_mode', 'dontAsk')
                            self.sessions[user_id] = session
                            print(f"[CCB] Loaded config for {user_id}")
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

    def _start_session_process(self, session: UserSession) -> bool:
        """启动用户的 ccb 进程"""
        if session.process and session.process.poll() is None:
            return True  # 已在运行

        try:
            # 结束旧进程（如果存在）
            self._stop_session_process(session)

            cwd = session.working_dir
            cmd = [
                'ccb',
                '--permission-mode', session.permission_mode,
            ]

            print(f"[CCB] Starting interactive process for {session.user_id}")

            session.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
                cwd=cwd,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            session.is_running = True
            session.output_buffer = ""

            # 启动输出读取线程
            session.output_thread = threading.Thread(
                target=self._read_output,
                args=(session,),
                daemon=True
            )
            session.output_thread.start()

            # 等待一点时间让进程启动
            time.sleep(0.5)
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start process: {e}")
            return False

    def _stop_session_process(self, session: UserSession):
        """停止用户的 ccb 进程"""
        session.is_running = False

        if session.process:
            try:
                session.process.stdin.close()
            except:
                pass

            try:
                session.process.terminate()
                try:
                    session.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    session.process.kill()
                    session.process.wait()
            except:
                pass

            session.process = None

    def _read_output(self, session: UserSession):
        """后台线程读取进程输出"""
        try:
            while session.is_running and session.process and session.process.poll() is None:
                try:
                    line = session.process.stdout.readline()
                    if not line:
                        break

                    with session.output_lock:
                        session.output_buffer += line

                except Exception as e:
                    print(f"[ERROR] Read output error: {e}")
                    break
        except Exception as e:
            print(f"[ERROR] Output thread error: {e}")

        session.is_running = False

    def _wait_for_output(self, session: UserSession, timeout: float = 10.0) -> str:
        """等待并获取输出"""
        start_time = time.time()
        last_output_len = 0

        while time.time() - start_time < timeout:
            with session.output_lock:
                current_output = session.output_buffer

            # 如果输出在增长，继续等待
            if len(current_output) > last_output_len:
                last_output_len = len(current_output)
                time.sleep(0.5)
            else:
                # 输出稳定了，再等一小会儿确认
                time.sleep(0.3)
                with session.output_lock:
                    final_output = session.output_buffer
                    if len(final_output) == last_output_len:
                        break

        with session.output_lock:
            output = session.output_buffer
            session.output_buffer = ""  # 清空缓冲区

        return output

    def send_query(self, user_id: str, query: str) -> str:
        """发送查询给 CCB - 交互式版本"""
        session = self.get_session(user_id)

        try:
            print(f"[CCB] User {user_id} query: {query[:80]}...")

            # 确保进程在运行
            if not self._start_session_process(session):
                return "[ERROR] Failed to start Claude Code process"

            # 发送查询
            if session.process and session.process.stdin:
                try:
                    session.process.stdin.write(query + "\n")
                    session.process.stdin.flush()
                except Exception as e:
                    print(f"[ERROR] Write to stdin error: {e}")
                    # 尝试重启进程
                    self._stop_session_process(session)
                    if not self._start_session_process(session):
                        return "[ERROR] Failed to restart Claude Code process"
                    # 重试发送
                    session.process.stdin.write(query + "\n")
                    session.process.stdin.flush()

            # 等待输出
            output = self._wait_for_output(session, timeout=self.timeout)

            if not output or output.strip() == "":
                output = "[No output received]"

            print(f"[CCB] Response: {len(output)} chars")
            return output

        except Exception as e:
            print(f"[ERROR] Send query exception: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"

    def set_working_dir(self, user_id: str, dir_path: str) -> str:
        """设置用户的工作目录（需要重启进程）"""
        import os
        session = self.get_session(user_id)

        if dir_path and os.path.isdir(dir_path):
            session.working_dir = os.path.abspath(dir_path)
            # 保存配置到文件
            self._save_user_config(session)
            # 重启进程以应用新目录
            self._stop_session_process(session)
            return f"[OK] 工作目录已切换到: {session.working_dir}\n(进程已重启，配置已保存)"
        else:
            return f"[ERROR] 目录不存在: {dir_path}"

    def get_working_dir(self, user_id: str) -> Optional[str]:
        """获取用户的工作目录"""
        with self.lock:
            if user_id in self.sessions:
                return self.sessions[user_id].working_dir
            return None

    def set_permission_mode(self, user_id: str, mode: str) -> str:
        """设置用户的权限模式（需要重启进程）"""
        valid_modes = ["default", "dontAsk", "acceptEdits", "bypassPermissions", "plan"]
        session = self.get_session(user_id)

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
        # 保存配置到文件
        self._save_user_config(session)
        # 重启进程以应用新模式
        self._stop_session_process(session)
        return f"[OK] 权限模式已设置为: {mode}\n(进程已重启，配置已保存)"

    def get_permission_mode(self, user_id: str) -> str:
        """获取用户的权限模式"""
        with self.lock:
            if user_id in self.sessions:
                return self.sessions[user_id].permission_mode
            return "dontAsk"

    def reset_session(self, user_id: str) -> str:
        """重置用户会话（重启进程）"""
        session = self.get_session(user_id)
        self._stop_session_process(session)
        return "[OK] 会话已重置"

    def cleanup_idle_sessions(self, idle_seconds: int = 3600):
        """清理空闲会话"""
        now = datetime.now()
        with self.lock:
            to_remove = []
            for user_id, session in self.sessions.items():
                idle_time = (now - session.last_active).total_seconds()
                if idle_time > idle_seconds:
                    self._stop_session_process(session)
                    to_remove.append(user_id)

            for user_id in to_remove:
                del self.sessions[user_id]
                print(f"[CCB] Cleaned up idle session: {user_id}")


# 单例
_bridge_instance = None


def get_bridge() -> CCBInteractiveBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = CCBInteractiveBridge()
    return _bridge_instance

