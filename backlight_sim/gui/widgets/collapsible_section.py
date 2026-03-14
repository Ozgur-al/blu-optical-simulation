"""Collapsible section widget — a toggleable header + content area.

Used to group related properties in the PropertiesPanel so users can
collapse sections they don't need, reducing scroll distance.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QWidget):
    """A header button that shows/hides a content area when clicked.

    Usage::

        section = CollapsibleSection("Position")
        form = QFormLayout()
        form.addRow("X:", spin_x)
        form.addRow("Y:", spin_y)
        section.addLayout(form)

    The section starts expanded by default. Pass ``collapsed=True`` to
    start collapsed.
    """

    def __init__(self, title: str, parent: QWidget | None = None, collapsed: bool = False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toggle button acts as the section header
        self._toggle = QToolButton()
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if not collapsed else Qt.ArrowType.RightArrow
        )
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle.setStyleSheet("font-weight: bold; text-align: left; padding: 4px 8px;")
        self._toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self._toggle)

        # Content frame (indented slightly so it reads as "inside" the section)
        self._content = QFrame()
        self._content.setVisible(not collapsed)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 4, 4)
        self._content_layout.setSpacing(2)
        layout.addWidget(self._content)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_toggle(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def addWidget(self, widget: QWidget) -> None:
        """Add a widget to the collapsible content area."""
        self._content_layout.addWidget(widget)

    def addLayout(self, layout) -> None:
        """Add a layout to the collapsible content area."""
        self._content_layout.addLayout(layout)

    def contentLayout(self) -> QVBoxLayout:
        """Return the inner QVBoxLayout for advanced manipulation."""
        return self._content_layout

    def setCollapsed(self, collapsed: bool) -> None:
        """Programmatically collapse or expand the section."""
        self._toggle.setChecked(not collapsed)

    def isCollapsed(self) -> bool:
        """Return True if the section is currently collapsed."""
        return not self._toggle.isChecked()
