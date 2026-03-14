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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)

from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.solid_body import SolidBox, FACE_NAMES


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


def _name_edit(max_length: int = 128) -> QLineEdit:
    """Create a QLineEdit for object names with a max-length constraint."""
    w = QLineEdit()
    w.setMaxLength(max_length)
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

        for form_cls in (SourceForm, SurfaceForm, MaterialForm, OpticalPropertiesForm, DetectorForm, SphereDetectorForm, SettingsForm, BatchForm, SolidBoxForm, FaceForm):
            form = form_cls()
            form.changed.connect(self.properties_changed)
            self.addWidget(form)
            setattr(self, f"_{form_cls.__name__.lower()}", form)

    def _finalize_active_editor(self):
        focus = QApplication.focusWidget()
        if focus is not None and self.isAncestorOf(focus):
            focus.clearFocus()

    def show_source(self, src, distribution_names=None):
        self._finalize_active_editor()
        self._sourceform.load(src, distribution_names=distribution_names)
        self.setCurrentWidget(self._sourceform)

    def show_surface(self, surf, mat_names, opt_prop_names=None):
        self._finalize_active_editor()
        self._surfaceform.load(surf, mat_names, opt_prop_names)
        self.setCurrentWidget(self._surfaceform)

    def show_material(self, mat):
        self._finalize_active_editor()
        self._materialform.load(mat)
        self.setCurrentWidget(self._materialform)

    def show_detector(self, det):
        self._finalize_active_editor()
        self._detectorform.load(det)
        self.setCurrentWidget(self._detectorform)

    def show_sphere_detector(self, det):
        self._finalize_active_editor()
        self._spheredetectorform.load(det)
        self.setCurrentWidget(self._spheredetectorform)

    def show_settings(self, settings):
        self._finalize_active_editor()
        self._settingsform.load(settings)
        self.setCurrentWidget(self._settingsform)

    def show_optical_properties(self, op):
        self._finalize_active_editor()
        self._opticalpropertiesform.load(op)
        self.setCurrentWidget(self._opticalpropertiesform)

    def show_batch(self, group: str, objects: list, distribution_names=None, mat_names=None):
        self._finalize_active_editor()
        self._batchform.load(group, objects, distribution_names=distribution_names, mat_names=mat_names)
        self.setCurrentWidget(self._batchform)

    def show_solid_box(self, box: "SolidBox", mat_names: list[str]):
        self._finalize_active_editor()
        self._solidboxform.load(box, mat_names)
        self.setCurrentWidget(self._solidboxform)

    def show_face(self, box: "SolidBox", face_id: str, opt_prop_names: list[str]):
        self._finalize_active_editor()
        self._faceform.load(box, face_id, opt_prop_names)
        self.setCurrentWidget(self._faceform)

    def clear_selection(self):
        self._finalize_active_editor()
        self.setCurrentIndex(0)


class SourceForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
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

        # Peak intensity helper (read/convert) ──────────────────────────
        peak_row = QHBoxLayout()
        self._peak_spin = _dspin(0.01, 1e8, 3, 31.83, 10.0)
        self._peak_spin.setToolTip(
            "Peak intensity in cd.\n"
            "Lambertian: flux = π × cd\n"
            "Isotropic:  flux = 4π × cd\n"
            "Editing this field updates Flux automatically."
        )
        self._peak_set_btn = QPushButton("→ Flux")
        self._peak_set_btn.setToolTip("Apply peak cd value and update Flux")
        self._peak_set_btn.setFixedWidth(56)
        self._peak_set_btn.clicked.connect(self._apply_peak)
        peak_row.addWidget(self._peak_spin)
        peak_row.addWidget(self._peak_set_btn)
        self._peak_lbl = QLabel("")          # holds the formatted estimate
        self._peak_lbl.setStyleSheet("color: gray; font-size: 10px;")
        fl.addRow("Peak cd:", peak_row)
        # ────────────────────────────────────────────────────────────────

        fl.addRow("Distribution:", self._dist)

        # Bin tolerance, current scaling, thermal derating
        self._tolerance = _dspin(0, 100, 1, 0.0, 1.0)
        self._tolerance.setToolTip("LED flux bin tolerance ±% (0 = exact)")
        fl.addRow("Flux tolerance ±%:", self._tolerance)
        self._current = _dspin(0, 1e5, 1, 0.0, 1.0)
        self._current.setToolTip("Drive current in mA (0 = use flux directly)")
        fl.addRow("Current (mA):", self._current)
        self._flux_per_mA = _dspin(0, 1e5, 4, 0.0, 0.01)
        self._flux_per_mA.setToolTip("Flux per mA (lm/mA). When >0, flux = current × flux_per_mA")
        fl.addRow("Flux/mA:", self._flux_per_mA)
        self._thermal = _dspin(0, 1, 3, 1.0, 0.01)
        self._thermal.setToolTip("Thermal derating factor 0–1 (1 = no derating)")
        fl.addRow("Thermal derate:", self._thermal)
        # LED color (RGB)
        color_row = QHBoxLayout()
        self._cr = _dspin(0, 1, 2, 1.0, 0.05)
        self._cg = _dspin(0, 1, 2, 1.0, 0.05)
        self._cb = _dspin(0, 1, 2, 1.0, 0.05)
        self._cr.setToolTip("Red weight 0–1")
        self._cg.setToolTip("Green weight 0–1")
        self._cb.setToolTip("Blue weight 0–1")
        color_row.addWidget(QLabel("R:"))
        color_row.addWidget(self._cr)
        color_row.addWidget(QLabel("G:"))
        color_row.addWidget(self._cg)
        color_row.addWidget(QLabel("B:"))
        color_row.addWidget(self._cb)
        fl.addRow("LED Color:", color_row)
        # Spectral power distribution
        self._spd = QComboBox()
        self._spd.addItems(["white", "warm_white", "cool_white",
                            "mono_450", "mono_525", "mono_630"])
        self._spd.setEditable(True)
        self._spd.setToolTip(
            "Spectral power distribution.\n"
            "Built-in: white, warm_white, cool_white\n"
            "Monochromatic: mono_<nm> (e.g. mono_550)\n"
            "Or type a custom SPD name."
        )
        fl.addRow("SPD:", self._spd)

        self._src = None
        self._loading = False
        for w in (self._px, self._py, self._pz, self._flux, self._tolerance,
                  self._current, self._flux_per_mA, self._thermal,
                  self._cr, self._cg, self._cb):
            w.valueChanged.connect(self._apply)
        self._dist.currentIndexChanged.connect(self._apply)
        self._spd.currentTextChanged.connect(self._apply)
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
            QSignalBlocker(self._tolerance),
            QSignalBlocker(self._current),
            QSignalBlocker(self._flux_per_mA),
            QSignalBlocker(self._thermal),
            QSignalBlocker(self._cr),
            QSignalBlocker(self._cg),
            QSignalBlocker(self._cb),
            QSignalBlocker(self._spd),
        ]
        self._name.setText(src.name)
        self._enabled.setChecked(src.enabled)
        self._px.setValue(src.position[0])
        self._py.setValue(src.position[1])
        self._pz.setValue(src.position[2])
        self._flux.setValue(src.flux)
        self._tolerance.setValue(src.flux_tolerance)
        self._current.setValue(src.current_mA)
        self._flux_per_mA.setValue(src.flux_per_mA)
        self._thermal.setValue(src.thermal_derate)
        self._cr.setValue(src.color_rgb[0])
        self._cg.setValue(src.color_rgb[1])
        self._cb.setValue(src.color_rgb[2])
        if self._spd.findText(src.spd) < 0:
            self._spd.addItem(src.spd)
        self._spd.setCurrentText(src.spd)
        base = ["isotropic", "lambertian"]
        extra = [name for name in (distribution_names or []) if name not in base]
        self._dist.clear()
        self._dist.addItems(base + extra)
        if self._dist.findText(src.distribution) < 0:
            self._dist.addItem(src.distribution)
        self._dist.setCurrentText(src.distribution)
        self._loading = False
        del blockers
        self._update_peak_display()

    # ── peak intensity helpers ─────────────────────────────────────────

    def _flux_to_peak(self, flux: float, dist: str) -> float:
        import math
        return flux / (math.pi if "lambertian" in dist else 4 * math.pi)

    def _peak_to_flux(self, peak: float, dist: str) -> float:
        import math
        return peak * (math.pi if "lambertian" in dist else 4 * math.pi)

    def _update_peak_display(self):
        flux = self._flux.value()
        dist = self._dist.currentText()
        peak = self._flux_to_peak(flux, dist)
        # Update the spinbox without triggering any connected slot
        self._peak_spin.blockSignals(True)
        self._peak_spin.setValue(peak)
        self._peak_spin.blockSignals(False)

    def _apply_peak(self):
        """Convert the peak cd spinbox value back to flux and apply."""
        if self._src is None or self._loading:
            return
        dist = self._dist.currentText()
        flux = self._peak_to_flux(self._peak_spin.value(), dist)
        self._flux.blockSignals(True)
        self._flux.setValue(flux)
        self._flux.blockSignals(False)
        self._src.flux = flux
        self._src.distribution = dist
        self.changed.emit()

    # ──────────────────────────────────────────────────────────────────

    def _apply(self):
        if self._src is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        self._src.name = name
        self._src.enabled = self._enabled.isChecked()
        self._src.position = np.array([self._px.value(), self._py.value(), self._pz.value()])
        self._src.flux = self._flux.value()
        self._src.distribution = self._dist.currentText()
        self._src.flux_tolerance = self._tolerance.value()
        self._src.current_mA = self._current.value()
        self._src.flux_per_mA = self._flux_per_mA.value()
        self._src.thermal_derate = self._thermal.value()
        self._src.color_rgb = (self._cr.value(), self._cg.value(), self._cb.value())
        self._src.spd = self._spd.currentText()
        self._update_peak_display()
        self.changed.emit()


class SurfaceForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
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
        self._opt_prop = QComboBox()
        self._opt_prop.setToolTip("Override material's optical behavior with specific optical properties")
        fl.addRow("Material:", self._mat)
        fl.addRow("Optical Props:", self._opt_prop)
        fl.addRow("", self._normal_lbl)
        self._surf = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._sw, self._sh, self._rx, self._ry, self._rz):
            w.valueChanged.connect(self._apply)
        self._face.currentIndexChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._opt_prop.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, surf: Rectangle, mat_names: list[str], opt_prop_names: list[str] | None = None):
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
            QSignalBlocker(self._opt_prop),
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
        self._opt_prop.clear()
        self._opt_prop.addItem("(none)")
        if opt_prop_names:
            self._opt_prop.addItems(opt_prop_names)
        if surf.optical_properties_name:
            oidx = self._opt_prop.findText(surf.optical_properties_name)
            if oidx >= 0:
                self._opt_prop.setCurrentIndex(oidx)
        n = surf.normal
        self._normal_lbl.setText(f"normal: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")
        self._loading = False
        del blockers

    def _apply(self):
        if self._surf is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        self._surf.name = name
        self._surf.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._surf.size = (self._sw.value(), self._sh.value())
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        self._surf.u_axis = u.copy()
        self._surf.v_axis = v.copy()
        if self._mat.currentText():
            self._surf.material_name = self._mat.currentText()
        op_text = self._opt_prop.currentText()
        self._surf.optical_properties_name = "" if op_text == "(none)" else op_text
        n = self._surf.normal
        self._normal_lbl.setText(f"normal: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")
        self.changed.emit()


class MaterialForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
        self._type = QComboBox()
        self._type.addItems(["reflector", "absorber", "diffuser"])
        self._ref = _dspin(0, 1, 3, 0.9, 0.01)
        self._abs = _dspin(0, 1, 3, 0.1, 0.01)
        self._trn = _dspin(0, 1, 3, 0.0, 0.01)
        self._mode = QComboBox()
        self._mode.addItems(["Diffuse (Lambertian)", "Specular"])
        self._haze = _dspin(0, 90, 1, 0.0, 1.0)
        self._haze.setToolTip("Haze / scatter half-angle in degrees (specular only, 0 = perfect mirror)")
        self._ri = _dspin(0.1, 10.0, 3, 1.0, 0.01)
        self._ri.setToolTip("Index of refraction (1.0 = air, 1.5 = glass, 2.4 = diamond)")
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        fl.addRow("Name:", self._name)
        fl.addRow("Type:", self._type)
        fl.addRow("Reflectance:", self._ref)
        fl.addRow("Absorption:", self._abs)
        fl.addRow("Transmittance:", self._trn)
        fl.addRow("Reflection:", self._mode)
        fl.addRow("Haze (deg):", self._haze)
        fl.addRow("Refractive Index:", self._ri)
        fl.addRow("Color:", self._color_btn)
        self._mat = None
        self._loading = False
        self._color = (0.55, 0.65, 1.0)
        for w in (self._ref, self._abs, self._trn, self._haze, self._ri):
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
            QSignalBlocker(self._haze),
            QSignalBlocker(self._ri),
        ]
        self._name.setText(mat.name)
        self._type.setCurrentIndex(["reflector", "absorber", "diffuser"].index(mat.surface_type))
        self._ref.setValue(mat.reflectance)
        self._abs.setValue(mat.absorption)
        self._trn.setValue(mat.transmittance)
        self._mode.setCurrentIndex(0 if mat.is_diffuse else 1)
        self._haze.setValue(mat.haze)
        self._ri.setValue(mat.refractive_index)
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
        name = self._name.text().strip()
        if not name:
            return
        self._mat.name = name
        self._mat.surface_type = self._type.currentText()
        self._mat.reflectance = self._ref.value()
        self._mat.absorption = self._abs.value()
        self._mat.transmittance = self._trn.value()
        self._mat.is_diffuse = self._mode.currentIndex() == 0
        self._mat.haze = self._haze.value()
        self._mat.refractive_index = self._ri.value()
        self._mat.color = self._color
        self.changed.emit()


