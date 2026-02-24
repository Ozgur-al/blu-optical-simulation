"""Left-panel scene object tree."""

from __future__ import annotations

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PySide6.QtCore import Signal, Qt


# Top-level group names
GROUPS = ("Sources", "Surfaces", "Materials", "Detectors")


class ObjectTree(QTreeWidget):
    """Tree widget showing all scene objects grouped by type."""

    object_selected = Signal(str, str)  # (group, object_name)
    add_requested = Signal(str)  # group name
    delete_requested = Signal(str, str)  # (group, object_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Scene")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.currentItemChanged.connect(self._on_selection_changed)

        self._group_items: dict[str, QTreeWidgetItem] = {}
        for group in GROUPS:
            item = QTreeWidgetItem(self, [group])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setExpanded(True)
            self._group_items[group] = item

    def refresh(self, project):
        """Rebuild the tree from the project model."""
        group_data = {
            "Sources": [s.name for s in project.sources],
            "Surfaces": [s.name for s in project.surfaces],
            "Materials": list(project.materials.keys()),
            "Detectors": [d.name for d in project.detectors],
        }

        for group_name, names in group_data.items():
            parent = self._group_items[group_name]
            parent.takeChildren()
            for name in names:
                QTreeWidgetItem(parent, [name])

    def _on_selection_changed(self, current, _previous):
        if current is None or current.parent() is None:
            return
        group = current.parent().text(0)
        name = current.text(0)
        self.object_selected.emit(group, name)

    def _context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            return

        # Clicked on a group header
        if item.parent() is None:
            group = item.text(0)
            action = menu.addAction(f"Add {group[:-1]}")  # "Sources" -> "Add Source"
            action.triggered.connect(lambda: self.add_requested.emit(group))
        else:
            # Clicked on an object
            group = item.parent().text(0)
            name = item.text(0)
            action = menu.addAction(f"Delete {name}")
            action.triggered.connect(lambda: self.delete_requested.emit(group, name))

        menu.exec(self.viewport().mapToGlobal(pos))
