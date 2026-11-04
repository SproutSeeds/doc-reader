"""Windows desktop workspace. Qt's browser engine is bundled with the app."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow


class WorkspacePage(QWebEnginePage):
    def __init__(self, origin: str, parent=None):
        super().__init__(parent)
        self.origin = QUrl(origin)
        script = QWebEngineScript()
        script.setSourceCode("window.readDocsDesktop = 'windows';")
        script.setInjectionPoint(QWebEngineScript.DocumentCreation)
        script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(False)
        self.scripts().insert(script)
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, False)
        self.settings().setAttribute(QWebEngineSettings.NavigateOnDropEnabled, False)

    def same_origin(self, url: QUrl) -> bool:
        return (url.scheme(), url.host(), url.port()) == (
            self.origin.scheme(), self.origin.host(), self.origin.port())

    def acceptNavigationRequest(self, url, kind, main_frame):  # noqa: N802
        if self.same_origin(url) or url.toString() == "about:blank":
            return True
        if main_frame and self.same_origin(self.url()):
            if url.toString() == "read-docs://permission/microphone":
                QDesktopServices.openUrl(QUrl("ms-settings:privacy-microphone"))
            elif kind == QWebEnginePage.NavigationTypeLinkClicked and url.scheme() in ("http", "https"):
                QDesktopServices.openUrl(url)
        return False


class WorkspaceWindow(QMainWindow):
    def __init__(self, url: str):
        super().__init__()
        self.workspace_url = QUrl(url)
        self.loaded = False
        self.setWindowTitle("Read Docs")
        self.resize(1000, 780)
        self.setMinimumSize(520, 520)
        self.view = QWebEngineView(self)
        self.view.setPage(WorkspacePage(url, self.view))
        self.setCentralWidget(self.view)
        self.view.loadFinished.connect(self._finished)
        self.view.setHtml("<html><style>body{font:17px system-ui;display:grid;place-content:center;height:90vh;text-align:center;background:#f3f4ef;color:#20332c}h1{font:52px Georgia}</style><h1>Read Docs</h1><p>Opening your workspace…</p></html>")

    def present(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def load_workspace(self):
        if not self.loaded:
            self.view.load(self.workspace_url)

    def _finished(self, ok: bool):
        if self.view.url().host() != self.workspace_url.host():
            return
        self.loaded = ok
        if not ok:
            self.view.setHtml(f"<html><style>body{{font:20px system-ui;padding:15vh;text-align:center}}a{{color:inherit;padding:16px}}</style><h1>Let’s try again.</h1><a href='{self.workspace_url.toString()}'>Retry</a></html>")