class OpticalPropertiesForm(QWidget):
    """Editor for OpticalProperties (per-surface optical behavior)."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
        self._type = QComboBox()
        self._type.addItems(["reflector", "absorber", "diffuser"])
        self._ref = _dspin(0, 1, 3, 0.9, 0.01)
        self._abs = _dspin(0, 1, 3, 0.1, 0.01)
        self._trn = _dspin(0, 1, 3, 0.0, 0.01)
        self._mode = QComboBox()
        self._mode.addItems(["Diffuse (Lambertian)", "Specular"])
        self._haze = _dspin(0, 90, 1, 0.0, 1.0)
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        fl.addRow(QLabel("<b>Optical Properties</b>"))
        fl.addRow("Name:", self._name)
        fl.addRow("Surface type:", self._type)
        fl.addRow("Reflectance:", self._ref)
        fl.addRow("Absorption:", self._abs)
        fl.addRow("Transmittance:", self._trn)
        fl.addRow("Reflection:", self._mode)
        fl.addRow("Haze (deg):", self._haze)
        fl.addRow("Color:", self._color_btn)
        self._op = None
        self._loading = False
        self._color = (0.55, 0.65, 1.0)
        for w in (self._ref, self._abs, self._trn, self._haze):
            w.valueChanged.connect(self._apply)
        self._type.currentIndexChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        self._update_color_button()

    def load(self, op):
        self._loading = True
        self._op = op
        blockers = [QSignalBlocker(w) for w in (
            self._name, self._type, self._ref, self._abs, self._trn, self._mode, self._haze)]
        self._name.setText(op.name)
        self._type.setCurrentIndex(["reflector", "absorber", "diffuser"].index(op.surface_type))
        self._ref.setValue(op.reflectance)
        self._abs.setValue(op.absorption)
        self._trn.setValue(op.transmittance)
        self._mode.setCurrentIndex(0 if op.is_diffuse else 1)
        self._haze.setValue(op.haze)
        self._color = tuple(op.color)
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
        if self._op is None:
            return
        start = QColor.fromRgbF(self._color[0], self._color[1], self._color[2])
        picked = QColorDialog.getColor(start, self, "Choose Color")
        if not picked.isValid():
            return
        self._color = (picked.redF(), picked.greenF(), picked.blueF())
        self._update_color_button()
        self._apply()

    def _apply(self):
        if self._op is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        self._op.name = name
        self._op.surface_type = self._type.currentText()
        self._op.reflectance = self._ref.value()
        self._op.absorption = self._abs.value()
        self._op.transmittance = self._trn.value()
        self._op.is_diffuse = self._mode.currentIndex() == 0
        self._op.haze = self._haze.value()
        self._op.color = self._color
        self.changed.emit()


class DetectorForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
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
        name = self._name.text().strip()
        if not name:
            return
        self._det.name = name
        self._det.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._det.size = (self._sw.value(), self._sh.value())
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        self._det.u_axis = u.copy()
        self._det.v_axis = v.copy()
        self._det.resolution = (self._rx_res.value(), self._ry_res.value())
        self.changed.emit()


class SphereDetectorForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin(val=0.0)
        self._radius = _dspin(0.1, 9999, 2, 10.0, 1.0)
        self._n_phi = QSpinBox()
        self._n_phi.setRange(8, 360)
        self._n_phi.setValue(72)
        self._n_theta = QSpinBox()
        self._n_theta.setRange(4, 180)
        self._n_theta.setValue(36)
        fl.addRow(QLabel("<b>Sphere Detector</b>"))
        fl.addRow("Name:", self._name)
        fl.addRow("Center X:", self._cx)
        fl.addRow("Center Y:", self._cy)
        fl.addRow("Center Z:", self._cz)
        fl.addRow("Radius:", self._radius)
        fl.addRow("Phi bins:", self._n_phi)
        fl.addRow("Theta bins:", self._n_theta)
        self._det = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._radius):
            w.valueChanged.connect(self._apply)
        self._n_phi.valueChanged.connect(self._apply)
        self._n_theta.valueChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, det: SphereDetector):
        self._loading = True
        self._det = det
        blockers = [QSignalBlocker(w) for w in (
            self._name, self._cx, self._cy, self._cz, self._radius, self._n_phi, self._n_theta)]
        self._name.setText(det.name)
        self._cx.setValue(det.center[0])
        self._cy.setValue(det.center[1])
        self._cz.setValue(det.center[2])
        self._radius.setValue(det.radius)
        self._n_phi.setValue(det.resolution[0])
        self._n_theta.setValue(det.resolution[1])
        self._loading = False
        del blockers

    def _apply(self):
        if self._det is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        self._det.name = name
        self._det.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._det.radius = self._radius.value()
        self._det.resolution = (self._n_phi.value(), self._n_theta.value())
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
        self._flux_unit = QComboBox()
        self._flux_unit.addItems(["lm", "mW", "W"])
        self._angle_unit = QComboBox()
        self._angle_unit.addItems(["deg", "rad"])
        self._mp = QCheckBox("Enable multiprocessing")
        self._mp.setToolTip("Parallelize across sources (no ray path recording)")
        fl.addRow("Rays per source:", self._rays)
        fl.addRow("Max bounces:", self._bounce)
        fl.addRow("Energy threshold:", self._thresh)
        fl.addRow("Random seed:", self._seed)
        fl.addRow("Record ray paths:", self._rec)
        fl.addRow("Distance unit:", self._unit)
        fl.addRow("Flux unit:", self._flux_unit)
        fl.addRow("Angle unit:", self._angle_unit)
        fl.addRow("", self._mp)
        self._s = None
        self._loading = False
        self._rays.valueChanged.connect(self._apply)
        self._bounce.valueChanged.connect(self._apply)
        self._thresh.valueChanged.connect(self._apply)
        self._seed.valueChanged.connect(self._apply)
        self._rec.valueChanged.connect(self._apply)
        self._unit.currentIndexChanged.connect(self._apply)
        self._flux_unit.currentIndexChanged.connect(self._apply)
        self._angle_unit.currentIndexChanged.connect(self._apply)
        self._mp.toggled.connect(self._apply)

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
            QSignalBlocker(self._flux_unit),
            QSignalBlocker(self._angle_unit),
            QSignalBlocker(self._mp),
        ]
        self._rays.setValue(s.rays_per_source)
        self._bounce.setValue(s.max_bounces)
        self._thresh.setValue(s.energy_threshold)
        self._seed.setValue(s.random_seed)
        self._rec.setValue(s.record_ray_paths)
        idx = self._unit.findText(s.distance_unit)
        if idx >= 0:
            self._unit.setCurrentIndex(idx)
        idx = self._flux_unit.findText(s.flux_unit)
        if idx >= 0:
            self._flux_unit.setCurrentIndex(idx)
        idx = self._angle_unit.findText(s.angle_unit)
        if idx >= 0:
            self._angle_unit.setCurrentIndex(idx)
        self._mp.setChecked(s.use_multiprocessing)
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
        self._s.flux_unit = self._flux_unit.currentText()
        self._s.angle_unit = self._angle_unit.currentText()
        self._s.use_multiprocessing = self._mp.isChecked()
        self.changed.emit()


class BatchForm(QWidget):
    """Batch-edit form for multiple selected objects of the same type."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._header = QLabel("Batch Edit")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        fl.addRow(self._header)

        # Source batch fields
        self._flux = _dspin(0, 1e7, 1, 100.0, 10.0)
        self._dist = QComboBox()
        self._dist.addItems(["isotropic", "lambertian"])
        self._enabled = QCheckBox()
        self._enabled.setChecked(True)
        self._tolerance = _dspin(0, 100, 1, 0.0, 1.0)
        self._thermal = _dspin(0, 1, 3, 1.0, 0.01)
        self._src_widgets = []
        for label, w in [
            ("Flux:", self._flux),
            ("Distribution:", self._dist),
            ("Enabled:", self._enabled),
            ("Flux tolerance ±%:", self._tolerance),
            ("Thermal derate:", self._thermal),
        ]:
            fl.addRow(label, w)
            self._src_widgets.extend([fl.itemAt(fl.count() - 1), fl.itemAt(fl.count() - 2)])

        # Surface batch fields
        self._mat = QComboBox()
        fl.addRow("Material:", self._mat)

        self._apply_btn = QPushButton("Apply to All Selected")
        self._apply_btn.clicked.connect(self._apply)
        fl.addRow("", self._apply_btn)

        self._objects = []
        self._group = ""
        self._loading = False

    def load(self, group: str, objects: list, distribution_names=None, mat_names=None):
        self._loading = True
        self._group = group
        self._objects = objects
        self._header.setText(f"Batch Edit — {len(objects)} {group}")

        # Show/hide relevant fields
        is_src = group == "Sources"
        is_surf = group == "Surfaces"
        self._flux.setVisible(is_src)
        self._dist.setVisible(is_src)
        self._enabled.setVisible(is_src)
        self._tolerance.setVisible(is_src)
        self._thermal.setVisible(is_src)
        self._mat.setVisible(is_surf)

        if is_src and distribution_names:
            base = ["isotropic", "lambertian"]
            extra = [n for n in distribution_names if n not in base]
            self._dist.clear()
            self._dist.addItems(base + extra)

        if is_surf and mat_names:
            self._mat.clear()
            self._mat.addItems(mat_names)

        self._loading = False

    def _apply(self):
        if not self._objects or self._loading:
            return
        if self._group == "Sources":
            for src in self._objects:
                src.flux = self._flux.value()
                src.distribution = self._dist.currentText()
                src.enabled = self._enabled.isChecked()
                src.flux_tolerance = self._tolerance.value()
                src.thermal_derate = self._thermal.value()
        elif self._group == "Surfaces":
            mat = self._mat.currentText()
            if mat:
                for surf in self._objects:
                    surf.material_name = mat
        self.changed.emit()


