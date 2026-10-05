#!/usr/bin/env python3
"""决策收集页的本地服务：读取 board.json，渲染页面并接收选择与提问。

用法：``python3 serve_board.py --board <board.json> [--port 8765] [--open]``
``--open`` 会额外用系统默认浏览器打开页面；默认不开，避免自检时弹窗。

只监听 127.0.0.1。产出三个文件，落在 board.json 同目录（或 --workdir）：
``answers.json`` 是九项选择结果（每次提交覆盖），``questions.jsonl`` 是页面提问
（只追加，供对话侧 tail 唤醒），``answers.jsonl`` 是对话侧回答（只追加，由 qa.py 写）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "board.html"
QUESTION_MAX_CHARS = 4000


def validate_board(board: dict) -> tuple[list[str], dict]:
    """校验 board 结构，返回 ``(错误列表, 归一化后的 board)``。

    Args:
        board (dict): 读入的 board.json 对象。

    Returns:
        tuple[list[str], dict]: 错误为空时第二个元素可直接渲染。
    """
    errors_list: list[str] = []
    questions_list = board.get("questions")
    if not isinstance(questions_list, list) or not questions_list:
        return ["questions 必须是非空数组"], board
    seen_ids = set()
    for index, question in enumerate(questions_list):
        where = f"questions[{index}]"
        if not isinstance(question, dict):
            errors_list.append(f"{where} 必须是对象")
            continue
        question_id_text = str(question.get("id", "")).strip()
        if not question_id_text:
            errors_list.append(f"{where}.id 不能为空")
            continue
        if question_id_text in seen_ids:
            errors_list.append(f"{where}.id 重复：{question_id_text}")
        seen_ids.add(question_id_text)
        where = f"{where}({question_id_text})"
        if not str(question.get("t", "")).strip():
            errors_list.append(f"{where}.t（题干）不能为空")
        options_list = question.get("opts")
        if not isinstance(options_list, list) or len(options_list) < 2:
            errors_list.append(f"{where}.opts 至少两项 [key, label]")
            continue
        keys = {str(opt[0]) for opt in options_list if isinstance(opt, list) and opt}
        if len(keys) != len(options_list):
            errors_list.append(f"{where}.opts 的选项 key 必须唯一且非空")
        recommend_text = str(question.get("rec", ""))
        if recommend_text not in keys:
            errors_list.append(f"{where}.rec 必须是 opts 之一，当前 {recommend_text or '空'}")
        for field_text in ("why", "cost"):
            if not str(question.get(field_text, "")).strip():
                errors_list.append(f"{where}.{field_text} 必填（你的看法与代价）")
    return errors_list, board


def render_page(board: dict) -> bytes:
    """把 board 数据注入页面模板。"""
    html_text = TEMPLATE.read_text(encoding="utf-8")
    payload_text = json.dumps(board, ensure_ascii=False).replace("</", "<\\/")
    for placeholder_text, value_text in (
        ("__DATA__", payload_text),
        ("__TITLE__", str(board.get("title", "待决项"))),
        ("__SOURCE__", str(board.get("source", ""))),
        ("__INTRO__", str(board.get("intro", ""))),
    ):
        html_text = html_text.replace(placeholder_text, value_text)
    return html_text.encode("utf-8")


def read_jsonl(jsonl_path: Path) -> list[dict]:
    """按行读取 JSONL，忽略空行与损坏行。"""
    if not jsonl_path.is_file():
        return []
    records_list = []
    for raw_line_text in jsonl_path.read_text(encoding="utf-8").splitlines():
        if raw_line_text.strip():
            try:
                records_list.append(json.loads(raw_line_text))
            except json.JSONDecodeError:
                continue
    return records_list


def append_jsonl(jsonl_path: Path, record: dict) -> None:
    """只追加写一条记录，保证 tail -F 不会重发历史行。"""
    with jsonl_path.open("a", encoding="utf-8") as jsonl_file:
        jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def archive_qa_files(questions_path: Path, replies_path: Path) -> list[str]:
    """把问答流移入 ``_cleared/`` 归档，返回被移动的文件名。

    清空**不能**用 truncate：``tail -F`` 在监听的文件被截断或替换后会重新打开，
    服务侧再往同名文件追加时事件流会与旧内容混在一起。归档则两个文件都消失、
    由服务在下次追加时新建，监听端看到的是干净的新文件。归档而非删除，是为了
    让页面的「清空」可回溯。

    Args:
        questions_path (Path): 页面提问（questions.jsonl）。
        replies_path (Path): 对话侧回答（answers.jsonl）。

    Returns:
        list[str]: 被移动的归档文件名。
    """
    cleared_dir = questions_path.parent / "_cleared"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    moved: list[str] = []
    for source_path in (questions_path, replies_path):
        if not source_path.is_file():
            continue
        cleared_dir.mkdir(parents=True, exist_ok=True)
        destination = cleared_dir / f"{stamp}-{source_path.name}"
        source_path.replace(destination)
        moved.append(destination.name)
    return moved


def open_in_browser(page_url: str) -> None:
    """用系统默认浏览器打开页面，失败只告警、不影响服务。

    按平台选择系统自带的 opener：macOS ``open``、Linux ``xdg-open``、
    Windows ``cmd /c start``。以 ``Popen`` 分离启动，不等待也不占用服务进程。

    Args:
        page_url (str): 要打开的页面地址，如 ``http://127.0.0.1:8765/``。
    """
    if sys.platform == "darwin":
        open_command = ["open", page_url]
    elif sys.platform.startswith("win"):
        open_command = ["cmd", "/c", "start", "", page_url]
    else:
        open_command = ["xdg-open", page_url]
    try:
        subprocess.Popen(
            open_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"⚠ 无法自动打开浏览器（{exc}）：请手动访问 {page_url}", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    """提供渲染后的页面，并接收选择提交与提问。"""

    paths: argparse.Namespace  # 由 main() 注入

    def _write(self, status_code: int, body: bytes, content_type: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self) -> dict | None:
        """读取并解析请求体，失败时返回 None。"""
        raw_body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write(400, b"bad json", "text/plain; charset=utf-8")
            return None
        if not isinstance(payload, dict):
            self._write(400, b"json body must be an object", "text/plain; charset=utf-8")
            return None
        return payload

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        """返回看板页面、已选结果或问答线程的只读视图。"""
        if self.path in ("/", "/index.html"):
            self._write(200, render_page(self.paths.board), "text/html; charset=utf-8")
        elif self.path == "/answers":
            body = (
                self.paths.answers.read_bytes()
                if self.paths.answers.is_file()
                else b'{"pending": true}'
            )
            self._write(200, body, "application/json; charset=utf-8")
        elif self.path.startswith("/qa"):
            replies_by_id = {
                str(rec.get("id")): rec for rec in read_jsonl(self.paths.replies) if rec.get("id")
            }
            threads = []
            for question_rec in read_jsonl(self.paths.questions):
                question_id_text = str(question_rec.get("id", ""))
                reply_rec = replies_by_id.get(question_id_text)
                threads.append({**question_rec, "reply": (reply_rec or {}).get("reply")})
            self._write(
                200,
                json.dumps(threads, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
            )
        else:
            self._write(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        """接收选择提交（/answers）、提问（/ask）与清空（/qa/clear），落盘。"""
        if self.path == "/qa/clear":
            moved_files = archive_qa_files(self.paths.questions, self.paths.replies)
            self._write(
                200,
                json.dumps({"ok": True, "archived": moved_files}, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
            )
            return
        if self.path == "/answers":
            payload = self._json_body()
            if payload is None:
                return
            record = {
                "received_at": datetime.now().astimezone().isoformat(),
                "board": self.paths.board.get("title", ""),
                "selection": payload,
            }
            self.paths.answers.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            self._write(200, b'{"ok": true}', "application/json; charset=utf-8")
            return
        if self.path == "/ask":
            payload = self._json_body()
            if payload is None:
                return
            question_text = str(payload.get("question", "")).strip()
            if not question_text:
                self._write(400, b"empty question", "text/plain; charset=utf-8")
                return
            question_id_text = f"q{len(read_jsonl(self.paths.questions)) + 1}"
            append_jsonl(
                self.paths.questions,
                {
                    "id": question_id_text,
                    "ts": datetime.now().astimezone().isoformat(),
                    "about": str(payload.get("about", ""))[:40],
                    "question": question_text[:QUESTION_MAX_CHARS],
                },
            )
            self._write(
                200,
                json.dumps({"ok": True, "id": question_id_text}).encode(),
                "application/json; charset=utf-8",
            )
            return
        self._write(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """静默 BaseHTTPRequestHandler 的默认访问日志，避免污染问答输出。"""


def main() -> int:
    """解析参数、校验 board 并启动服务。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", required=True, type=Path, help="board.json 路径")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="仅建议 127.0.0.1")
    parser.add_argument("--workdir", type=Path, default=None, help="产物目录，默认 board 同目录")
    parser.add_argument("--open", action="store_true", help="启动后用系统默认浏览器打开页面")
    args = parser.parse_args()

    if not TEMPLATE.is_file():
        print(f"❌ 页面模板缺失：{TEMPLATE}", file=sys.stderr)
        return 1
    if not args.board.is_file():
        print(f"❌ board 不存在：{args.board}", file=sys.stderr)
        return 1
    try:
        board = json.loads(args.board.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ board 不是合法 JSON：{exc}", file=sys.stderr)
        return 1
    if not isinstance(board, dict):
        print("❌ board 顶层必须是对象", file=sys.stderr)
        return 1
    errors_list, board = validate_board(board)
    if errors_list:
        print(f"❌ board 校验未通过（{len(errors_list)} 条）：", file=sys.stderr)
        for error_text in errors_list[:20]:
            print(f"   - {error_text}", file=sys.stderr)
        return 1

    workdir = args.workdir or args.board.resolve().parent
    workdir.mkdir(parents=True, exist_ok=True)
    args.answers = workdir / "answers.json"
    args.questions = workdir / "questions.jsonl"
    args.replies = workdir / "answers.jsonl"
    args.board = board
    Handler.paths = args

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            f"⚠ 正在监听 {args.host}：页面内容会离开本机回环，确认这是你想要的。",
            file=sys.stderr,
        )
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"❌ 端口 {args.port} 起不来：{exc}", file=sys.stderr)
        return 1

    board_url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(f"board: {len(board['questions'])} 项待决 · {board_url}")
    print(f"提问 → {args.questions}    回答 → {args.replies}    选择 → {args.answers}")
    if args.open:
        open_in_browser(board_url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
