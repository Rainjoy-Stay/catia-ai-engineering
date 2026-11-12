"""Conservative CATIA dialog watcher with an exact-text safety allowlist."""
from __future__ import annotations

import argparse
import ctypes
import json
import time
from datetime import datetime
from pathlib import Path

import win32con
import win32gui


def classify_dialog(title: str, text: str, allow_save_as_references: bool = False) -> dict:
    lowered = text.lower()
    if title.lower().endswith((".stp", ".step", ".igs", ".iges")):
        return {"action": "CLICK", "buttons": {"确定", "OK", "&OK"},
                "rule": "NEUTRAL_TRANSLATOR_NOTICE"}
    if ("完成转换" in text and "CATReport" in text) or (
            "conversion completed" in lowered and "catreport" in lowered):
        return {"action": "CLICK", "buttons": {"确定", "OK", "&OK"},
                "rule": "NEUTRAL_TRANSLATION_COMPLETED"}
    if title in {"打开", "Open"} and (("相同标识" in text and "无法加载" in text) or
                                        ("same identifier" in lowered and "cannot" in lowered)):
        return {"action": "CLICK", "buttons": {"确定", "OK", "&OK"},
                "rule": "DUPLICATE_DOCUMENT_IDENTIFIER"}
    if title in {"另存为", "Save As"} and (("激活其他文档保存操作" in text and "想要继续吗" in text) or
                                             ("activate other documents" in lowered and "continue" in lowered)):
        if allow_save_as_references:
            return {"action": "CLICK", "buttons": {"是(Y)", "是(&Y)", "是", "Yes", "&Yes"},
                    "rule": "SAVE_AS_REFERENCED_DOCUMENTS_EXPLICIT"}
        return {"action": "BLOCK", "rule": "SAVE_AS_REQUIRES_EXPLICIT_SCOPE"}
    destructive = ("保存" in text or "save" in lowered or "覆盖" in text or "overwrite" in lowered or
                   "删除" in text or "delete" in lowered or "update diagnosis" in lowered or "更新诊断" in text)
    return {"action": "BLOCK", "rule": "UNRECOGNIZED_DESTRUCTIVE" if destructive else "UNRECOGNIZED"}


def _children(hwnd: int) -> list[tuple[int, str, str]]:
    values = []
    win32gui.EnumChildWindows(
        hwnd, lambda child, _: values.append(
            (child, win32gui.GetClassName(child), win32gui.GetWindowText(child))), None)
    return values


def _parent_alive(pid: int) -> bool:
    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return False
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x00000102
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--allow-save-as-references", action="store_true")
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    while _parent_alive(args.parent_pid):
        windows = []
        def collect(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                children = _children(hwnd)
                text = "\n".join(value for _, _, value in children if value)
                translation_notice = title.lower().endswith((".stp", ".step", ".igs", ".iges")) or ("CATReport" in text and (
                    "完成转换" in text or "conversion completed" in text.lower())
                )
                if title in {"打开", "Open", "另存为", "Save As", "CATIA", "警告", "Warning"} or translation_notice:
                    windows.append(hwnd)
        win32gui.EnumWindows(collect, None)
        for hwnd in windows:
            children = _children(hwnd)
            title = win32gui.GetWindowText(hwnd)
            text = "\n".join(value for _, _, value in children if value)
            signature = (title, text)
            decision = classify_dialog(title, text, args.allow_save_as_references)
            clicked = False
            if decision["action"] == "CLICK":
                all_buttons = [(child, value) for child, cls, value in children if cls == "Button"]
                if decision["rule"].startswith("NEUTRAL_TRANSLAT") and len(all_buttons) == 1:
                    buttons = all_buttons
                else:
                    buttons = [(child, value) for child, value in all_buttons
                               if value in decision["buttons"]]
                if len(buttons) == 1:
                    win32gui.SendMessage(buttons[0][0], win32con.BM_CLICK, 0, 0)
                    clicked = True
                else:
                    decision = {"action": "BLOCK", "rule": "AMBIGUOUS_BUTTON_MATCH"}
            if signature not in seen or clicked:
                seen.add(signature)
                with args.log.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"),
                                             "title": title, "text": text, "decision": decision,
                                             "clicked": clicked}, ensure_ascii=False) + "\n")
        time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