class SolidBoxForm(QWidget):
    """Property editor for a SolidBox (box-level properties)."""

    changed = Signal()

    def __init__(self):
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        super().__init__()
        fl = QFormLayout(self)
        fl.addRow(QLabel("<b>Solid Box</b>"))

        self._name = _name_edit()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        self._dw = _dspin(0.1, 9999, 2, 50.0)
        self._dh = _dspin(0.1, 9999, 2, 30.0)
        self._dd = _dspin(0.1, 9999, 2, 3.0)
        self._mat = QComboBox()

        fl.addRow("Name:", self._name)
        fl.addRow("Center X:", self._cx)
        fl.addRow("Center Y:", self._cy)
        fl.addRow("Center Z:", self._cz)
        fl.addRow("Width (X):", self._dw)
        fl.addRow("Height (Y):", self._dh)
        fl.addRow("Depth (Z):", self._dd)
        fl.addRow("Material:", self._mat)

        # Coupling edges checkboxes
        fl.addRow(QLabel("Coupling edges:"))
        self._edge_checks: dict[str, QCheckBox] = {}
        for edge_id in ("left", "right", "front", "back"):
            cb = QCheckBox(edge_id)
            fl.addRow("", cb)
            self._edge_checks[edge_id] = cb

        self._box: SolidBox | None = None
        self._loading = False

        for w in (self._cx, self._cy, self._cz, self._dw, self._dh, self._dd):
            w.valueChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        for cb in self._edge_checks.values():
            cb.toggled.connect(self._apply)

    def load(self, box: SolidBox, mat_names: list[str]):
        self._loading = True
        self._box = box
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._cx), QSignalBlocker(self._cy), QSignalBlocker(self._cz),
            QSignalBlocker(self._dw), QSignalBlocker(self._dh), QSignalBlocker(self._dd),
            QSignalBlocker(self._mat),
        ] + [QSignalBlocker(cb) for cb in self._edge_checks.values()]
        self._name.setText(box.name)
        self._cx.setValue(float(box.center[0]))
        self._cy.setValue(float(box.center[1]))
        self._cz.setValue(float(box.center[2]))
        self._dw.setValue(float(box.dimensions[0]))
        self._dh.setValue(float(box.dimensions[1]))
        self._dd.setValue(float(box.dimensions[2]))
        self._mat.clear()
        self._mat.addItems(mat_names)
        midx = self._mat.findText(box.material_name)
        if midx >= 0:
            self._mat.setCurrentIndex(midx)
        for edge_id, cb in self._edge_checks.items():
            cb.setChecked(edge_id in box.coupling_edges)
        self._loading = False
        del blockers

    def _apply(self):
        if self._box is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        self._box.name = name
        self._box.center = np.array([self._cx.value(), self._cy.value(), self._cz.value()])
        self._box.dimensions = (self._dw.value(), self._dh.value(), self._dd.value())
        if self._mat.currentText():
            self._box.material_name = self._mat.currentText()
        self._box.coupling_edges = [eid for eid, cb in self._edge_checks.items() if cb.isChecked()]
        self.changed.emit()


