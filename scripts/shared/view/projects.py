"""登记本机查看器服务，并把启动请求交给最近使用的浏览器页面。"""

from __future__ import annotations

import http.client
import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from instance import LOOPBACK_HOST


def _directory() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache_root / "zview" / "projects"


def register(port: int, root: Path) -> Path:
    """登记服务端口和项目目录，返回服务退出时清理的文件路径。"""
    directory = _directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = directory / f"{port}-{os.getpid()}.json"
    temporary = record.with_suffix(".tmp")
    temporary.write_text(json.dumps(str(root)), encoding="utf-8")
    temporary.replace(record)
    return record


def active_projects() -> list[dict]:
    """列出仍在运行的本机项目，忽略失效或损坏的记录。"""
    projects = []
    for record in _directory().glob("*.json"):
        try:
            port, pid = map(int, record.stem.split("-"))
            if os.name == "nt":
                # Windows 的 os.kill(pid, 0) 可能终止进程，改探测回环监听端口。
                with socket.socket() as probe:
                    probe.settimeout(0.2)
                    if probe.connect_ex((LOOPBACK_HOST, port)):
                        continue
            else:
                os.kill(pid, 0)
            root = Path(json.loads(record.read_text(encoding="utf-8")))
        except ProcessLookupError:
            record.unlink(missing_ok=True)
            continue
        except (ValueError, TypeError, OSError):
            continue
        projects.append({"port": port, "root": str(root), "name": root.name or str(root)})
    return sorted(projects, key=lambda project: project["root"])


class BrowserTabs:
    """管理本服务上的等待页面和需要页面确认的切换请求。"""

    def __init__(self) -> None:
        """初始化活动页和请求表。"""
        self.condition = threading.Condition()
        self.tabs: dict[str, tuple[float, float]] = {}
        self.pending: dict[str, dict] = {}

    def recent(self) -> dict[str, float]:
        """返回近期仍有联系的页面及其最后使用时间。"""
        with self.condition:
            cutoff = time.monotonic() - 30
            self.tabs = {tab: stamp for tab, stamp in self.tabs.items() if stamp[1] > cutoff}
            return {tab: stamp[0] for tab, stamp in self.tabs.items()}

    def handle(self, body: dict) -> dict:
        """处理同源页面的等待、活动通知、确认，以及启动器的投递。"""
        tab = body.get("tab")
        if not isinstance(tab, str) or len(tab) > 64:
            return {}
        action = body.get("action")
        with self.condition:
            if action == "leave":
                self.tabs.pop(tab, None)
                self.condition.notify_all()
                return {}
            if action == "deliver":
                return self._deliver(tab, body.get("url"))
            if action == "ack":
                command = self.pending.get(tab)
                if command and command["id"] == body.get("id"):
                    command["accepted"] = True
                    self.condition.notify_all()
                    return {"accepted": True}
                return {}
            if action not in ("wait", "focus"):
                return {}
            previous_focus = self.tabs.get(tab, (0, 0))[0]
            self.tabs[tab] = (
                time.time() if action == "focus" else previous_focus,
                time.monotonic(),
            )
            if action == "focus":
                return {}
            self.condition.wait_for(lambda: tab in self.pending or tab not in self.tabs, timeout=12)
            return {"command": self.pending.get(tab)}

    def _deliver(self, tab: str, url: object) -> dict:
        if tab not in self.tabs or tab in self.pending or not isinstance(url, str):
            return {}
        try:
            target = urlsplit(url)
        except ValueError:
            return {}
        if (
            target.path != "/"
            or not any(
                target.netloc == f"{LOOPBACK_HOST}:{project['port']}"
                for project in active_projects()
            )
            or target.scheme != "http"
        ):
            return {}
        command = {"id": uuid.uuid4().hex, "url": url, "accepted": False}
        self.pending[tab] = command
        try:
            self.condition.notify_all()
            self.condition.wait_for(lambda: command["accepted"], timeout=1.2)
            return {"accepted": command["accepted"]}
        finally:
            del self.pending[tab]
            if not command["accepted"]:
                self.tabs.pop(tab, None)


def _contact(port: int, body: dict | None = None) -> dict:
    connection = http.client.HTTPConnection(LOOPBACK_HOST, port, timeout=2)
    try:
        if body is None:
            connection.request("GET", "/api/project-tabs")
        else:
            connection.request(
                "POST", "/api/project-tabs", json.dumps(body), {"Content-Type": "application/json"}
            )
        response = connection.getresponse()
        return json.loads(response.read()) if response.status == 200 else {}
    except (OSError, ValueError, http.client.HTTPException):
        return {}
    finally:
        connection.close()


def hand_off(url: str) -> bool:
    """依最近使用顺序投递 URL，页面确认后停止尝试。"""
    candidates = []
    for project in active_projects():
        port = project["port"]
        for tab, focused in _contact(port).get("tabs", {}).items():
            candidates.append((focused, port, tab))
    for _, port, tab in sorted(candidates, reverse=True):
        if _contact(port, {"action": "deliver", "tab": tab, "url": url}).get("accepted"):
            return True
    return False
