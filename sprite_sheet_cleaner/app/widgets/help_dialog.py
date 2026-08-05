from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from sprite_sheet_cleaner.app.services.help_catalog import HelpCatalog


class HelpDialog(QDialog):
    def __init__(self, catalog: HelpCatalog | None = None, parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog or HelpCatalog()
        self.setWindowTitle("Sprite Sheet Cleaner Help")
        self.resize(920, 620)

        self.document_list = QListWidget()
        self.document_list.setMinimumWidth(220)
        self.document_list.setToolTip("Choose a guide to read.")
        self.document_browser = QTextBrowser()
        self.document_browser.setOpenExternalLinks(False)
        self.document_browser.setReadOnly(True)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.document_list)
        splitter.addWidget(self.document_browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        close_button = QDialogButtonBox(QDialogButtonBox.Close)
        close_button.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a topic to see the full guide."))
        layout.addWidget(splitter, 1)
        layout.addWidget(close_button)

        self.document_list.currentRowChanged.connect(self._show_document)
        self._populate()

    def _populate(self) -> None:
        self.document_list.clear()
        for document in self.catalog.documents:
            item = QListWidgetItem(document.title)
            item.setData(Qt.UserRole, document.document_id)
            item.setToolTip(document.description)
            self.document_list.addItem(item)
        if self.document_list.count():
            self.document_list.setCurrentRow(0)

    def _show_document(self, row: int) -> None:
        if not 0 <= row < self.document_list.count():
            self.document_browser.clear()
            return
        document_id = self.document_list.item(row).data(Qt.UserRole)
        self.document_browser.setMarkdown(self.catalog.read(str(document_id)))
