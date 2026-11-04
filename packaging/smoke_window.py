"""Render the actual workspace in the packaged Windows WebEngine, without audio."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from doc_reader.workspace_window import WorkspaceWindow

with tempfile.TemporaryDirectory(prefix="read-docs-window-") as folder:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ | {"DOC_READER_MANAGED_ROOT": folder, "DOC_READER_ANALYSIS_ENABLED":"0",
                        "DOC_READER_TTS_UMBRA_URL":"http://127.0.0.1:1", "DOC_READER_TTS_MAC_URL":"http://127.0.0.1:1"}
    log = open(Path(folder) / "web.log", "w")
    service = subprocess.Popen([sys.executable, "-m", "doc_reader.webapp", "--port", str(port)], env=env, stdout=log, stderr=log)
    try:
        app = QApplication([])
        window = WorkspaceWindow(f"http://127.0.0.1:{port}")
        window.present()
        done = [False]
        def check(value):
            if done[0] or not value:
                return
            data = json.loads(value)
            if data.get("desktop") == "windows" and data.get("setup") and data.get("guides") == 2:
                done[0] = True
                print("PASS: packaged Qt WebEngine renders the Read Docs setup window", flush=True)
                if os.getenv("WORKSPACE_NATIVE_SCREENSHOT"):
                    window.grab().save(os.environ["WORKSPACE_NATIVE_SCREENSHOT"])
                app.exit(0)
        def poll():
            if not window.loaded:
                window.load_workspace()
            window.view.page().runJavaScript("JSON.stringify({desktop:window.readDocsDesktop,setup:document.querySelector('#setupWizard')?.open,guides:document.querySelectorAll('.shortcut-guide button').length})", check)
        timer = QTimer()
        timer.timeout.connect(poll)
        timer.start(2000)
        QTimer.singleShot(45000, lambda: app.exit(1))
        result = app.exec()
        if result:
            raise RuntimeError("The packaged native workspace did not load")
    finally:
        service.terminate()
        service.wait(timeout=10)
        log.close()
