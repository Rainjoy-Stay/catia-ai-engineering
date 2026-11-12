"""Recoverable CATIA session transaction for inspection workflows."""
from __future__ import annotations

import os
from typing import Any

import win32api
import win32con
import win32gui
import win32process


def find_visible_catia_window() -> int:
    """Resolve one unowned top-level CNEXT window; never match by title alone."""
    candidates: list[int] = []
    def collect(hwnd: int, _: object) -> None:
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetWindow(hwnd, win32con.GW_OWNER):
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            try:
                executable = os.path.basename(win32process.GetModuleFileNameEx(process, 0))
            finally:
                process.Close()
        except Exception:
            return
        if executable.casefold() == "cnext.exe" and win32gui.GetWindowText(hwnd).startswith("CATIA V5"):
            candidates.append(hwnd)
    win32gui.EnumWindows(collect, None)
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one visible CATIA CNEXT window, found {len(candidates)}")
    return candidates[0]


class CATIASessionManager:
    """Snapshot and restore only state owned by the current inspection run."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.original_document = app.ActiveDocument
        self.original_document_name = str(self.original_document.Name)
        self.window_handle = find_visible_catia_window()
        self.original_window_placement = win32gui.GetWindowPlacement(self.window_handle)
        self.temporary_documents: list[Any] = []
        self._restored = False
        self.events: list[dict[str, Any]] = []

    def register_temporary_document(self, document: Any) -> None:
        self.temporary_documents.append(document)
        self.events.append({"event": "REGISTER_TEMPORARY_DOCUMENT", "name": str(document.Name)})

    def maximize(self) -> int:
        win32gui.ShowWindow(self.window_handle, win32con.SW_MAXIMIZE)
        self.events.append({"event": "MAXIMIZE_WINDOW"})
        return self.window_handle

    def restore(self) -> None:
        if self._restored:
            return
        self._restored = True
        closed = []
        for document in reversed(self.temporary_documents):
            try:
                name = str(document.Name)
                document.Close()
                closed.append(name)
            except Exception:
                pass
        try:
            self.original_document.Activate()
        except Exception:
            pass
        try:
            win32gui.SetWindowPlacement(self.window_handle, self.original_window_placement)
        except Exception:
            pass
        self.events.append({"event": "RESTORE", "closed_temporary_documents": closed,
                            "restored_document": self.original_document_name})

    def audit(self) -> dict[str, Any]:
        return {"original_document": self.original_document_name,
                "temporary_document_count": len(self.temporary_documents),
                "restored": self._restored, "events": list(self.events)}

    def __enter__(self) -> "CATIASessionManager":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.restore()
        return False
