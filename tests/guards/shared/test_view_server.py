"""守护本机只读查看器服务端的守卫测试（guard test）。

本文件位于 ``tests/guards/shared/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``scripts/shared/view/server.py``、``launch.py`` 与 ``instance.py``。核心
不变量：

1. **只读是硬边界，不是「本期先不做」。** 服务端不得出现任何写方法处理器名字
   （``do_POST`` / ``do_PUT`` / ``do_DELETE`` / ``do_PATCH``），运行时的写请求一律
   405。逐个定义同名方法会把「服务端根本不存在写入口」变成「服务端有一个专门用来
   拒绝的写入口」，``rg -n "do_POST" scripts/shared/view/`` 这类静态断言会随之失去
   判别力。
2. **路径不得越出仓库。** ``..`` 与符号链接都要在 ``resolve()`` 之后再断言，顺序颠倒
   时符号链接逃逸会漏网；拒绝信息本身也不得回声绝对路径，否则「被拒绝」就成了仓库外
   路径的探测口。
3. **路径参数会变成 git 的位置参数。** 基线必须对本地分支白名单校验，否则
   ``--output=...`` 这类以 ``-`` 开头的取值会被 git 当成选项解析。
4. **界面数字必须与终端逐项一致。** ``--numstat -z`` 的普通条目与重命名条目 token
   数不同；把两者混为一谈会静默漏掉一半改动文件，而界面看上去仍然"有内容"。
5. **陈旧登记必须被接管，且登记清理不得误伤他人。** 复用判定依赖三项交叉校验
   （进程存活 / 端口可连 / 仓库一致）；空闲回收清理登记时要确认登记仍属于自己，
   否则 ``--no-reuse`` 起的更新实例会被旧实例顺手抹掉登记。
6. **服务只绑本机回环地址。** 绑成 ``0.0.0.0`` 会把一个只读接口开给整个局域网。

用例全部打在真实进程与真实 HTTP 上：被测的是绑定、路由分发与 ``git`` 子进程这条
完整链路，桩掉其中任何一段都测不到本文列出的不变量。
"""

from __future__ import annotations

import html
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[3]
_VIEW_SCRIPTS_PATH = _PROJECT_ROOT_PATH / "scripts" / "shared" / "view"
_SERVER_SCRIPT_PATH = _VIEW_SCRIPTS_PATH / "server.py"
_LAUNCH_SCRIPT_PATH = _VIEW_SCRIPTS_PATH / "launch.py"

# server.py / launch.py 不是包的一部分，import 前需把它们所在目录放到 sys.path。
if str(_VIEW_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(_VIEW_SCRIPTS_PATH))

import instance  # noqa: E402
import server  # noqa: E402

_LOOPBACK_HOST = "127.0.0.1"
_SERVER_START_TIMEOUT_SECONDS = 10.0
_SERVER_POLL_INTERVAL_SECONDS = 0.05
_STOP_TIMEOUT_SECONDS = 10.0

#: 超过 ``workspace.MAX_FILE_BYTES``（256 KiB）的正文，用于验「不返回正文」。
_OVERSIZE_BYTE_COUNT = 300 * 1024

_FORBIDDEN_WRITE_METHOD_HANDLER_NAMES = ("do_POST", "do_PUT", "do_DELETE", "do_PATCH")


