"""Right-panel property editor for selected scene objects."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QColorDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)

from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.geometry import Rectangle


_AXIS_MAP = {
    (0, 1.0): (np.array([0, 1, 0], float), np.array([0, 0, 1], float)),
    (0, -1.0): (np.array([0, 1, 0], float), np.array([0, 0, -1], float)),
    (1, 1.0): (np.array([0, 0, 1], float), np.array([1, 0, 0], float)),
    (1, -1.0): (np.array([0, 0, 1], float), np.array([-1, 0, 0], float)),
    (2, 1.0): (np.array([1, 0, 0], float), np.array([0, 1, 0], float)),
    (2, -1.0): (np.array([1, 0, 0], float), np.array([0, -1, 0], float)),
}


def _dspin(lo=-9999.0, hi=9999.0, dec=2, val=0.0, step=0.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(dec)
    w.setValue(val)
    w.setSingleStep(step)
    return w


def _rotation_matrix_xyz(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    rx, ry, rz = np.radians([rx_deg, ry_deg, rz_deg])
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    rx_m = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=float)
    ry_m = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=float)
    rz_m = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=float)
    return rz_m @ ry_m @ rx_m


def _euler_xyz_from_matrix(r: np.ndarray) -> tuple[float, float, float]:
    sy = -r[2, 0]
    sy = np.clip(sy, -1.0, 1.0)
    ry = np.arcsin(sy)
    cy = np.cos(ry)
    if abs(cy) > 1e-8:
        rx = np.arctan2(r[2, 1], r[2, 2])
        rz = np.arctan2(r[1, 0], r[0, 0])
    else:
        rx = np.arctan2(-r[1, 2], r[1, 1])
        rz = 0.0
    return tuple(np.degrees([rx, ry, rz]))


def _face_basis(face_key: tuple[int, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    u0, v0 = _AXIS_MAP[face_key]
    n0 = np.cross(u0, v0)
    return u0, v0, n0


def _axes_from_face_and_rotation(face_key: tuple[int, float], rx: float, ry: float, rz: float) -> tuple[np.ndarray, np.ndarray]:
    u0, v0, _ = _face_basis(face_key)
    r = _rotation_matrix_xyz(rx, ry, rz)
    u = r @ u0
    v = r @ v0
    return u, v


def _rotation_from_axes(face_key: tuple[int, float], u: np.ndarray, v: np.ndarray) -> tuple[float, float, float]:
    u0, v0, n0 = _face_basis(face_key)
    n = np.cross(u, v)
    a = np.column_stack([u, v, n])
    b = np.column_stack([u0, v0, n0])
    r = a @ b.T
    return _euler_xyz_from_matrix(r)


class PropertiesPanel(QStackedWidget):
    properties_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)

        empty = QLabel("Select an object to edit")
        empty.setStyleSheet("color: gray; padding: 8px;")
        self.addWidget(empty)

        for form_cls in (SourceForm, SurfaceForm, MaterialForm, DetectorForm, SettingsForm):
            form = form_cls()
            form.changed.connect(self.properties_changed)
            self.addWidget(form)
            setattr(self, f"_{form_cls.__name__.lower()}", form)

    def _finalize_active_editor(self):
        focus = QApplication.focusWidget()
        if focus is not None and self.isAncestorOf(focus):
            focus.clearFocus()
            QApplication.processEvents()

    def show_source(self, src, distribution_names=None):
        self._finalize_active_editor()
        self._sourceform.load(src, distribution_names=distribution_names)
        self.setCurrentWidget(self._sourceform)

    def show_surface(self, surf, mat_names):
        self._finalize_active_editor()
        self._surfaceform.load(surf, mat_names)
        self.setCurrentWidget(self._surfaceform)

    def show_material(self, mat):
        self._finalize_active_editor()
        self._materialform.load(mat)
        self.setCurrentWidget(self._materialform)

    def show_detector(self, det):
        self._finalize_active_editor()
        self._detectorform.load(det)
        self.setCurrentWidget(self._detectorform)

    def show_settings(self, settings):
        self._finalize_active_editor()
        self._settingsform.load(settings)
        self.setCurrentWidget(self._settingsform)

    def clear_selection(self):
        self._finalize_active_editor()
        self.setCurrentIndex(0)


class SourceForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = QLineEdit()
        self._px = _dspin()
        self._py = _dspin()
        self._pz = _dspin()
        self._flux = _dspin(0, 1e7, 1, 100.0, 10.0)
        self._dist = QComboBox()
        self._dist.addItems(["isotropic", "lambertian"])
        self._enabled = QCheckBox()
        self._enabled.setChecked(True)
        fl.addRow("Name:", self._name)
        fl.addRow("Enabled:", self._enabled)
        fl.addRow("X:", self._px)
        fl.addRow("Y:", self._py)
        fl.addRow("Z:", self._pz)
        fl.addRow("Flux:", self._flux)
        fl.addRow("Distribution:", self._dist)
        self._src = None
        self._loading = False
        for w in (self._px, self._py, self._pz, self._flux):
            w.valueChanged.connect(self._apply)
        self._dist.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        self._enabled.toggled.connect(self._apply)

    def load(self, src, distribution_names=None):
        self._loading = True
        self._src = src
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._px),
            QSignalBlocker(self._py),
            QSignalBlocker(self._pz),
            QSignalBlocker(self._flux),
            QSignalBlocker(self._dist),
            QSignalBlocker(self._enabled),
        ]
        self._name.setText(src.name)
        self._enabled.setChecked(src.enabled)
        self._px.setValue(src.position[0])
        self._py.setValue(src.position[1])
        self._pz.setValue(src.position[2])
        self._flux.setValue(src.flux)
        base = ["isotropic", "lambertian"]
        extra = [name for name in (distribution_names or []) if name not in base]
        self._dist.clear()
        self._dist.addItems(base + extra)
        if self._dist.findText(src.distribution) < 0:
            self._dist.addItem(src.distribution)
        self._dist.setCurrentText(src.distribution)
        self._loading = False
        del blockers

    def _apply(self):
        if self._src is None or self._loading:
            return
        self._src.name = self._name.text()
        self._src.enabled = self._enabled.isChecked()
        self._src.position = np.array([self._px.value(), self._py.value(), self._pz.value()])
        self._src.flux = self._flux.value()
        self._src.distribution = self._dist.currentText()
        self.changed.emit()


class SurfaceForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = QLineEdit()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        self._sw = _dspin(0.01, 9999, 2, 10.0)
        self._sh = _dspin(0.01, 9999, 2, 10.0)
        self._face = QComboBox()
        self._face.addItems(["+X face", "-X face", "+Y face", "-Y face", "+Z face", "-Z face"])
        self._rx = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._ry = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._rz = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._mat = QComboBox()
        self._normal_lbl = QLabel("normal: ?")
        self._normal_lbl.setStyleSheet("color: gray; font-size: 11px;")
        fl.addRow("Name:", self._name)
        fl.addRow("Center X:", self._cx)
        fl.addRow("Center Y:", self._cy)
        fl.addRow("Center Z:", self._cz)
        fl.addRow("Width:", self._sw)
        fl.addRow("Height:", self._sh)
        fl.addRow("Face direction:", self._face)
        fl.addRow("Rotate X (deg):", self._rx)
        fl.addRow("Rotate Y (deg):", self._ry)
        fl.addRow("Rotate Z (deg):", self._rz)
        fl.addRow("Material:", self._mat)
        fl.addRow("", self._normal_lbl)
        self._surf = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._sw, self._sh, self._rx, self._ry, self._rz):
            w.valueChanged.connect(self._apply)
        self._face.currentIndexChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, surf: Rectangle, mat_names: list[str]):
        self._loading = True
        self._surf = surf
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._cx),
            QSignalBlocker(self._cy),
            QSignalBlocker(self._cz),
            QSignalBlocker(self._sw),
            QSignalBlocker(self._sh),
            QSignalBlocker(self._face),
            QSignalBlocker(self._rx),
            QSignalBlocker(self._ry),
            QSignalBlocker(self._rz),
            QSignalBlocker(self._mat),
        ]
        self._name.setText(surf.name)
        self._cx.setValue(surf.center[0])
        self._cy.setValue(surf.center[1])
        self._cz.setValue(surf.center[2])
        self._sw.setValue(surf.size[0])
        self._sh.setValue(surf.size[1])
        key = (surf.dominant_normal_axis, surf.dominant_normal_sign)
        idx = self._FACE_KEYS.index(key) if key in self._FACE_KEYS else 4
        self._face.setCurrentIndex(idx)
        rx, ry, rz = _rotation_from_axes(self._FACE_KEYS[self._face.currentIndex()], surf.u_axis, surf.v_axis)
        self._rx.setValue(float(rx))
        self._ry.setValue(float(ry))
        self._rz.setValue(float(rz))
        self._mat.clear()
        self._mat.addItems(mat_names)
        midx = self._mat.findText(surf.material_name)
        if midx >= 0:
            self._mat.setCurrentIndex(midx)
        n = surf.normal
        self._normal_lbl.setText(f"normal: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")
        self._loading = False
        del blockers

    def _apply(self):
        if self._surf is None or self._loading:
            return
        self._surf.name = self._name.text()
        self._surf.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._surf.size = (self._sw.value(), self._sh.value())
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        self._surf.u_axis = u.copy()
        self._surf.v_axis = v.copy()
        if self._mat.currentText():
            self._surf.material_name = self._mat.currentText()
        n = self._surf.normal
        self._normal_lbl.setText(f"normal: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")
        self.changed.emit()


class MaterialForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = QLineEdit()
        self._type = QComboBox()
        self._type.addItems(["reflector", "absorber", "diffuser"])
        self._ref = _dspin(0, 1, 3, 0.9, 0.01)
        self._abs = _dspin(0, 1, 3, 0.1, 0.01)
        self._trn = _dspin(0, 1, 3, 0.0, 0.01)
        self._mode = QComboBox()
        self._mode.addItems(["Diffuse (Lambertian)", "Specular"])
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        fl.addRow("Name:", self._name)
        fl.addRow("Type:", self._type)
        fl.addRow("Reflectance:", self._ref)
        fl.addRow("Absorption:", self._abs)
        fl.addRow("Transmittance:", self._trn)
        fl.addRow("Reflection:", self._mode)
        fl.addRow("Color:", self._color_btn)
        self._mat = None
        self._loading = False
        self._color = (0.55, 0.65, 1.0)
        for w in (self._ref, self._abs, self._trn):
            w.valueChanged.connect(self._apply)
        self._type.currentIndexChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        self._update_color_button()

    def load(self, mat):
        self._loading = True
        self._mat = mat
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._type),
            QSignalBlocker(self._ref),
            QSignalBlocker(self._abs),
            QSignalBlocker(self._trn),
            QSignalBlocker(self._mode),
        ]
        self._name.setText(mat.name)
        self._type.setCurrentIndex(["reflector", "absorber", "diffuser"].index(mat.surface_type))
        self._ref.setValue(mat.reflectance)
        self._abs.setValue(mat.absorption)
        self._trn.setValue(mat.transmittance)
        self._mode.setCurrentIndex(0 if mat.is_diffuse else 1)
        self._color = tuple(mat.color)
        self._update_color_button()
        self._loading = False
        del blockers

    def _update_color_button(self):
        r = int(round(self._color[0] * 255))
        g = int(round(self._color[1] * 255))
        b = int(round(self._color[2] * 255))
        self._color_btn.setText(f"#{r:02X}{g:02X}{b:02X}")
        self._color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")

    def _pick_color(self):
        if self._mat is None:
            return
        start = QColor.fromRgbF(self._color[0], self._color[1], self._color[2])
        picked = QColorDialog.getColor(start, self, "Choose Material Color")
        if not picked.isValid():
            return
        self._color = (picked.redF(), picked.greenF(), picked.blueF())
        self._update_color_button()
        self._apply()

    def _apply(self):
        if self._mat is None or self._loading:
            return
        self._mat.name = self._name.text()
        self._mat.surface_type = self._type.currentText()
        self._mat.reflectance = self._ref.value()
        self._mat.absorption = self._abs.value()
        self._mat.transmittance = self._trn.value()
        self._mat.is_diffuse = self._mode.currentIndex() == 0
        self._mat.color = self._color
        self.changed.emit()


class DetectorForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = QLineEdit()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin(val=5.0)
        self._sw = _dspin(0.01, 9999, 2, 10.0)
        self._sh = _dspin(0.01, 9999, 2, 10.0)
        self._face = QComboBox()
        self._face.addItems(["+X face", "-X face", "+Y face", "-Y face", "+Z face", "-Z face"])
        self._face.setCurrentIndex(4)
        self._rx = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._ry = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._rz = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._rx_res = QSpinBox()
        self._rx_res.setRange(10, 2000)
        self._rx_res.setValue(100)
        self._ry_res = QSpinBox()
        self._ry_res.setRange(10, 2000)
        self._ry_res.setValue(100)
        fl.addRow("Name:", self._name)
        fl.addRow("Center X:", self._cx)
        fl.addRow("Center Y:", self._cy)
        fl.addRow("Center Z:", self._cz)
        fl.addRow("Width:", self._sw)
        fl.addRow("Height:", self._sh)
        fl.addRow("Face direction:", self._face)
        fl.addRow("Rotate X (deg):", self._rx)
        fl.addRow("Rotate Y (deg):", self._ry)
        fl.addRow("Rotate Z (deg):", self._rz)
        fl.addRow("Resolution X:", self._rx_res)
        fl.addRow("Resolution Y:", self._ry_res)
        self._det = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._sw, self._sh, self._rx, self._ry, self._rz):
            w.valueChanged.connect(self._apply)
        self._face.currentIndexChanged.connect(self._apply)
        self._rx_res.valueChanged.connect(self._apply)
        self._ry_res.valueChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, det: DetectorSurface):
        self._loading = True
        self._det = det
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._cx),
            QSignalBlocker(self._cy),
            QSignalBlocker(self._cz),
            QSignalBlocker(self._sw),
            QSignalBlocker(self._sh),
            QSignalBlocker(self._face),
            QSignalBlocker(self._rx),
            QSignalBlocker(self._ry),
            QSignalBlocker(self._rz),
            QSignalBlocker(self._rx_res),
            QSignalBlocker(self._ry_res),
        ]
        self._name.setText(det.name)
        self._cx.setValue(det.center[0])
        self._cy.setValue(det.center[1])
        self._cz.setValue(det.center[2])
        self._sw.setValue(det.size[0])
        self._sh.setValue(det.size[1])
        key = (det.dominant_normal_axis, det.dominant_normal_sign)
        idx = self._FACE_KEYS.index(key) if key in self._FACE_KEYS else 4
        self._face.setCurrentIndex(idx)
        rx, ry, rz = _rotation_from_axes(self._FACE_KEYS[self._face.currentIndex()], det.u_axis, det.v_axis)
        self._rx.setValue(float(rx))
        self._ry.setValue(float(ry))
        self._rz.setValue(float(rz))
        self._rx_res.setValue(det.resolution[0])
        self._ry_res.setValue(det.resolution[1])
        self._loading = False
        del blockers

    def _apply(self):
        if self._det is None or self._loading:
            return
        self._det.name = self._name.text()
        self._det.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._det.size = (self._sw.value(), self._sh.value())
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        self._det.u_axis = u.copy()
        self._det.v_axis = v.copy()
        self._det.resolution = (self._rx_res.value(), self._ry_res.value())
        self.changed.emit()


_QUALITY_PRESETS = {
    "Quick":    dict(rays=1_000,   bounces=20,  rec=50),
    "Standard": dict(rays=10_000,  bounces=50,  rec=200),
    "High":     dict(rays=100_000, bounces=100, rec=500),
}


class SettingsForm(QWidget):
    changed = Signal()

    def __init__(self):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Quality preset row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Quality:"))
        for name, vals in _QUALITY_PRESETS.items():
            btn = QPushButton(name)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _=False, v=vals: self._apply_preset(v))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        outer.addLayout(preset_row)

        fl = QFormLayout()
        outer.addLayout(fl)

        self._rays = QSpinBox()
        self._rays.setRange(100, 10_000_000)
        self._rays.setValue(10_000)
        self._rays.setSingleStep(1000)
        self._bounce = QSpinBox()
        self._bounce.setRange(1, 500)
        self._bounce.setValue(50)
        self._thresh = _dspin(0, 1, 6, 0.001, 0.0001)
        self._seed = QSpinBox()
        self._seed.setRange(0, 999999)
        self._seed.setValue(42)
        self._rec = QSpinBox()
        self._rec.setRange(0, 5000)
        self._rec.setValue(200)
        self._unit = QComboBox()
        self._unit.addItems(["mm", "cm", "m", "in"])
        fl.addRow("Rays per source:", self._rays)
        fl.addRow("Max bounces:", self._bounce)
        fl.addRow("Energy threshold:", self._thresh)
        fl.addRow("Random seed:", self._seed)
        fl.addRow("Record ray paths:", self._rec)
        fl.addRow("Distance unit:", self._unit)
        self._s = None
        self._loading = False
        self._rays.valueChanged.connect(self._apply)
        self._bounce.valueChanged.connect(self._apply)
        self._thresh.valueChanged.connect(self._apply)
        self._seed.valueChanged.connect(self._apply)
        self._rec.valueChanged.connect(self._apply)
        self._unit.currentIndexChanged.connect(self._apply)

    def load(self, s):
        self._loading = True
        self._s = s
        blockers = [
            QSignalBlocker(self._rays),
            QSignalBlocker(self._bounce),
            QSignalBlocker(self._thresh),
            QSignalBlocker(self._seed),
            QSignalBlocker(self._rec),
            QSignalBlocker(self._unit),
        ]
        self._rays.setValue(s.rays_per_source)
        self._bounce.setValue(s.max_bounces)
        self._thresh.setValue(s.energy_threshold)
        self._seed.setValue(s.random_seed)
        self._rec.setValue(s.record_ray_paths)
        idx = self._unit.findText(s.distance_unit)
        if idx >= 0:
            self._unit.setCurrentIndex(idx)
        self._loading = False
        del blockers

    def _apply_preset(self, vals: dict):
        self._rays.setValue(vals["rays"])
        self._bounce.setValue(vals["bounces"])
        self._rec.setValue(vals["rec"])
        # _apply fires automatically via valueChanged signals

    def _apply(self):
        if self._s is None or self._loading:
            return
        self._s.rays_per_source = self._rays.value()
        self._s.max_bounces = self._bounce.value()
        self._s.energy_threshold = self._thresh.value()
        self._s.random_seed = self._seed.value()
        self._s.record_ray_paths = self._rec.value()
        self._s.distance_unit = self._unit.currentText()
        self.changed.emit()
