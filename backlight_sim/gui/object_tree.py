"""Left-panel scene object tree with multi-select support."""

from __future__ import annotations

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


# Top-level group names
GROUPS = ("Sources", "Surfaces", "Materials", "Optical Properties", "Detectors", "Sphere Detectors", "Solid Bodies")

# Icon colors per group type (engineering convention)
_GROUP_ICON_COLOR: dict[str, str] = {
    "Sources": "#ffc107",           # yellow — light emitters
    "Surfaces": "#42a5f5",          # blue — reflective/structural
    "Materials": "#9e9e9e",         # gray — material definitions
    "Optical Properties": "#ab47bc", # purple — optical property sets
    "Detectors": "#66bb6a",         # green — measurement surfaces
    "Sphere Detectors": "#26c6da",  # teal — 3D measurement
    "Solid Bodies": "#ff7043",      # orange — solid geometry
}


def _make_icon(color_hex: str, size: int = 12) -> QIcon:
    """Create a small filled-circle icon from a hex color string.

    Uses QPainter on QPixmap — no external image files required.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(color_hex)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    margin = 1
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pixmap)


class ObjectTree(QTreeWidget):
    """Tree widget showing all scene objects grouped by type."""

    object_selected = Signal(str, str)   # (group, object_name) — single selection
    multi_selected = Signal(str, list)   # (group, [names]) — multi-selection (same group)
    add_requested = Signal(str)          # group name
    delete_requested = Signal(str, str)  # (group, object_name)
    duplicate_requested = Signal(str, str)  # (group, object_name)
    # NOTE: duplicate_requested must be connected in MainWindow._connect_signals()
    # e.g.: self._tree.duplicate_requested.connect(self._duplicate_object)

    # Class-level icon cache — created once, shared across all instances
    _ICONS: dict[str, QIcon] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Scene")
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemExpanded.connect(self._update_arrow)
        self.itemCollapsed.connect(self._update_arrow)
        self.setRootIsDecorated(False)
        self.setIndentation(16)

        # Pre-build icon cache for all group types
        self._ensure_icons()

        self._group_items: dict[str, QTreeWidgetItem] = {}
        for group in GROUPS:
            item = QTreeWidgetItem(self, [f"\u25BC {group}"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, group)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setExpanded(True)
            self._group_items[group] = item

    @classmethod
    def _ensure_icons(cls) -> None:
        """Build the icon cache if it hasn't been done yet."""
        if cls._ICONS:
            return
        for group, color in _GROUP_ICON_COLOR.items():
            cls._ICONS[group] = _make_icon(color, size=12)

    def _get_icon(self, group: str) -> QIcon:
        """Return the icon for the given group, or an empty QIcon if unknown."""
        return self._ICONS.get(group, QIcon())

    def _update_arrow(self, item: QTreeWidgetItem):
        """Update the arrow prefix on group/parent items when expanded/collapsed."""
        stored = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if stored is not None:
            arrow = "\u25BC" if item.isExpanded() else "\u25B6"
            item.setText(0, f"{arrow} {stored}")

    def _get_group_name(self, item: QTreeWidgetItem) -> str:
        """Get the real group name from a top-level item (strips arrow prefix)."""
        stored = item.data(0, Qt.ItemDataRole.UserRole + 1)
        return stored if stored else item.text(0)

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

        # Pre-build disabled-source lookup to avoid O(n²) scan
        disabled_sources = {s.name for s in project.sources if not s.enabled}

        for group_name, names in group_data.items():
            parent = self._group_items[group_name]
            parent.takeChildren()
            icon = self._get_icon(group_name)
            for name in names:
                child = QTreeWidgetItem(parent, [name])
                child.setIcon(0, icon)
                if group_name == "Sources" and name in disabled_sources:
                    child.setForeground(0, QColor(150, 150, 150))
                    child.setToolTip(0, "Disabled")

        # Solid Bodies: parent/child tree (box -> faces, cylinder -> caps+side, prism -> caps+sides)
        sb_group = self._group_items["Solid Bodies"]
        sb_group.takeChildren()
        sb_icon = self._get_icon("Solid Bodies")
        for box in getattr(project, "solid_bodies", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Box] {box.name}"])
            parent_item.setIcon(0, sb_icon)
            parent_item.setData(0, Qt.ItemDataRole.UserRole, ("box", box.name))
            parent_item.setExpanded(True)
            for face_id in ("top", "bottom", "left", "right", "front", "back"):
                face_item = QTreeWidgetItem(parent_item, [face_id])
                if face_id in box.coupling_edges:
                    face_item.setForeground(0, QColor(50, 180, 50))
                    face_item.setToolTip(0, "Coupling edge (light enters here)")
        for cyl in getattr(project, "solid_cylinders", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Cyl] {cyl.name}"])
            parent_item.setIcon(0, sb_icon)
            parent_item.setData(0, Qt.ItemDataRole.UserRole, ("cylinder", cyl.name))
            parent_item.setExpanded(True)
            for face_id in ("top_cap", "bottom_cap", "side"):
                QTreeWidgetItem(parent_item, [face_id])
        for prism in getattr(project, "solid_prisms", []):
            parent_item = QTreeWidgetItem(sb_group, [f"[Prism] {prism.name}"])
            parent_item.setIcon(0, sb_icon)
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
        if grandparent is not None and grandparent.parent() is None and self._get_group_name(grandparent) == "Solid Bodies":
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
        if parent.parent() is None and self._get_group_name(parent) == "Solid Bodies":
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
        group = self._get_group_name(parent)
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

    # ------------------------------------------------------------------
    # Context menu labels (more descriptive than the old "Add {group[:-1]}")
    # ------------------------------------------------------------------

    _ADD_LABEL: dict[str, str] = {
        "Sources": "Add Point Source",
        "Surfaces": "Add Surface",
        "Materials": "Add Material",
        "Optical Properties": "Add Optical Properties",
        "Detectors": "Add Detector Surface",
        "Sphere Detectors": "Add Sphere Detector",
    }

    def _context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            return

        # Clicked on a group header (top level)
        if item.parent() is None:
            group = self._get_group_name(item)
            if group == "Solid Bodies":
                a1 = menu.addAction("Add Solid Box")
                a1.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:box"))
                a2 = menu.addAction("Add Cylinder")
                a2.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:cylinder"))
                a3 = menu.addAction("Add Prism")
                a3.triggered.connect(lambda: self.add_requested.emit("Solid Bodies:prism"))
            else:
                label = self._ADD_LABEL.get(group, f"Add {group[:-1]}")
                action = menu.addAction(label)
                action.triggered.connect(lambda: self.add_requested.emit(group))
        else:
            # Clicked on an object (or face node)
            group, name = self._item_group_and_name(item)
            if group.startswith("Solid Bodies") and "::" in name:
                # Face node — no context menu actions (faces can't be individually duplicated/deleted)
                pass
            elif group:
                dup_action = menu.addAction(f"Duplicate {name}")
                dup_action.triggered.connect(
                    lambda checked=False, g=group, n=name: self.duplicate_requested.emit(g, n)
                )
                menu.addSeparator()
                del_action = menu.addAction(f"Delete {name}")
                del_action.triggered.connect(
                    lambda checked=False, g=group, n=name: self.delete_requested.emit(g, n)
                )

        if not menu.isEmpty():
            menu.exec(self.viewport().mapToGlobal(pos))