@dataclass(frozen=True)
class RunningViewServer:
    """一个跑在真实回环端口上的查看器服务，供用例发真实 HTTP 请求。

    Attributes:
        repository_root (Path): 被查看的仓库根。
        port (int): 服务监听端口。
        process_id (int): 服务进程号。
    """

    repository_root: Path
    port: int
    process_id: int

    def request(self, route: str, *, method: str = "GET") -> tuple[int, dict]:
        """对服务发一次真实 HTTP 请求。

        Args:
            route (str): 形如 ``/api/tree`` 的路由（含查询串）。
            method (str): HTTP 方法。

        Returns:
            tuple[int, dict]: 状态码与解析后的 JSON 正文。
        """
        request = urllib.request.Request(  # 目标固定为本机回环
            f"http://{_LOOPBACK_HOST}:{self.port}{route}",
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as http_error:
            return http_error.code, json.loads(http_error.read().decode("utf-8"))

    def request_text(self, route: str) -> tuple[int, str, str]:
        """对服务发一次真实 HTTP 请求，返回原始文本与响应头里的内容类型。

        Args:
            route (str): 路由（含查询串）。

        Returns:
            tuple[int, str, str]: 状态码、正文文本与 ``Content-Type``。
        """
        request = urllib.request.Request(f"http://{_LOOPBACK_HOST}:{self.port}{route}")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return (
                    response.status,
                    response.read().decode("utf-8"),
                    response.headers.get("Content-Type", ""),
                )
        except urllib.error.HTTPError as http_error:
            return http_error.code, http_error.read().decode("utf-8"), ""


def _run_git(repository_path: Path, *git_arguments: str) -> subprocess.CompletedProcess[str]:
    """在指定目录执行 git 命令并返回结果。"""
    return subprocess.run(
        ["git", *git_arguments],
        cwd=repository_path,
        capture_output=True,
        text=True,
        check=True,
    )


def _find_free_port() -> int:
    """取一个本机回环上空闲的端口号。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation_socket:
        reservation_socket.bind((_LOOPBACK_HOST, 0))
        return int(reservation_socket.getsockname()[1])


def _find_defunct_process_id() -> int:
    """取一个确定已经退出的进程号。

    用 ``subprocess`` 起一个立刻退出的进程并 ``wait()`` 收尸，拿到的 pid 在随后的
    探测里必然被判为「进程已退出」——这正是陈旧登记用例需要的输入。
    """
    defunct_process = subprocess.Popen([sys.executable, "-c", "pass"])
    defunct_process.wait()
    return defunct_process.pid


def _build_fixture_repository(repository_root: Path) -> Path:
    """建一个带真实提交、重命名、二进制与超限文件的小仓库。"""
    repository_root.mkdir(parents=True, exist_ok=True)
    _run_git(repository_root, "init", "-b", "main")
    _run_git(repository_root, "config", "user.email", "guard@example.com")
    _run_git(repository_root, "config", "user.name", "guard-test")

    (repository_root / "src").mkdir()
    (repository_root / "src" / "module.py").write_text(
        "def answer():\n    return 42\n", encoding="utf-8"
    )
    # 目录名像构建产物的**受控源码**：按目录名剪枝会把它整棵藏掉，因此这里真的放一份。
    (repository_root / "scripts" / "build").mkdir(parents=True)
    (repository_root / "scripts" / "build" / "tool.py").write_text(
        "BUILD_TOOL = True\n", encoding="utf-8"
    )
    (repository_root / "rename_me.txt").write_text("rename source\n", encoding="utf-8")
    (repository_root / "big.txt").write_text("x" * _OVERSIZE_BYTE_COUNT, encoding="utf-8")
    (repository_root / "blob.bin").write_bytes(b"\x00\x01\x02binary payload")
    _run_git(repository_root, "add", ".")
    _run_git(repository_root, "commit", "-m", "init")

    # 制造一次改动：重命名、文本修改、二进制修改，外加未跟踪文件与未忽略的依赖目录。
    _run_git(repository_root, "mv", "rename_me.txt", "renamed.txt")
    (repository_root / "src" / "module.py").write_text(
        "def answer():\n    return 43\n", encoding="utf-8"
    )
    (repository_root / "blob.bin").write_bytes(b"\x00\x01\x02changed payload")
    (repository_root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    (repository_root / "node_modules").mkdir()
    (repository_root / "node_modules" / "left-pad.js").write_text(
        "module.exports = 1\n", encoding="utf-8"
    )
    return repository_root


@pytest.fixture
def fixture_repository(tmp_path: Path) -> Path:
    """提供一个带真实 git 状态的小仓库。"""
    return _build_fixture_repository(tmp_path / "fixture-repo")


def _wait_until_port_is_listening(port: int) -> bool:
    """轮询端口直到可连接。"""
    deadline_monotonic = time.monotonic() + _SERVER_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline_monotonic:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            probe_socket.settimeout(0.5)
            if probe_socket.connect_ex((_LOOPBACK_HOST, port)) == 0:
                return True
        time.sleep(_SERVER_POLL_INTERVAL_SECONDS)
    return False


@pytest.fixture
def running_view_server(fixture_repository: Path) -> RunningViewServer:
    """拉起一个真实服务进程，并在用例结束后确认它已被收掉。

    清理走「终止进程 + 清登记」，与 ``just view --stop`` 同一条路径：守卫测试自己
    不能变成孤儿进程的来源，这正是 PRD 记录过的那条教训。
    """
    port = _find_free_port()
    server_process = subprocess.Popen(
        [
            sys.executable,
            str(_SERVER_SCRIPT_PATH),
            "--repo-root",
            str(fixture_repository),
            "--port",
            str(port),
            "--idle-timeout",
            "0",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert _wait_until_port_is_listening(
        port
    ), f"查看器服务在 {_SERVER_START_TIMEOUT_SECONDS:.0f} 秒内没有开始监听端口 {port}"
    try:
        yield RunningViewServer(
            repository_root=fixture_repository,
            port=port,
            process_id=server_process.pid,
        )
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait(timeout=_STOP_TIMEOUT_SECONDS)


def _run_launch(repository_root: Path, *launch_arguments: str) -> subprocess.CompletedProcess[str]:
    """在指定仓库里以真实入口运行 ``launch.py``。"""
    return subprocess.run(
        [sys.executable, str(_LAUNCH_SCRIPT_PATH), *launch_arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _stop_recorded_instance(repository_root: Path) -> None:
    """按登记收掉服务进程并清理登记，供用例结束时兜底。"""
    recorded_instance = instance.read_instance_record(repository_root)
    if recorded_instance is not None:
        try:
            os.kill(recorded_instance.process_id, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    instance.clear_instance_record(repository_root)


def test_repository_escape_requests_are_refused(running_view_server: RunningViewServer) -> None:
    """``..``、绝对路径与符号链接三种逃逸都必须被拒，且不回声绝对路径。"""
    outside_file_path = running_view_server.repository_root.parent / "outside-secret.txt"
    outside_file_path.write_text("SECRET-OUTSIDE-CONTENT\n", encoding="utf-8")
    escape_link_path = running_view_server.repository_root / "escape-link"
    escape_link_path.symlink_to(outside_file_path)

    for escape_route in (
        "/api/file?path=../outside-secret.txt",
        "/api/file?path=../../outside-secret.txt",
        "/api/file?path=/etc/hosts",
        "/api/file?path=escape-link",
        "/api/diff?path=../outside-secret.txt&base=worktree",
    ):
        status_code, response_body = running_view_server.request(escape_route)
        assert status_code == 403, f"{escape_route} 未被拒绝：{status_code} {response_body}"
        response_text = json.dumps(response_body, ensure_ascii=False)
        assert "SECRET-OUTSIDE-CONTENT" not in response_text
        assert str(running_view_server.repository_root) not in response_text
        assert "/etc/hosts" not in response_text


def test_malformed_path_parameters_are_refused_not_dropped(
    running_view_server: RunningViewServer,
) -> None:
    """畸形路径参数（内嵌 NUL 字节）必须得到拒绝应答，而不是让连接被丢弃。

    路径里带 NUL 时 ``Path.resolve()`` 抛的是 ``ValueError`` 而不是 ``OSError``；只捕
    ``OSError`` 会让异常穿透到 HTTP 层，客户端拿不到任何应答（``curl`` 显示 000），
    服务端日志则留下一条 traceback——拒绝语义从「明确拒绝」退化成「无应答」。
    """
    for malformed_route in (
        "/api/file?path=module.py%00.txt",
        "/api/file?path=..%00",
        "/api/diff?path=..%00&base=worktree",
    ):
        status_code, response_body = running_view_server.request(malformed_route)
        assert status_code == 403, f"{malformed_route} 未被拒绝：{status_code} {response_body}"
        assert "越出仓库范围" in response_body["error"]


def test_non_read_methods_and_unknown_routes_are_refused(
    running_view_server: RunningViewServer,
) -> None:
    """写方法与白名单外的路由一律被拒。"""
    for write_method in ("POST", "PUT", "DELETE", "PATCH"):
        status_code, response_body = running_view_server.request(
            "/api/file?path=src/module.py", method=write_method
        )
        assert status_code == 405, f"{write_method} 未被拒绝：{status_code} {response_body}"
        assert "只读" in response_body["error"]

    unknown_route_status, unknown_route_body = running_view_server.request("/api/not-whitelisted")
    assert unknown_route_status == 404
    assert "未知路由" in unknown_route_body["error"]

    asset_escape_status, asset_escape_body = running_view_server.request("/assets/../server.py")
    assert asset_escape_status == 404, asset_escape_body


def test_server_source_has_no_write_method_handler_names() -> None:
    """服务端源码里不得出现任何写方法处理器名字。

    这条静态断言与 ``do_POST`` 式的改写互为因果：一旦有人为了「更明确地拒绝」而
    定义同名方法，只读边界的可审查性就没了。
    """
    server_source_text = _SERVER_SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden_handler_name in _FORBIDDEN_WRITE_METHOD_HANDLER_NAMES:
        assert forbidden_handler_name not in server_source_text


def test_server_binds_loopback_address_only(fixture_repository: Path) -> None:
    """服务绑定地址必须就是 ``127.0.0.1``，不是 ``0.0.0.0``。"""
    viewer_server = server.ViewerHTTPServer(
        server.ServerConfiguration(
            repository_root=fixture_repository,
            port=0,
            idle_timeout_seconds=0,
        ),
        server.ViewerRequestHandler,
    )
    try:
        assert viewer_server.server_address[0] == _LOOPBACK_HOST
    finally:
        viewer_server.server_close()


def test_source_is_served_verbatim_with_line_numbers(
    running_view_server: RunningViewServer,
) -> None:
    """文件正文必须逐行等于本地文件，且带语法高亮的行级标记。"""
    status_code, response_body = running_view_server.request("/api/file?path=src/module.py")

    assert status_code == 200
    assert response_body["kind"] == "text"
    assert response_body["highlighted"] is True
    local_source_lines = (
        (running_view_server.repository_root / "src" / "module.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert response_body["line_count"] == len(local_source_lines)
    assert len(response_body["lines"]) == len(local_source_lines)
    for line_index, local_source_line in enumerate(local_source_lines):
        rendered_line_html = response_body["lines"][line_index]
        assert _strip_html_tags(rendered_line_html) == local_source_line
    # 每行自身标签平衡：跨行 token span 必须在行边界闭合再重开，否则浏览器会把
    # 后面所有行的排版一起吃掉。
    for rendered_line_html in response_body["lines"]:
        assert rendered_line_html.count("<span") == rendered_line_html.count("</span>")


def test_tracked_files_win_over_directory_name_pruning(
    running_view_server: RunningViewServer,
) -> None:
    """受控文件即使在名为 ``build`` 的目录下也必须出现在文件树里。

    这条守的是一个真实踩过的坑：按目录名剪枝会把仓库里 ``scripts/build/`` 这类**源码**
    整棵藏掉，而文件树看上去仍然"有内容"，没人会注意到少了什么。目录名剪枝只该作用在
    未跟踪文件上；受控文件是「这不是构建产物」的权威信号。
    """
    status_code, response_body = running_view_server.request("/api/tree")
    assert status_code == 200
    tree_paths = set(response_body["paths"])

    assert "scripts/build/tool.py" in tree_paths
    assert "src/module.py" in tree_paths
    # 未跟踪且未被忽略的依赖目录仍要挡在文件树外。
    assert not any(tree_path.startswith("node_modules/") for tree_path in tree_paths)


def test_oversize_and_binary_files_are_marked_not_rendered(
    running_view_server: RunningViewServer,
) -> None:
    """超限与二进制文件返回明确标记，不返回正文也不留空白。"""
    oversize_status, oversize_body = running_view_server.request("/api/file?path=big.txt")
    assert oversize_status == 200
    assert oversize_body["kind"] == "oversize"
    assert oversize_body["limit_label"] == "256 KiB"
    assert "lines" not in oversize_body
    assert oversize_body["note"]

    binary_status, binary_body = running_view_server.request("/api/file?path=blob.bin")
    assert binary_status == 200
    assert binary_body["kind"] == "binary"
    assert "lines" not in binary_body
    assert binary_body["note"]


def test_changed_file_totals_match_terminal_git_output(
    running_view_server: RunningViewServer,
) -> None:
    """改动文件集合与增删统计必须与终端同参数 ``git diff`` 逐项一致。

    夹具里刻意同时放了重命名与二进制改动——``--numstat -z`` 对这两类用的是不同的
    token 形状，只处理其中一种会静默漏掉一半文件。
    """
    repository_root = running_view_server.repository_root
    status_code, response_body = running_view_server.request("/api/changes?base=worktree")
    assert status_code == 200

    terminal_name_only = _run_git(repository_root, "diff", "HEAD", "--name-only").stdout.split()
    assert sorted(entry["path"] for entry in response_body["files"]) == sorted(terminal_name_only)

    terminal_numstat_lines = _run_git(
        repository_root, "diff", "HEAD", "--numstat"
    ).stdout.splitlines()
    expected_counts_by_path = {}
    for numstat_line in terminal_numstat_lines:
        added_field, deleted_field, displayed_path = numstat_line.split("\t")
        # 非 -z 输出里重命名写成 "old => new"；界面与 --name-only 一样只认新路径。
        # 夹具造的是同目录整文件改名，因此必然是这种简单形式——若哪天不是，下面的
        # 文件集合断言会先炸，不会让这里静默取到错的键。
        changed_path = displayed_path.split(" => ")[-1]
        expected_counts_by_path[changed_path] = (
            None if added_field == "-" else int(added_field),
            None if deleted_field == "-" else int(deleted_field),
        )
    for changed_file_entry in response_body["files"]:
        assert (changed_file_entry["add"], changed_file_entry["del"]) == expected_counts_by_path[
            changed_file_entry["path"]
        ]

    assert response_body["totals"]["files"] == len(terminal_name_only)
    assert response_body["totals"]["add"] == sum(
        added_count or 0 for added_count, _ in expected_counts_by_path.values()
    )
    assert response_body["totals"]["del"] == sum(
        deleted_count or 0 for _, deleted_count in expected_counts_by_path.values()
    )
    # 未跟踪且未暂存的新文件不进改动列表：口径与终端 git diff HEAD 一致。
    assert "untracked.txt" not in terminal_name_only


def test_branch_baseline_matches_terminal_merge_base_diff(
    running_view_server: RunningViewServer,
) -> None:
    """分支基线走 ``<分支>...HEAD``，与终端同参数输出一致。"""
    repository_root = running_view_server.repository_root
    _run_git(repository_root, "checkout", "-q", "-b", "feature/add-answer")
    (repository_root / "notes.md").write_text("branch note\n", encoding="utf-8")
    _run_git(repository_root, "add", "notes.md")
    _run_git(repository_root, "commit", "-m", "add notes")

    status_code, response_body = running_view_server.request("/api/changes?base=main")
    assert status_code == 200
    terminal_name_only = _run_git(
        repository_root, "diff", "main...HEAD", "--name-only"
    ).stdout.split()
    assert sorted(entry["path"] for entry in response_body["files"]) == sorted(terminal_name_only)
    assert terminal_name_only, "夹具应当造出相对 main 的差异，否则这条断言没有判别力"


def test_option_like_baseline_is_refused(running_view_server: RunningViewServer) -> None:
    """以 ``-`` 开头的基线取值必须被拒，不能流进 git 的选项解析。"""
    for option_like_baseline in ("--output=/tmp/leak", "-c", "--exec=rm -rf /"):
        encoded_baseline = urllib.parse.quote(option_like_baseline, safe="")
        status_code, response_body = running_view_server.request(
            f"/api/changes?base={encoded_baseline}"
        )
        assert status_code == 400, f"{option_like_baseline} 未被拒绝：{response_body}"
        assert "不是可用的比较基线" in response_body["error"]


def test_changed_file_diff_has_line_numbers(running_view_server: RunningViewServer) -> None:
    """单文件改动要给出可着色的逐行结构与新旧行号。"""
    status_code, response_body = running_view_server.request(
        "/api/diff?path=src/module.py&base=worktree"
    )
    assert status_code == 200
    assert response_body["empty"] is False
    added_rows = [row for row in response_body["rows"] if row["kind"] == "add"]
    assert [row["text"] for row in added_rows] == ["    return 43"], response_body["rows"]
    assert all(row["new_no"] is not None for row in added_rows)
    assert any(row["kind"] == "hunk" for row in response_body["rows"])


def test_second_launch_reuses_the_resident_instance(fixture_repository: Path) -> None:
    """连续两次打开必须复用同一实例：进程号不变。"""
    try:
        first_launch_result = _run_launch(fixture_repository, "--no-open")
        assert first_launch_result.returncode == 0, first_launch_result.stderr
        first_instance = instance.read_instance_record(fixture_repository)
        assert first_instance is not None
        assert _wait_until_port_is_listening(first_instance.port)

        second_launch_result = _run_launch(fixture_repository, "--no-open")
        assert second_launch_result.returncode == 0, second_launch_result.stderr
        second_instance = instance.read_instance_record(fixture_repository)

        assert second_instance is not None
        assert second_instance.process_id == first_instance.process_id
        assert "复用既有实例" in second_launch_result.stdout
        assert "重新起服务" not in second_launch_result.stdout
    finally:
        _stop_recorded_instance(fixture_repository)


def test_stale_registry_is_taken_over_by_a_fresh_instance(fixture_repository: Path) -> None:
    """登记项指向已退出的进程时必须判为陈旧并接管，而不是打开连不通的页面。"""
    stale_process_id = _find_defunct_process_id()
    instance.write_instance_record(
        instance.ViewInstanceRecord(
            process_id=stale_process_id,
            port=_find_free_port(),
            repository_root=fixture_repository,
            started_at_iso="2026-01-01T00:00:00+0000",
        )
    )
    try:
        launch_result = _run_launch(fixture_repository, "--no-open")
        assert launch_result.returncode == 0, launch_result.stderr
        assert "重新起服务" in launch_result.stdout

        refreshed_instance = instance.read_instance_record(fixture_repository)
        assert refreshed_instance is not None
        assert refreshed_instance.process_id != stale_process_id
        assert _wait_until_port_is_listening(refreshed_instance.port)
    finally:
        _stop_recorded_instance(fixture_repository)


def test_launch_stop_recycles_the_instance(fixture_repository: Path) -> None:
    """``--stop`` 之后端口不再被监听，登记被清理。"""
    try:
        assert _run_launch(fixture_repository, "--no-open").returncode == 0
        recorded_instance = instance.read_instance_record(fixture_repository)
        assert recorded_instance is not None
        assert _wait_until_port_is_listening(recorded_instance.port)

        stop_result = _run_launch(fixture_repository, "--stop")

        assert stop_result.returncode == 0, stop_result.stderr
        assert instance.read_instance_record(fixture_repository) is None
        assert not _is_port_listening(recorded_instance.port)
    finally:
        _stop_recorded_instance(fixture_repository)


def test_idle_timeout_exits_and_clears_registry(fixture_repository: Path) -> None:
    """空闲到时限后服务自行退出并清理登记。"""
    port = _find_free_port()
    server_process = subprocess.Popen(
        [
            sys.executable,
            str(_SERVER_SCRIPT_PATH),
            "--repo-root",
            str(fixture_repository),
            "--port",
            str(port),
            "--idle-timeout",
            "1",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    instance.write_instance_record(
        instance.ViewInstanceRecord(
            process_id=server_process.pid,
            port=port,
            repository_root=fixture_repository,
            started_at_iso="2026-01-01T00:00:00+0000",
        )
    )
    try:
        assert _wait_until_port_is_listening(port)

        assert _wait_until_process_exits(server_process), "空闲时限到点后服务没有退出"
        assert instance.read_instance_record(fixture_repository) is None
        assert not _is_port_listening(port)
    finally:
        if server_process.poll() is None:
            server_process.kill()
        server_process.wait(timeout=_STOP_TIMEOUT_SECONDS)
        _stop_recorded_instance(fixture_repository)


def test_idle_timeout_zero_disables_automatic_recycling(fixture_repository: Path) -> None:
    """``--idle-timeout 0`` 关闭自动回收：手上有请求之外的等待也不会被收掉。"""
    port = _find_free_port()
    server_process = subprocess.Popen(
        [
            sys.executable,
            str(_SERVER_SCRIPT_PATH),
            "--repo-root",
            str(fixture_repository),
            "--port",
            str(port),
            "--idle-timeout",
            "0",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        assert _wait_until_port_is_listening(port)
        time.sleep(2.5)
        assert server_process.poll() is None, "关闭自动回收后服务不应自行退出"
        assert _is_port_listening(port)
    finally:
        server_process.terminate()
        server_process.wait(timeout=_STOP_TIMEOUT_SECONDS)


def test_registry_clear_never_removes_another_instances_record(fixture_repository: Path) -> None:
    """登记清理必须确认登记仍属于自己，否则会抹掉更新实例的记录。"""
    live_process_id = 4242
    instance.write_instance_record(
        instance.ViewInstanceRecord(
            process_id=live_process_id,
            port=8791,
            repository_root=fixture_repository,
            started_at_iso="2026-01-01T00:00:00+0000",
        )
    )

    assert (
        instance.clear_instance_record(fixture_repository, expected_process_id=live_process_id + 1)
        is False
    )
    assert instance.read_instance_record(fixture_repository) is not None
    assert (
        instance.clear_instance_record(fixture_repository, expected_process_id=live_process_id)
        is True
    )
    assert instance.read_instance_record(fixture_repository) is None


def test_registry_file_is_ignored_by_the_repository() -> None:
    """登记文件必须落在本仓库被 git 忽略的 ``.env*`` 规则里，不进入版本库。"""
    ignored_result = _run_git(
        _PROJECT_ROOT_PATH, "check-ignore", "--no-index", instance.REGISTRY_FILE_NAME
    )
    assert instance.REGISTRY_FILE_NAME in ignored_result.stdout


def _strip_html_tags(rendered_line_html: str) -> str:
    """剥掉行级 HTML 的标签并还原实体，用于核对渲染结果与源码逐行一致。"""
    return html.unescape(re.sub(r"<[^>]+>", "", rendered_line_html))


def _is_port_listening(port: int) -> bool:
    """判断端口当前是否可连接。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.settimeout(0.5)
        return probe_socket.connect_ex((_LOOPBACK_HOST, port)) == 0


def _wait_until_process_exits(server_process: subprocess.Popen) -> bool:
    """等待服务进程自行退出。"""
    deadline_monotonic = time.monotonic() + _STOP_TIMEOUT_SECONDS
    while time.monotonic() < deadline_monotonic:
        if server_process.poll() is not None:
            return True
        time.sleep(_SERVER_POLL_INTERVAL_SECONDS)
    return False
