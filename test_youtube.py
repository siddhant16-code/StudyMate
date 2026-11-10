
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl

app = QApplication(sys.argv)

browser = QWebEngineView()
browser.resize(1100, 700)
browser.setWindowTitle("YouTube Rendering Test")

browser.load(QUrl("https://www.youtube.com/results?search_query=python"))

browser.show()

sys.exit(app.exec())
