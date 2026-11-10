import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl


def main():

    app = QApplication([])

    player = QWebEngineView()

    player.setWindowTitle("StudyMate | Lecture Hub")
    player.resize(1100, 750)

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.youtube.com"

    player.load(QUrl(url))

    player.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()