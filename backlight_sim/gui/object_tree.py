"""Left-panel scene object tree with multi-select support."""

from __future__ import annotations

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor


# Top-level group names
GROUPS = ("Sources", "Surfaces", "Materials", "Optical Properties", "Detectors", "Sphere Detectors", "Solid Bodies")


class ObjectTree(QTreeWidget):
    """Tree widget showing all scene objects grouped by type."""

    object_selected = Signal(str, str)  # (group, object_name) — single selection
    multi_selected = Signal(str, list)  # (group, [names]) — multi-selection (same group)
    add_requested = Signal(str)  # group name
    delete_requested = Signal(str, str)  # (group, object_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Scene")
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)

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
            "Optical Properties": list(project.optical_properties.keys()),
            "Detectors": [d.name for d in project.detectors],
            "Sphere Detectors": [d.name for d in project.sphere_detectors],
        }

        for group_name, names in group_data.items():
            parent = self._group_items[group_name]
            parent.takeChildren()
            for name in names:
                child = QTreeWidgetItem(parent, [name])
                if group_name == "Sources":
                    src = next((s for s in project.sources if s.name == name), None)
                    if src and not src.enabled:
                        child.setForeground(0, QColor(150, 150, 150))
                        child.setToolTip(0, "Disabled")

        # Solid Bodies: parent/child tree (box -> faces, cylinder -> caps+side, prism -> caps+sides)
        sb_group = self._group_items["Solid Bodies"]
        sb_group.takeChildren()
        for box in getattr(project, "solid_bodies", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Box] {box.name}"])
            parent_item.setData(0, Qt.ItemDataRole.UserRole, ("box", box.name))
            parent_item.setExpanded(True)
            for face_id in ("top", "bottom", "left", "right", "front", "back"):
                face_item = QTreeWidgetItem(parent_item, [face_id])
                if face_id in box.coupling_edges:
                    face_item.setForeground(0, QColor(50, 180, 50))
                    face_item.setToolTip(0, "Coupling edge (light enters here)")
        for cyl in getattr(project, "solid_cylinders", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Cyl] {cyl.name}"])
            parent_item.setData(0, Qt.ItemDataRole.UserRole, ("cylinder", cyl.name))
            parent_item.setExpanded(True)
            for face_id in ("top_cap", "bottom_cap", "side"):
                QTreeWidgetItem(parent_item, [face_id])
        for prism in getattr(project, "solid_prisms", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Prism] {prism.name}"])
            parent_item.setData(0, Qt.ItemDataRole.UserRole, ("prism", prism.name))
            parent_item.setExpanded(True)
            QTreeWidgetItem(parent_item, ["cap_top"])
            QTreeWidgetItem(parent_item, ["cap_bottom"])
            for i in range(prism.n_sides):
                QTreeWidgetItem(parent_item, [f"side_{i}"])

    def _item_group_and_name(self, item: QTreeWidgetItem) -> tuple[str, str]:
        """Return (group, name) for an item, handling Solid Bodies' face nodes."""
        parent = item.parent()
        if parent is None:
            return "", ""
        grandparent = parent.parent()
        # Face node: parent is a solid body node, grandparent is "Solid Bodies" group header
        if grandparent is not None and grandparent.parent() is None and grandparent.text(0) == "Solid Bodies":
            # Determine actual body name from UserRole data stored on parent
            user_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if user_data:
                body_type, body_name = user_data
            else:
                # Legacy: strip prefix tag if present
                body_name = parent.text(0)
                for prefix in ("[Box] ", "[Cyl] ", "[Prism] "):
                    if body_name.startswith(prefix):
                        body_name = body_name[len(prefix):]
                        break
            face_id = item.text(0)
            return "Solid Bodies", f"{body_name}::{face_id}"
        # Solid body parent node (level directly under group header)
        if parent.parent() is None and parent.text(0) == "Solid Bodies":
            # Item is a solid body node itself
            user_data = item.data(0, Qt.ItemDataRole.UserRole)
            if user_data:
                body_type, body_name = user_data
                return f"Solid Bodies:{body_type}", body_name
            # Fallback: strip prefix
            name = item.text(0)
            for prefix in ("[Box] ", "[Cyl] ", "[Prism] "):
                if name.startswith(prefix):
                    return "Solid Bodies:box", name[len(prefix):]
            return "Solid Bodies:box", name
        # Normal item: parent is a group header (no grandparent)
        group = parent.text(0)
        name = item.text(0)
        return group, name

    def _on_selection_changed(self):
        selected = self.selectedItems()
        # Filter out group headers and SolidBox parent nodes (non-selectable conceptually)
        items = [it for it in selected if it.parent() is not None]
        if not items:
            return

        if len(items) == 1:
            group, name = self._item_group_and_name(items[0])
            if group:
                self.object_selected.emit(group, name)
            return

        # Multi-select: check if all in the same group
        groups_names = [self._item_group_and_name(it) for it in items]
        all_groups = set(gn[0] for gn in groups_names)
        if len(all_groups) == 1:
            group = all_groups.pop()
            names = [gn[1] for gn in groups_names]
            self.multi_selected.emit(group, names)
        else:
            # Mixed groups — just select the first item
            group, name = self._item_group_and_name(items[0])
            if group:
                self.object_selected.emit(group, name)

    def _context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            return

        # Clicked on a group header (top level)
        if item.parent() is None:
            group = item.text(0)
            if group == "Solid Bodies":
                a1 = menu.addAction("Add Solid Box")
                a1.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:box"))
                a2 = menu.addAction("Add Cylinder")
                a2.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:cylinder"))
                a3 = menu.addAction("Add Prism")
                a3.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:prism"))
            else:
                action = menu.addAction(f"Add {group[:-1]}")  # "Sources" -> "Add Source"
                action.triggered.connect(lambda: self.add_requested.emit(group))
        else:
            # Clicked on an object (or face node)
            group, name = self._item_group_and_name(item)
            if group.startswith("Solid Bodies") and "::" in name:
                # Face node — no delete action (faces can't be deleted individually)
                pass
            elif group:
                action = menu.addAction(f"Delete {name}")
                action.triggered.connect(lambda: self.delete_requested.emit(group, name))

        if not menu.isEmpty():
            menu.exec(self.viewport().mapToGlobal(pos))