class FaceForm(QWidget):
    """Property editor for a single face of a SolidBox."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        fl.addRow(QLabel("<b>Solid Box Face</b>"))

        self._face_lbl = QLabel("—")
        self._face_lbl.setStyleSheet("font-weight: bold;")
        fl.addRow("Face:", self._face_lbl)

        self._opt_prop = QComboBox()
        self._opt_prop.setToolTip(
            "Assign optical properties override to this face.\n"
            "Leave blank to use the box's bulk material.")
        fl.addRow("Optical Props:", self._opt_prop)

        self._box: SolidBox | None = None
        self._face_id: str = ""
        self._loading = False
        self._opt_prop.currentIndexChanged.connect(self._apply)

    def load(self, box: SolidBox, face_id: str, opt_prop_names: list[str]):
        self._loading = True
        self._box = box
        self._face_id = face_id
        blockers = [QSignalBlocker(self._opt_prop)]
        self._face_lbl.setText(face_id)
        self._opt_prop.clear()
        self._opt_prop.addItem("(use bulk material)")
        self._opt_prop.addItems(opt_prop_names)
        current_op = box.face_optics.get(face_id, "")
        if current_op:
            idx = self._opt_prop.findText(current_op)
            if idx >= 0:
                self._opt_prop.setCurrentIndex(idx)
        self._loading = False
        del blockers

    def _apply(self):
        if self._box is None or self._loading:
            return
        selected = self._opt_prop.currentText()
        if selected == "(use bulk material)" or not selected:
            self._box.face_optics.pop(self._face_id, None)
        else:
            self._box.face_optics[self._face_id] = selected
        self.changed.emit()
