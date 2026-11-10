import ctypes
import os

# A black/blank embedded browser is usually a GPU-rendering problem when Qt
# WebEngine is reparented into another window. These flags force safe software
# rendering. They MUST be set before any Qt WebEngine import.
_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")

for _flag in ("--disable-gpu", "--disable-gpu-compositing"):
    if _flag not in _flags:
        _flags = (_flags + " " + _flag).strip()

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags

from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QCoreApplication, Qt


class EmbeddedYouTube:

    def __init__(self, root, host_frame):

        self.root = root
        self.host = host_frame
        self.hwnd = None
        self.closed = False
        self.after_id = None

        QCoreApplication.setAttribute(
            Qt.ApplicationAttribute.AA_ShareOpenGLContexts
        )

        self.qt_app = QApplication.instance()

        if self.qt_app is None:
            self.qt_app = QApplication([])

        self.qt_app.setQuitOnLastWindowClosed(False)

        # Create browser as a child-style widget
        self.view = QWebEngineView()

        self.view.setWindowFlags(
            Qt.WindowType.Widget
        )

        self.view.setAttribute(
            Qt.WidgetAttribute.WA_NativeWindow,
            True
        )

        self.view.loadFinished.connect(
            self.check_loading
        )

        # Obtain native handles
        self.hwnd = int(self.view.winId())
        parent_hwnd = self.host.winfo_id()

        user32 = ctypes.windll.user32

        # Attach browser to Tkinter frame
        user32.SetParent(
            self.hwnd,
            parent_hwnd
        )

        # Preserve and update existing window styles
        GWL_STYLE = -16

        WS_CHILD = 0x40000000
        WS_VISIBLE = 0x10000000
        WS_CLIPSIBLINGS = 0x04000000
        WS_CLIPCHILDREN = 0x02000000

        style = user32.GetWindowLongPtrW(
            self.hwnd,
            GWL_STYLE
        )

        style = (
            style
            | WS_CHILD
            | WS_VISIBLE
            | WS_CLIPSIBLINGS
            | WS_CLIPCHILDREN
        )

        user32.SetWindowLongPtrW(
            self.hwnd,
            GWL_STYLE,
            style
        )

        # Bind resizing
        self.host.bind(
            "<Configure>",
            self.resize_player
        )

        self.host.bind(
            "<Destroy>",
            self.on_destroy
        )

        # Display after embedding
        self.view.show()

        self.resize_player()

        self.load(
            "https://www.youtube.com/results?search_query=python"
        )

        self.process_qt_events()

    def load(self, url):

        if self.closed:
            return

        print("Loading URL:", url)

        self.view.setUrl(QUrl(url))

    def check_loading(self, success):

        if self.closed:
            return

        print("Page loaded:", success)
        print("Page title:", self.view.title())
        print("Current URL:", self.view.url().toString())

    def resize_player(self, event=None):

        if self.closed or not self.hwnd:
            return

        width = self.host.winfo_width()
        height = self.host.winfo_height()

        if width > 1 and height > 1:

            ctypes.windll.user32.SetWindowPos(
                self.hwnd,
                0,
                0,
                0,
                width,
                height,
                0x0004 | 0x0010 | 0x0040
            )

    def process_qt_events(self):
        """Pump Qt events from the Tk loop. Stops as soon as the player closes."""

        if self.closed:
            return

        try:

            if self.root.winfo_exists() and self.host.winfo_exists():

                self.qt_app.processEvents()

                self.after_id = self.root.after(
                    15,
                    self.process_qt_events
                )

        except Exception as e:

            print("Qt event error:", e)

    def on_destroy(self, event):

        if event.widget == self.host:
            self.close()

    def close(self):

        if self.closed:
            return

        self.closed = True

        # Stop the timer loop so it does not pile up on every page visit
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass

            self.after_id = None

        if hasattr(self, "view"):

            try:
                self.view.stop()
                self.view.close()
                self.view.deleteLater()
            except Exception as e:
                print("Player close error:", e)

        self.hwnd = None