"""Left-panel scene outliner: header bar, search filter, and tree."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


# Top-level group names
GROUPS = (
    "Sources", "Surfaces", "Materials", "Optical Properties",
    "Detectors", "Sphere Detectors", "Solid Bodies",
)

# Icon colors per group type
_GROUP_ICON_COLOR: dict[str, str] = {
    "Sources": "#e8b04a",           # amber — matches ACTION_AMBER
    "Surfaces": "#42a5f5",          # blue
    "Materials": "#9e9e9e",         # gray
    "Optical Properties": "#ab47bc", # purple
    "Detectors": "#66bb6a",         # green
    "Sphere Detectors": "#26c6da",  # teal
    "Solid Bodies": "#ff7043",      # orange
}

_ADD_LABEL: dict[str, str] = {
    "Sources": "Add Point Source",
    "Surfaces": "Add Surface",
    "Materials": "Add Material",
    "Optical Properties": "Add Optical Properties",
    "Detectors": "Add Detector Surface",
    "Sphere Detectors": "Add Sphere Detector",
}


def _make_filled_icon(color_hex: str, size: int = 12) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(Qt.PenStyle.NoPen)
    m = 1
    p.drawEllipse(m, m, size - 2 * m, size - 2 * m)
    p.end()
    return QIcon(pixmap)


def _make_outline_icon(color_hex: str, size: int = 12) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(color_hex), 1.5))
    m = 2
    p.drawEllipse(m, m, size - 2 * m, size - 2 * m)
    p.end()
    return QIcon(pixmap)


class _SceneTreeWidget(QTreeWidget):
    """Inner QTreeWidget — all tree logic lives here."""

    object_selected = Signal(str, str)
    multi_selected = Signal(str, list)
    add_requested = Signal(str)
    delete_requested = Signal(str, str)
    duplicate_requested = Signal(str, str)
    visibility_toggled = Signal(str, str, bool)  # (group, name, enabled)

    _ICONS_FILLED: dict[str, QIcon] = {}
    _ICONS_OUTLINE: dict[str, QIcon] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemExpanded.connect(self._update_arrow)
        self.itemCollapsed.connect(self._update_arrow)
        self.setRootIsDecorated(False)
        self.setIndentation(16)

        self._loading = False
        self._ensure_icons()

        self._group_items: dict[str, QTreeWidgetItem] = {}
        for group in GROUPS:
            item = QTreeWidgetItem(self, [f"\u25BC {group}"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, group)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setExpanded(True)
            self._group_items[group] = item

        self.itemChanged.connect(self._on_item_changed)

    @classmethod
    def _ensure_icons(cls) -> None:
        if cls._ICONS_FILLED:
            return
        for group, color in _GROUP_ICON_COLOR.items():
            cls._ICONS_FILLED[group] = _make_filled_icon(color, size=12)
            cls._ICONS_OUTLINE[group] = _make_outline_icon(color, size=12)

    def _get_icon(self, group: str, filled: bool = True) -> QIcon:
        cache = self._ICONS_FILLED if filled else self._ICONS_OUTLINE
        return cache.get(group, QIcon())

    def _update_arrow(self, item: QTreeWidgetItem) -> None:
        stored = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if stored is not None:
            arrow = "\u25BC" if item.isExpanded() else "\u25B6"
            item.setText(0, f"{arrow} {stored}")

    def _get_group_name(self, item: QTreeWidgetItem) -> str:
        stored = item.data(0, Qt.ItemDataRole.UserRole + 1)
        return stored if stored else item.text(0)

    def refresh(self, project) -> None:
        self._loading = True
        try:
            self._refresh_inner(project)
        finally:
            self._loading = False

    def _refresh_inner(self, project) -> None:
        disabled_sources = {s.name for s in project.sources if not s.enabled}

        project_sigma = getattr(project.settings, "source_position_sigma_mm", 0.0)
        toleranced_sources = {
            s.name for s in project.sources
            if getattr(s, "position_sigma_mm", 0.0) > 0 or project_sigma > 0
        }

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
                enabled = name not in disabled_sources
                # Phase 5: badge toleranced sources with " ±"; store clean name in UserRole
                if group_name == "Sources" and name in toleranced_sources:
                    display_name = name + " \u00b1"
                else:
                    display_name = name
                child = QTreeWidgetItem(parent, [display_name])
                if group_name == "Sources":
                    # Store clean name for signal emission (avoids " ±" in lookup keys)
                    child.setData(0, Qt.ItemDataRole.UserRole, name)
                    child.setFlags(
                        child.flags() | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    child.setCheckState(
                        0,
                        Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked,
                    )
                    child.setIcon(0, self._get_icon(group_name, filled=enabled))
                    if not enabled:
                        child.setForeground(0, QColor("#807c74"))
                        child.setToolTip(0, "Disabled — uncheck to hide from sim")
                    else:
                        child.setToolTip(0, "Enabled — uncheck to disable")
                else:
                    child.setIcon(0, self._get_icon(group_name))

        # Solid Bodies: hierarchical tree
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

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._loading or column != 0:
            return
        parent = item.parent()
        if parent is None:
            return
        if self._get_group_name(parent) != "Sources":
            return
        enabled = item.checkState(0) == Qt.CheckState.Checked
        # Update icon and text color to reflect new state
        self._loading = True
        try:
            item.setIcon(0, self._get_icon("Sources", filled=enabled))
            if enabled:
                item.setForeground(0, QColor("#f1ede4"))
                item.setToolTip(0, "Enabled — uncheck to disable")
            else:
                item.setForeground(0, QColor("#807c74"))
                item.setToolTip(0, "Disabled — uncheck to hide from sim")
        finally:
            self._loading = False
        # Phase 5: use clean name from UserRole to avoid " ±" badge in signal
        clean_name = item.data(0, Qt.ItemDataRole.UserRole)
        emit_name = clean_name if clean_name is not None else item.text(0)
        self.visibility_toggled.emit("Sources", emit_name, enabled)

    def _item_group_and_name(self, item: QTreeWidgetItem) -> tuple[str, str]:
        parent = item.parent()
        if parent is None:
            return "", ""
        grandparent = parent.parent()
        if (grandparent is not None
                and grandparent.parent() is None
                and self._get_group_name(grandparent) == "Solid Bodies"):
            user_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if user_data:
                _, body_name = user_data
            else:
                body_name = parent.text(0)
                for prefix in ("[Box] ", "[Cyl] ", "[Prism] "):
                    if body_name.startswith(prefix):
                        body_name = body_name[len(prefix):]
                        break
            return "Solid Bodies", f"{body_name}::{item.text(0)}"
        if parent.parent() is None and self._get_group_name(parent) == "Solid Bodies":
            user_data = item.data(0, Qt.ItemDataRole.UserRole)
            if user_data:
                body_type, body_name = user_data
                return f"Solid Bodies:{body_type}", body_name
            name = item.text(0)
            for prefix in ("[Box] ", "[Cyl] ", "[Prism] "):
                if name.startswith(prefix):
                    return "Solid Bodies:box", name[len(prefix):]
            return "Solid Bodies:box", name
        group = self._get_group_name(parent)
        # Phase 5: source items may have a " ±" badge; use stored clean name if present
        if group == "Sources":
            clean = item.data(0, Qt.ItemDataRole.UserRole)
            if clean is not None:
                return group, clean
        return group, item.text(0)

    def _on_selection_changed(self) -> None:
        selected = self.selectedItems()
        items = [it for it in selected if it.parent() is not None]
        if not items:
            return
        if len(items) == 1:
            group, name = self._item_group_and_name(items[0])
            if group:
                self.object_selected.emit(group, name)
            return
        groups_names = [self._item_group_and_name(it) for it in items]
        all_groups = {gn[0] for gn in groups_names}
        if len(all_groups) == 1:
            group = all_groups.pop()
            self.multi_selected.emit(group, [gn[1] for gn in groups_names])
        else:
            group, name = self._item_group_and_name(items[0])
            if group:
                self.object_selected.emit(group, name)

    def _context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        if item.parent() is None:
            group = self._get_group_name(item)
            if group == "Solid Bodies":
                menu.addAction("Add Solid Box").triggered.connect(
                    lambda: self.add_requested.emit("Solid Bodies:box")
                )
                menu.addAction("Add Cylinder").triggered.connect(
                    lambda: self.add_requested.emit("Solid Bodies:cylinder")
                )
                menu.addAction("Add Prism").triggered.connect(
                    lambda: self.add_requested.emit("Solid Bodies:prism")
                )
            else:
                label = _ADD_LABEL.get(group, f"Add {group[:-1]}")
                menu.addAction(label).triggered.connect(
                    lambda: self.add_requested.emit(group)
                )
        else:
            group, name = self._item_group_and_name(item)
            if group.startswith("Solid Bodies") and "::" in name:
                pass  # face nodes have no standalone actions
            elif group:
                if group == "Sources":
                    src_item = item
                    chk = src_item.checkState(0)
                    toggle_label = "Disable Source" if chk == Qt.CheckState.Checked else "Enable Source"
                    menu.addAction(toggle_label).triggered.connect(
                        lambda checked=False, i=src_item: i.setCheckState(
                            0,
                            Qt.CheckState.Unchecked
                            if i.checkState(0) == Qt.CheckState.Checked
                            else Qt.CheckState.Checked,
                        )
                    )
                    menu.addSeparator()
                menu.addAction(f"Duplicate {name}").triggered.connect(
                    lambda checked=False, g=group, n=name: self.duplicate_requested.emit(g, n)
                )
                menu.addSeparator()
                menu.addAction(f"Delete {name}").triggered.connect(
                    lambda checked=False, g=group, n=name: self.delete_requested.emit(g, n)
                )
        if not menu.isEmpty():
            menu.exec(self.viewport().mapToGlobal(pos))


class ObjectTree(QWidget):
    """Scene outliner: 'SCENE · N items' header + search filter + tree."""

    object_selected = Signal(str, str)
    multi_selected = Signal(str, list)
    add_requested = Signal(str)
    delete_requested = Signal(str, str)
    duplicate_requested = Signal(str, str)
    visibility_toggled = Signal(str, str, bool)  # (group, name, enabled)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setObjectName("scene_header_bar")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 5, 10, 5)
        self._count_label = QLabel("SCENE")
        self._count_label.setObjectName("scene_title")
        hl.addWidget(self._count_label)
        hl.addStretch()
        layout.addWidget(header)

        # Search box
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter…")
        self._search.setObjectName("scene_search")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        # Inner tree
        self._tree = _SceneTreeWidget(self)
        layout.addWidget(self._tree)

        # Wire pass-through signals
        self._tree.object_selected.connect(self.object_selected)
        self._tree.multi_selected.connect(self.multi_selected)
        self._tree.add_requested.connect(self.add_requested)
        self._tree.delete_requested.connect(self.delete_requested)
        self._tree.duplicate_requested.connect(self.duplicate_requested)
        self._tree.visibility_toggled.connect(self.visibility_toggled)

    def refresh(self, project) -> None:
        self._tree.refresh(project)
        total = (
            len(project.sources)
            + len(project.surfaces)
            + len(project.materials)
            + len(getattr(project, "optical_properties", {}))
            + len(project.detectors)
            + len(getattr(project, "sphere_detectors", []))
            + len(getattr(project, "solid_bodies", []))
            + len(getattr(project, "solid_cylinders", []))
            + len(getattr(project, "solid_prisms", []))
        )
        self._count_label.setText(f"SCENE  ·  {total}")
        self._apply_filter(self._search.text())

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        for group_item in self._tree._group_items.values():
            for i in range(group_item.childCount()):
                child = group_item.child(i)
                if not query or query in child.text(0).lower():
                    child.setHidden(False)
                else:
                    # Show solid-body parents if any child face matches
                    child_match = any(
                        query in child.child(j).text(0).lower()
                        for j in range(child.childCount())
                    )
                    child.setHidden(not child_match)

    def setAccessibleName(self, name: str) -> None:  # type: ignore[override]
        self._tree.setAccessibleName(name)
