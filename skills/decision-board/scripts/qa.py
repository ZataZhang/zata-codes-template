#!/usr/bin/env python3
"""对话侧读写问答流：列出待答问题、把回答追加进 answers.jsonl。

用法：
``python3 qa.py --dir <产物目录> list``　　列出问题与是否已答
``printf '%s' "回答" | python3 qa.py --dir <产物目录> answer q3``　　追加一条回答

回答只追加、绝不重写文件：``tail -F`` 在文件被 rename/truncate 后会从头重读，
导致同一个问题被重复通知、重复回答。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


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


def main() -> int:
    """按子命令列出问答状态或追加一条回答。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir", type=Path, default=Path("."), help="产物目录（含 questions.jsonl）"
    )
    parser.add_argument("command", choices=["list", "answer"])
    parser.add_argument("question_id", nargs="?", default="")
    args = parser.parse_args()

    questions_path = args.dir / "questions.jsonl"
    replies_path = args.dir / "answers.jsonl"
    question_records = read_jsonl(questions_path)
    if not question_records:
        print("（还没有提问）")
        return 0

    if args.command == "list":
        answered_ids = {str(rec.get("id")) for rec in read_jsonl(replies_path)}
        for question_rec in question_records:
            question_id_text = str(question_rec.get("id", ""))
            mark = "答" if question_id_text in answered_ids else "待"
            about_text = str(question_rec.get("about", "")).strip()
            prefix = f"{about_text} · " if about_text else ""
            question_text = str(question_rec.get("question", ""))[:160]
            print(f"[{mark}] {question_id_text} · {prefix}{question_text}")
        return 0

    if not args.question_id:
        print("❌ answer 需要问题 id", file=sys.stderr)
        return 2
    if str(args.question_id) not in {str(rec.get("id")) for rec in question_records}:
        print(f"⚠ {args.question_id} 不在现有问题里（仍已写入）", file=sys.stderr)
    reply_text = sys.stdin.read().strip()
    if not reply_text:
        print("❌ 回答正文走 stdin，且不能为空", file=sys.stderr)
        return 2
    with replies_path.open("a", encoding="utf-8") as replies_file:
        replies_file.write(
            json.dumps(
                {
                    "id": args.question_id,
                    "reply": reply_text,
                    "ts": datetime.now().astimezone().isoformat(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(f"answered {args.question_id}（{len(reply_text)} 字）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
