"""Right-panel property editor for selected scene objects."""

from __future__ import annotations

import csv

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.gui.widgets.collapsible_section import CollapsibleSection
from backlight_sim.gui.theme import TEXT_MUTED

from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.solid_body import SolidBox, SolidCylinder, SolidPrism, FACE_NAMES
from backlight_sim.gui.commands import SetPropertyCommand


def _vals_equal(a, b):
    """Compare values, handling numpy arrays."""
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        try:
            return np.array_equal(a, b)
        except TypeError:
            return False
    return a == b


def _push_or_apply_changes(obj, changes, push_cmd_fn, begin_macro_fn,
                           end_macro_fn, undo_stack, refresh_fn, changed_signal):
    """Apply attribute changes via undo commands or direct mutation.

    Parameters
    ----------
    obj : object with settable attributes
    changes : list of (attr_name, new_value) pairs
    push_cmd_fn : callable(QUndoCommand) or None — pushes with flag guard
    begin_macro_fn / end_macro_fn : callable for macro grouping
    undo_stack : QUndoStack (used for pushes inside macros)
    refresh_fn : callback for commands
    changed_signal : Signal to emit when using direct-mutation path
    """
    if push_cmd_fn is not None:
        pending = []
        for attr, new_val in changes:
            old_val = getattr(obj, attr)
            if not _vals_equal(old_val, new_val):
                pending.append((attr, old_val, new_val))
        if not pending:
            return
        if len(pending) == 1:
            attr, old_val, new_val = pending[0]
            push_cmd_fn(SetPropertyCommand(obj, attr, old_val, new_val, refresh_fn))
        else:
            begin_macro_fn(f"Edit {getattr(obj, 'name', '?')}")
            for attr, old_val, new_val in pending:
                undo_stack.push(SetPropertyCommand(obj, attr, old_val, new_val, refresh_fn))
            end_macro_fn()
    else:
        for attr, new_val in changes:
            setattr(obj, attr, new_val)
        changed_signal.emit()


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
        self.setMinimumWidth(320)

        empty = QLabel("Select an object to edit")
        empty.setStyleSheet(f"color: {TEXT_MUTED}; padding: 8px;")
        self.addWidget(empty)

        for form_cls in (SourceForm, SurfaceForm, MaterialForm, OpticalPropertiesForm,
                         DetectorForm, SphereDetectorForm, SettingsForm, BatchForm,
                         SolidBoxForm, FaceForm, SolidCylinderForm, SolidPrismForm):
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

    def show_material(self, mat, project=None):
        self._finalize_active_editor()
        self._materialform.load(mat, project=project)
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

    def show_optical_properties(self, op, bsdf_names: list[str] | None = None):
        self._finalize_active_editor()
        self._opticalpropertiesform.load(op, bsdf_names=bsdf_names)
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

    def show_solid_cylinder(self, cyl: "SolidCylinder", mat_names: list[str]):
        self._finalize_active_editor()
        self._solidcylinderform.load(cyl, mat_names)
        self.setCurrentWidget(self._solidcylinderform)

    def show_solid_prism(self, prism: "SolidPrism", mat_names: list[str]):
        self._finalize_active_editor()
        self._solidprismform.load(prism, mat_names)
        self.setCurrentWidget(self._solidprismform)

    def set_undo_stack(self, undo_stack, push_fn, begin_macro_fn, end_macro_fn, refresh_fn):
        """Wire undo infrastructure into all forms."""
        forms = [
            self._sourceform, self._surfaceform, self._materialform,
            self._opticalpropertiesform, self._detectorform, self._spheredetectorform,
            self._settingsform, self._solidboxform, self._faceform,
            self._solidcylinderform, self._solidprismform,
            self._batchform,
        ]
        for form in forms:
            form._push_command = push_fn
            form._begin_macro = begin_macro_fn
            form._end_macro = end_macro_fn
            form._undo_stack = undo_stack
            form._undo_refresh = refresh_fn

    def clear_selection(self):
        self._finalize_active_editor()
        self.setCurrentIndex(0)


class SourceForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section (name + enabled) ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._enabled = QCheckBox()
        self._enabled.setChecked(True)
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Enabled:", self._enabled)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._px = _dspin()
        self._py = _dspin()
        self._pz = _dspin()
        fl_pos.addRow("X:", self._px)
        fl_pos.addRow("Y:", self._py)
        fl_pos.addRow("Z:", self._pz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Emission section (flux, distribution, peak cd) ----
        sec_emission = CollapsibleSection("Emission", collapsed=False)
        fl_emission = QFormLayout()
        self._flux = _dspin(0, 1e7, 1, 100.0, 10.0)
        fl_emission.addRow("Flux:", self._flux)

        # Peak intensity helper (read/convert)
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
        self._peak_lbl = QLabel("")
        self._peak_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        fl_emission.addRow("Peak cd:", peak_row)

        self._dist = QComboBox()
        self._dist.addItems(["isotropic", "lambertian"])
        fl_emission.addRow("Distribution:", self._dist)
        sec_emission.addLayout(fl_emission)
        vbox.addWidget(sec_emission)

        # ---- Thermal / Binning section (collapsed by default) ----
        sec_thermal = CollapsibleSection("Thermal / Binning", collapsed=True)
        fl_thermal = QFormLayout()
        self._tolerance = _dspin(0, 100, 1, 0.0, 1.0)
        self._tolerance.setToolTip("LED flux bin tolerance ±% (0 = exact)")
        fl_thermal.addRow("Flux tolerance ±%:", self._tolerance)
        self._current = _dspin(0, 1e5, 1, 0.0, 1.0)
        self._current.setToolTip("Drive current in mA (0 = use flux directly)")
        fl_thermal.addRow("Current (mA):", self._current)
        self._flux_per_mA = _dspin(0, 1e5, 4, 0.0, 0.01)
        self._flux_per_mA.setToolTip("Flux per mA (lm/mA). When >0, flux = current × flux_per_mA")
        fl_thermal.addRow("Flux/mA:", self._flux_per_mA)
        self._thermal = _dspin(0, 1, 3, 1.0, 0.01)
        self._thermal.setToolTip("Thermal derating factor 0–1 (1 = no derating)")
        fl_thermal.addRow("Thermal derate:", self._thermal)

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
        fl_thermal.addRow("LED Color:", color_row)

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
        fl_thermal.addRow("SPD:", self._spd)
        sec_thermal.addLayout(fl_thermal)
        vbox.addWidget(sec_thermal)

        # Phase 5 — Position Tolerance
        sec_pos_tol = CollapsibleSection("Position Tolerance", collapsed=True)
        fl_pos_tol = QFormLayout()
        self._pos_sigma = _dspin(0, 100, 3, 0.0, 0.001)
        self._pos_sigma.setToolTip(
            "Per-source position jitter σ in mm (Gaussian, standard deviation).\n"
            "0 = use project-level default from Simulation Settings.\n"
            "Example: σ = 0.15 mm means ±0.15 mm (1σ) placement error."
        )
        fl_pos_tol.addRow("Position σ (mm):", self._pos_sigma)
        sec_pos_tol.addLayout(fl_pos_tol)
        vbox.addWidget(sec_pos_tol)
        vbox.addStretch()

        self._src = None
        self._loading = False
        for w in (self._px, self._py, self._pz, self._flux, self._tolerance,
                  self._current, self._flux_per_mA, self._thermal,
                  self._cr, self._cg, self._cb, self._pos_sigma):
            w.valueChanged.connect(self._apply)
        self._dist.currentIndexChanged.connect(self._apply)
        self._spd.currentTextChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        self._enabled.toggled.connect(self._apply)

        # Explicit tab order for keyboard navigation
        self.setTabOrder(self._name, self._enabled)
        self.setTabOrder(self._enabled, self._px)
        self.setTabOrder(self._px, self._py)
        self.setTabOrder(self._py, self._pz)
        self.setTabOrder(self._pz, self._flux)
        self.setTabOrder(self._flux, self._dist)
        self.setTabOrder(self._dist, self._tolerance)
        self.setTabOrder(self._tolerance, self._current)
        self.setTabOrder(self._current, self._flux_per_mA)
        self.setTabOrder(self._flux_per_mA, self._thermal)

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
            QSignalBlocker(self._pos_sigma),
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
        self._pos_sigma.setValue(getattr(src, 'position_sigma_mm', 0.0))
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
        return flux / (np.pi if "lambertian" in dist else 4 * np.pi)

    def _peak_to_flux(self, peak: float, dist: str) -> float:
        return peak * (np.pi if "lambertian" in dist else 4 * np.pi)

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
        changes = [('flux', flux), ('distribution', dist)]
        _push_or_apply_changes(self._src, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)

    # ──────────────────────────────────────────────────────────────────

    def _apply(self):
        if self._src is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        changes = [
            ('name', name),
            ('enabled', self._enabled.isChecked()),
            ('position', np.array([self._px.value(), self._py.value(), self._pz.value()])),
            ('flux', self._flux.value()),
            ('distribution', self._dist.currentText()),
            ('flux_tolerance', self._tolerance.value()),
            ('position_sigma_mm', self._pos_sigma.value()),
            ('current_mA', self._current.value()),
            ('flux_per_mA', self._flux_per_mA.value()),
            ('thermal_derate', self._thermal.value()),
            ('color_rgb', (self._cr.value(), self._cg.value(), self._cb.value())),
            ('spd', self._spd.currentText()),
        ]
        _push_or_apply_changes(self._src, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)
        self._update_peak_display()


class SurfaceForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._mat = QComboBox()
        self._opt_prop = QComboBox()
        self._opt_prop.setToolTip("Override material's optical behavior with specific optical properties")
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Material:", self._mat)
        fl_identity.addRow("Optical Props:", self._opt_prop)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        fl_pos.addRow("Center X:", self._cx)
        fl_pos.addRow("Center Y:", self._cy)
        fl_pos.addRow("Center Z:", self._cz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Orientation section ----
        sec_orient = CollapsibleSection("Orientation", collapsed=False)
        fl_orient = QFormLayout()
        self._face = QComboBox()
        self._face.addItems(["+X face", "-X face", "+Y face", "-Y face", "+Z face", "-Z face"])
        self._rx = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._ry = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._rz = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._normal_lbl = QLabel("normal: ?")
        self._normal_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        fl_orient.addRow("Face direction:", self._face)
        fl_orient.addRow("Rotate X (deg):", self._rx)
        fl_orient.addRow("Rotate Y (deg):", self._ry)
        fl_orient.addRow("Rotate Z (deg):", self._rz)
        fl_orient.addRow("", self._normal_lbl)
        sec_orient.addLayout(fl_orient)
        vbox.addWidget(sec_orient)

        # ---- Size section ----
        sec_size = CollapsibleSection("Size", collapsed=False)
        fl_size = QFormLayout()
        self._sw = _dspin(0.01, 9999, 2, 10.0)
        self._sh = _dspin(0.01, 9999, 2, 10.0)
        fl_size.addRow("Width:", self._sw)
        fl_size.addRow("Height:", self._sh)
        sec_size.addLayout(fl_size)
        vbox.addWidget(sec_size)
        vbox.addStretch()

        self._surf = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._sw, self._sh, self._rx, self._ry, self._rz):
            w.valueChanged.connect(self._apply)
        self._face.currentIndexChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._opt_prop.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

        # Explicit tab order for keyboard navigation
        self.setTabOrder(self._name, self._mat)
        self.setTabOrder(self._mat, self._opt_prop)
        self.setTabOrder(self._opt_prop, self._cx)
        self.setTabOrder(self._cx, self._cy)
        self.setTabOrder(self._cy, self._cz)
        self.setTabOrder(self._cz, self._face)
        self.setTabOrder(self._face, self._rx)
        self.setTabOrder(self._rx, self._ry)
        self.setTabOrder(self._ry, self._rz)
        self.setTabOrder(self._rz, self._sw)
        self.setTabOrder(self._sw, self._sh)

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
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        op_text = self._opt_prop.currentText()
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('size', (self._sw.value(), self._sh.value())),
            ('u_axis', u.copy()),
            ('v_axis', v.copy()),
            ('optical_properties_name', "" if op_text == "(none)" else op_text),
        ]
        if self._mat.currentText():
            changes.append(('material_name', self._mat.currentText()))
        _push_or_apply_changes(self._surf, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)
        n = self._surf.normal
        self._normal_lbl.setText(f"normal: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")


class MaterialForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Wrap everything in a scroll area so the form + spectral section fit
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(2)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._type = QComboBox()
        self._type.addItems(["reflector", "absorber", "diffuser"])
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Type:", self._type)
        sec_identity.addLayout(fl_identity)
        scroll_layout.addWidget(sec_identity)

        # ---- Optical section ----
        sec_optical = CollapsibleSection("Optical", collapsed=False)
        fl_optical = QFormLayout()
        self._ref = _dspin(0, 1, 3, 0.9, 0.01)
        self._abs = _dspin(0, 1, 3, 0.1, 0.01)
        self._trn = _dspin(0, 1, 3, 0.0, 0.01)
        self._mode = QComboBox()
        self._mode.addItems(["Diffuse (Lambertian)", "Specular"])
        self._haze = _dspin(0, 90, 1, 0.0, 1.0)
        self._haze.setToolTip("Haze / scatter half-angle in degrees (specular only, 0 = perfect mirror)")
        self._ri = _dspin(0.1, 10.0, 3, 1.0, 0.01)
        self._ri.setToolTip("Index of refraction (1.0 = air, 1.5 = glass, 2.4 = diamond)")
        fl_optical.addRow("Reflectance:", self._ref)
        fl_optical.addRow("Absorption:", self._abs)
        fl_optical.addRow("Transmittance:", self._trn)
        fl_optical.addRow("Reflection:", self._mode)
        fl_optical.addRow("Haze (deg):", self._haze)
        fl_optical.addRow("Refractive Index:", self._ri)
        sec_optical.addLayout(fl_optical)
        scroll_layout.addWidget(sec_optical)

        # ---- Visual section (color, collapsed by default) ----
        sec_visual = CollapsibleSection("Visual", collapsed=True)
        fl_visual = QFormLayout()
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        fl_visual.addRow("Color:", self._color_btn)
        sec_visual.addLayout(fl_visual)
        scroll_layout.addWidget(sec_visual)

        # ---- Spectral R/T section (collapsed by default) ----
        self._spec_group = QGroupBox("Spectral R/T")
        self._spec_group.setCheckable(True)
        self._spec_group.setChecked(False)
        spec_layout = QVBoxLayout(self._spec_group)

        spec_btns = QHBoxLayout()
        self._spec_import_btn = QPushButton("Import CSV")
        self._spec_import_btn.clicked.connect(self._import_spectral)
        self._spec_export_btn = QPushButton("Export CSV")
        self._spec_export_btn.clicked.connect(self._export_spectral)
        self._spec_clear_btn = QPushButton("Clear")
        self._spec_clear_btn.clicked.connect(self._clear_spectral)
        for btn in (self._spec_import_btn, self._spec_export_btn, self._spec_clear_btn):
            spec_btns.addWidget(btn)
        spec_btns.addStretch()
        spec_layout.addLayout(spec_btns)

        self._spec_table = QTableWidget(0, 3)
        self._spec_table.setHorizontalHeaderLabels(["wavelength_nm", "reflectance", "transmittance"])
        self._spec_table.horizontalHeader().setStretchLastSection(True)
        self._spec_table.verticalHeader().setVisible(False)
        self._spec_table.setMaximumHeight(150)
        self._spec_table.cellChanged.connect(self._on_spec_table_edited)
        spec_layout.addWidget(self._spec_table)

        self._spec_plot = pg.PlotWidget()
        self._spec_plot.setLabel("bottom", "Wavelength (nm)")
        self._spec_plot.setLabel("left", "Value")
        self._spec_plot.setTitle("R/T")
        self._spec_plot.showGrid(x=True, y=True, alpha=0.25)
        self._spec_plot.addLegend()
        self._spec_plot.setMaximumHeight(140)
        spec_layout.addWidget(self._spec_plot)

        scroll_layout.addWidget(self._spec_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

        self._mat = None
        self._project = None
        self._loading = False
        self._loading_spec_table = False
        self._color = (0.55, 0.65, 1.0)
        for w in (self._ref, self._abs, self._trn, self._haze, self._ri):
            w.valueChanged.connect(self._apply)
        self._type.currentIndexChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)
        self._update_color_button()

    def load(self, mat, project=None):
        self._loading = True
        self._mat = mat
        self._project = project
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
        # Load spectral R/T data
        self._load_spectral_data()

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
        changes = [
            ('name', name),
            ('surface_type', self._type.currentText()),
            ('reflectance', self._ref.value()),
            ('absorption', self._abs.value()),
            ('transmittance', self._trn.value()),
            ('is_diffuse', self._mode.currentIndex() == 0),
            ('haze', self._haze.value()),
            ('refractive_index', self._ri.value()),
            ('color', self._color),
        ]
        _push_or_apply_changes(self._mat, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)

    # ------------------------------------------------------------------
    # Spectral R/T editor
    # ------------------------------------------------------------------

    def _load_spectral_data(self):
        """Load spectral R/T data from project into table and plot."""
        self._loading_spec_table = True
        self._spec_table.setRowCount(0)
        self._spec_plot.clear()
        if self._project is None or self._mat is None:
            self._spec_group.setChecked(False)
            self._loading_spec_table = False
            return
        entry = self._project.spectral_material_data.get(self._mat.name)
        if entry:
            lam = np.asarray(entry.get("wavelength_nm", []), dtype=float)
            R = np.asarray(entry.get("reflectance", []), dtype=float)
            T = np.asarray(entry.get("transmittance", []), dtype=float)
            self._spec_group.setChecked(True)
            self._fill_spec_table(lam, R, T)
            self._plot_spec(lam, R, T)
        else:
            self._spec_group.setChecked(False)
        self._loading_spec_table = False

    def _fill_spec_table(self, lam: np.ndarray, R: np.ndarray, T: np.ndarray):
        self._loading_spec_table = True
        self._spec_table.setRowCount(0)
        for i in range(len(lam)):
            row = self._spec_table.rowCount()
            self._spec_table.insertRow(row)
            rv = float(R[i]) if i < len(R) else 0.0
            tv = float(T[i]) if i < len(T) else 0.0
            self._spec_table.setItem(row, 0, QTableWidgetItem(f"{float(lam[i]):.4g}"))
            self._spec_table.setItem(row, 1, QTableWidgetItem(f"{rv:.6g}"))
            self._spec_table.setItem(row, 2, QTableWidgetItem(f"{tv:.6g}"))
        self._loading_spec_table = False

    def _plot_spec(self, lam: np.ndarray, R: np.ndarray, T: np.ndarray):
        self._spec_plot.clear()
        if len(lam) == 0:
            return
        self._spec_plot.plot(lam, R, pen=pg.mkPen((80, 160, 255), width=2), name="R(λ)")
        self._spec_plot.plot(lam, T, pen=pg.mkPen((80, 255, 120), width=2), name="T(λ)")

    def _on_spec_table_edited(self, row: int, col: int):
        if self._loading_spec_table or self._project is None or self._mat is None:
            return
        lam, R, T = self._read_spec_table()
        if lam is None:
            return
        self._project.spectral_material_data[self._mat.name] = {
            "wavelength_nm": lam.tolist(),
            "reflectance": R.tolist(),
            "transmittance": T.tolist(),
        }
        self._plot_spec(lam, R, T)
        self.changed.emit()

    def _read_spec_table(self):
        lam, R, T = [], [], []
        for row in range(self._spec_table.rowCount()):
            wi = self._spec_table.item(row, 0)
            ri = self._spec_table.item(row, 1)
            ti = self._spec_table.item(row, 2)
            if wi is None:
                continue
            try:
                lam.append(float(wi.text()))
                R.append(float(ri.text()) if ri is not None else 0.0)
                T.append(float(ti.text()) if ti is not None else 0.0)
            except ValueError:
                continue
        if len(lam) < 1:
            return None, None, None
        return np.array(lam, dtype=float), np.array(R, dtype=float), np.array(T, dtype=float)

    def _import_spectral(self):
        if self._project is None or self._mat is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Spectral R/T CSV", "",
            "CSV files (*.csv *.txt);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r and not r[0].startswith("#")]
            start = 0
            try:
                float(rows[0][0])
            except (ValueError, IndexError):
                start = 1
            data = []
            for r in rows[start:]:
                if not r:
                    continue
                try:
                    vals = [float(v) for v in r[:3]]
                    data.append(vals)
                except ValueError:
                    continue
            if not data:
                raise ValueError("No numeric rows found.")
            data = np.array(data, dtype=float)
            lam = data[:, 0]
            R = data[:, 1] if data.shape[1] > 1 else np.zeros_like(lam)
            T = data[:, 2] if data.shape[1] > 2 else np.zeros_like(lam)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        self._project.spectral_material_data[self._mat.name] = {
            "wavelength_nm": lam.tolist(),
            "reflectance": R.tolist(),
            "transmittance": T.tolist(),
        }
        self._fill_spec_table(lam, R, T)
        self._plot_spec(lam, R, T)
        self._spec_group.setChecked(True)
        self.changed.emit()

    def _export_spectral(self):
        if self._project is None or self._mat is None:
            return
        entry = self._project.spectral_material_data.get(self._mat.name)
        if not entry:
            QMessageBox.information(self, "No Data", f"No spectral table for '{self._mat.name}'.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Spectral R/T CSV", f"{self._mat.name}_spectral.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        lam = np.asarray(entry.get("wavelength_nm", []), dtype=float)
        R = np.asarray(entry.get("reflectance", []), dtype=float)
        T = np.asarray(entry.get("transmittance", []), dtype=float)
        data = np.column_stack([lam, R, T])
        np.savetxt(
            path, data, delimiter=",",
            header="wavelength_nm,reflectance,transmittance", comments="",
        )

    def _clear_spectral(self):
        if self._project is None or self._mat is None:
            return
        self._project.spectral_material_data.pop(self._mat.name, None)
        self._spec_table.setRowCount(0)
        self._spec_plot.clear()
        self._spec_group.setChecked(False)
        self.changed.emit()


class OpticalPropertiesForm(QWidget):
    """Editor for OpticalProperties (per-surface optical behavior).

    Includes a BSDF profile dropdown: when a BSDF profile is selected,
    the manual reflectance/transmittance/mode/haze fields are greyed out.
    """

    changed = Signal()

    def __init__(self):
        super().__init__()
        fl = QFormLayout(self)
        self._name = _name_edit()
        self._type = QComboBox()
        self._type.addItems(["reflector", "absorber", "diffuser"])
        self._bsdf_combo = QComboBox()
        self._bsdf_combo.addItem("(None)")
        self._bsdf_combo.setToolTip(
            "Assign a BSDF profile to this optical property.\n"
            "When set, manual reflectance/transmittance fields are bypassed."
        )
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
        fl.addRow("BSDF profile:", self._bsdf_combo)
        fl.addRow("Reflectance:", self._ref)
        fl.addRow("Absorption:", self._abs)
        fl.addRow("Transmittance:", self._trn)
        fl.addRow("Reflection:", self._mode)
        fl.addRow("Haze (deg):", self._haze)
        fl.addRow("Color:", self._color_btn)
        self._op = None
        self._loading = False
        self._color = (0.55, 0.65, 1.0)
        # Manual fields list for grey-out logic
        self._manual_fields = [self._ref, self._abs, self._trn, self._mode, self._haze]
        for w in (self._ref, self._abs, self._trn, self._haze):
            w.valueChanged.connect(self._apply)
        self._type.currentIndexChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._apply)
        self._bsdf_combo.currentIndexChanged.connect(self._on_bsdf_changed)
        self._name.editingFinished.connect(self._apply)
        self._update_color_button()

    def refresh_bsdf_names(self, bsdf_names: list[str]):
        """Update the BSDF dropdown with profile names from the project."""
        self._loading = True
        blocker = QSignalBlocker(self._bsdf_combo)
        current = self._bsdf_combo.currentText()
        self._bsdf_combo.clear()
        self._bsdf_combo.addItem("(None)")
        for name in bsdf_names:
            self._bsdf_combo.addItem(name)
        # Restore selection
        idx = self._bsdf_combo.findText(current)
        if idx >= 0:
            self._bsdf_combo.setCurrentIndex(idx)
        self._loading = False
        del blocker

    def _on_bsdf_changed(self, _idx: int):
        if self._loading:
            return
        selected = self._bsdf_combo.currentText()
        bsdf_active = (selected != "(None)")
        for w in self._manual_fields:
            w.setEnabled(not bsdf_active)
        self._apply()

    def load(self, op, bsdf_names: list[str] | None = None):
        self._loading = True
        self._op = op
        blockers = [QSignalBlocker(w) for w in (
            self._name, self._type, self._ref, self._abs, self._trn,
            self._mode, self._haze, self._bsdf_combo)]
        self._name.setText(op.name)
        self._type.setCurrentIndex(["reflector", "absorber", "diffuser"].index(op.surface_type))
        self._ref.setValue(op.reflectance)
        self._abs.setValue(op.absorption)
        self._trn.setValue(op.transmittance)
        self._mode.setCurrentIndex(0 if op.is_diffuse else 1)
        self._haze.setValue(op.haze)
        self._color = tuple(op.color)
        self._update_color_button()
        # BSDF dropdown
        if bsdf_names is not None:
            self._bsdf_combo.clear()
            self._bsdf_combo.addItem("(None)")
            for name in bsdf_names:
                self._bsdf_combo.addItem(name)
        bsdf_name = getattr(op, "bsdf_profile_name", "")
        if bsdf_name:
            idx = self._bsdf_combo.findText(bsdf_name)
            if idx >= 0:
                self._bsdf_combo.setCurrentIndex(idx)
            else:
                self._bsdf_combo.setCurrentIndex(0)
        else:
            self._bsdf_combo.setCurrentIndex(0)
        bsdf_active = bsdf_name != ""
        for w in self._manual_fields:
            w.setEnabled(not bsdf_active)
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
        bsdf_text = self._bsdf_combo.currentText()
        changes = [
            ('name', name),
            ('surface_type', self._type.currentText()),
            ('reflectance', self._ref.value()),
            ('absorption', self._abs.value()),
            ('transmittance', self._trn.value()),
            ('is_diffuse', self._mode.currentIndex() == 0),
            ('haze', self._haze.value()),
            ('color', self._color),
            ('bsdf_profile_name', "" if bsdf_text == "(None)" else bsdf_text),
        ]
        _push_or_apply_changes(self._op, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


class DetectorForm(QWidget):
    changed = Signal()

    _FACE_KEYS = [(0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0), (2, 1.0), (2, -1.0)]

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        fl_identity.addRow("Name:", self._name)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin(val=5.0)
        fl_pos.addRow("Center X:", self._cx)
        fl_pos.addRow("Center Y:", self._cy)
        fl_pos.addRow("Center Z:", self._cz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Orientation section ----
        sec_orient = CollapsibleSection("Orientation", collapsed=False)
        fl_orient = QFormLayout()
        self._face = QComboBox()
        self._face.addItems(["+X face", "-X face", "+Y face", "-Y face", "+Z face", "-Z face"])
        self._face.setCurrentIndex(4)
        self._rx = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._ry = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        self._rz = _dspin(-180.0, 180.0, 2, 0.0, 1.0)
        fl_orient.addRow("Face direction:", self._face)
        fl_orient.addRow("Rotate X (deg):", self._rx)
        fl_orient.addRow("Rotate Y (deg):", self._ry)
        fl_orient.addRow("Rotate Z (deg):", self._rz)
        sec_orient.addLayout(fl_orient)
        vbox.addWidget(sec_orient)

        # ---- Size & Resolution section ----
        sec_size = CollapsibleSection("Size & Resolution", collapsed=False)
        fl_size = QFormLayout()
        self._sw = _dspin(0.01, 9999, 2, 10.0)
        self._sh = _dspin(0.01, 9999, 2, 10.0)
        self._rx_res = QSpinBox()
        self._rx_res.setRange(10, 2000)
        self._rx_res.setValue(100)
        self._ry_res = QSpinBox()
        self._ry_res.setRange(10, 2000)
        self._ry_res.setValue(100)
        fl_size.addRow("Width:", self._sw)
        fl_size.addRow("Height:", self._sh)
        fl_size.addRow("Resolution X:", self._rx_res)
        fl_size.addRow("Resolution Y:", self._ry_res)
        sec_size.addLayout(fl_size)
        vbox.addWidget(sec_size)
        vbox.addStretch()

        self._det = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._sw, self._sh, self._rx, self._ry, self._rz):
            w.valueChanged.connect(self._apply)
        self._face.currentIndexChanged.connect(self._apply)
        self._rx_res.valueChanged.connect(self._apply)
        self._ry_res.valueChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

        # Explicit tab order for keyboard navigation
        self.setTabOrder(self._name, self._cx)
        self.setTabOrder(self._cx, self._cy)
        self.setTabOrder(self._cy, self._cz)
        self.setTabOrder(self._cz, self._face)
        self.setTabOrder(self._face, self._rx)
        self.setTabOrder(self._rx, self._ry)
        self.setTabOrder(self._ry, self._rz)
        self.setTabOrder(self._rz, self._sw)
        self.setTabOrder(self._sw, self._sh)
        self.setTabOrder(self._sh, self._rx_res)
        self.setTabOrder(self._rx_res, self._ry_res)

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
        key = self._FACE_KEYS[self._face.currentIndex()]
        u, v = _axes_from_face_and_rotation(key, self._rx.value(), self._ry.value(), self._rz.value())
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('size', (self._sw.value(), self._sh.value())),
            ('u_axis', u.copy()),
            ('v_axis', v.copy()),
            ('resolution', (self._rx_res.value(), self._ry_res.value())),
        ]
        _push_or_apply_changes(self._det, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


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
        self._mode = QComboBox()
        self._mode.addItems(["near_field", "far_field"])
        self._mode.setToolTip(
            "near_field: bins by hit position on sphere\n"
            "far_field: bins by ray direction; produces candela distribution"
        )
        self._radius_label = QLabel("Radius:")
        fl.addRow(QLabel("<b>Sphere Detector</b>"))
        fl.addRow("Name:", self._name)
        fl.addRow("Center X:", self._cx)
        fl.addRow("Center Y:", self._cy)
        fl.addRow("Center Z:", self._cz)
        fl.addRow(self._radius_label, self._radius)
        fl.addRow("Phi bins:", self._n_phi)
        fl.addRow("Theta bins:", self._n_theta)
        fl.addRow("Mode:", self._mode)
        self._det = None
        self._loading = False
        for w in (self._cx, self._cy, self._cz, self._radius):
            w.valueChanged.connect(self._apply)
        self._n_phi.valueChanged.connect(self._apply)
        self._n_theta.valueChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._apply)
        self._mode.currentIndexChanged.connect(self._update_mode_visibility)
        self._name.editingFinished.connect(self._apply)

    def _update_mode_visibility(self):
        is_farfield = self._mode.currentText() == "far_field"
        self._radius_label.setVisible(not is_farfield)
        self._radius.setVisible(not is_farfield)

    def load(self, det: SphereDetector):
        self._loading = True
        self._det = det
        blockers = [QSignalBlocker(w) for w in (
            self._name, self._cx, self._cy, self._cz, self._radius,
            self._n_phi, self._n_theta, self._mode)]
        self._name.setText(det.name)
        self._cx.setValue(det.center[0])
        self._cy.setValue(det.center[1])
        self._cz.setValue(det.center[2])
        self._radius.setValue(det.radius)
        self._n_phi.setValue(det.resolution[0])
        self._n_theta.setValue(det.resolution[1])
        mode = getattr(det, "mode", "near_field")
        idx = self._mode.findText(mode)
        if idx >= 0:
            self._mode.setCurrentIndex(idx)
        self._loading = False
        del blockers
        self._update_mode_visibility()

    def _apply(self):
        if self._det is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('radius', self._radius.value()),
            ('resolution', (self._n_phi.value(), self._n_theta.value())),
            ('mode', self._mode.currentText()),
        ]
        _push_or_apply_changes(self._det, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


_QUALITY_PRESETS = {
    "Quick":    dict(rays=1_000,   bounces=20,  rec=50,  cv=5.0),
    "Standard": dict(rays=10_000,  bounces=50,  rec=200, cv=2.0),
    "High":     dict(rays=100_000, bounces=100, rec=500, cv=1.0),
}


class SettingsForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # Quality preset row (always visible, outside sections)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Quality:"))
        for name, vals in _QUALITY_PRESETS.items():
            btn = QPushButton(name)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _=False, v=vals: self._apply_preset(v))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        vbox.addLayout(preset_row)

        # ---- Ray Tracing section ----
        sec_rt = CollapsibleSection("Ray Tracing", collapsed=False)
        fl_rt = QFormLayout()
        self._rays = QSpinBox()
        self._rays.setRange(100, 10_000_000)
        self._rays.setValue(10_000)
        self._rays.setSingleStep(1000)
        self._bounce = QSpinBox()
        self._bounce.setRange(1, 500)
        self._bounce.setValue(50)
        self._thresh = _dspin(0, 1, 6, 0.001, 0.0001)
        fl_rt.addRow("Rays per source:", self._rays)
        fl_rt.addRow("Max bounces:", self._bounce)
        fl_rt.addRow("Energy threshold:", self._thresh)
        sec_rt.addLayout(fl_rt)
        vbox.addWidget(sec_rt)

        # ---- Convergence section (collapsed by default) ----
        sec_conv = CollapsibleSection("Convergence", collapsed=True)
        fl_conv = QFormLayout()
        self._adaptive = QCheckBox("Adaptive sampling")
        self._adaptive.setToolTip(
            "Stop ray generation per source when detector CV% drops below threshold"
        )
        self._adaptive.setChecked(True)
        self._cv_target = QDoubleSpinBox()
        self._cv_target.setRange(0.1, 20.0)
        self._cv_target.setSingleStep(0.5)
        self._cv_target.setDecimals(1)
        self._cv_target.setValue(2.0)
        self._cv_target.setSuffix(" %")
        self._cv_target.setToolTip(
            "Stop when detector CV (coefficient of variation) drops below this value"
        )
        self._check_interval = QSpinBox()
        self._check_interval.setRange(100, 100_000)
        self._check_interval.setSingleStep(100)
        self._check_interval.setValue(1000)
        self._check_interval.setToolTip("Check convergence every N rays per source")
        fl_conv.addRow("", self._adaptive)
        fl_conv.addRow("CV target:", self._cv_target)
        fl_conv.addRow("Check interval:", self._check_interval)
        sec_conv.addLayout(fl_conv)
        vbox.addWidget(sec_conv)

        # ---- Uncertainty (UQ) section (collapsed by default) ----
        sec_uq = CollapsibleSection("Uncertainty (UQ)", collapsed=True)
        fl_uq = QFormLayout()
        self._uq_batches = QSpinBox()
        self._uq_batches.setRange(0, 50)
        self._uq_batches.setValue(10)
        self._uq_batches.setToolTip(
            "Number of independent ray batches (K) used to estimate the confidence "
            "interval on each KPI. Same total rays as 'Rays per source' — just split "
            "into K groups so per-KPI variance can be measured.\n\n"
            "• 0 = disable UQ (legacy fast path, no ± bounds on KPIs)\n"
            "• 4-9 = coarse CI, faster\n"
            "• 10 = recommended default (Student-t ± 95% works well)\n"
            "• 20+ = tighter CI, marginal gain\n\n"
            "The heatmap panel, sweep results, and HTML report all show "
            "'value ± half_width' when K ≥ 4."
        )
        self._uq_include_spectral = QCheckBox("Store per-batch spectral grids")
        self._uq_include_spectral.setChecked(True)
        self._uq_include_spectral.setToolTip(
            "When ON, spectral scenes also keep one spectral grid per batch "
            "so wavelength-resolved KPIs get CI bounds too.\n\n"
            "Turn OFF to save memory on spectral scenes with many wavelength bins "
            "(only affects spectral sims; non-spectral sims ignore this)."
        )
        fl_uq.addRow("Batches (K):", self._uq_batches)
        fl_uq.addRow("", self._uq_include_spectral)
        sec_uq.addLayout(fl_uq)
        vbox.addWidget(sec_uq)

        # ---- Advanced section (collapsed by default) ----
        sec_adv = CollapsibleSection("Advanced", collapsed=True)
        fl_adv = QFormLayout()
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
        fl_adv.addRow("Random seed:", self._seed)
        fl_adv.addRow("Record ray paths:", self._rec)
        fl_adv.addRow("Distance unit:", self._unit)
        fl_adv.addRow("Flux unit:", self._flux_unit)
        fl_adv.addRow("Angle unit:", self._angle_unit)
        fl_adv.addRow("", self._mp)
        sec_adv.addLayout(fl_adv)
        vbox.addWidget(sec_adv)
        vbox.addStretch()

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
        self._adaptive.toggled.connect(self._apply)
        self._adaptive.toggled.connect(self._on_adaptive_toggled)
        self._cv_target.valueChanged.connect(self._apply)
        self._check_interval.valueChanged.connect(self._apply)
        self._uq_batches.valueChanged.connect(self._apply)
        self._uq_include_spectral.toggled.connect(self._apply)

        # Explicit tab order for keyboard navigation
        self.setTabOrder(self._rays, self._bounce)
        self.setTabOrder(self._bounce, self._thresh)
        self.setTabOrder(self._thresh, self._adaptive)
        self.setTabOrder(self._adaptive, self._cv_target)
        self.setTabOrder(self._cv_target, self._check_interval)
        self.setTabOrder(self._check_interval, self._uq_batches)
        self.setTabOrder(self._uq_batches, self._uq_include_spectral)
        self.setTabOrder(self._uq_include_spectral, self._seed)
        self.setTabOrder(self._seed, self._rec)
        self.setTabOrder(self._rec, self._unit)
        self.setTabOrder(self._unit, self._flux_unit)
        self.setTabOrder(self._flux_unit, self._angle_unit)
        self.setTabOrder(self._angle_unit, self._mp)

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
            QSignalBlocker(self._adaptive),
            QSignalBlocker(self._cv_target),
            QSignalBlocker(self._check_interval),
            QSignalBlocker(self._uq_batches),
            QSignalBlocker(self._uq_include_spectral),
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
        adaptive = getattr(s, "adaptive_sampling", True)
        self._adaptive.setChecked(adaptive)
        self._cv_target.setValue(getattr(s, "convergence_cv_target", 2.0))
        self._check_interval.setValue(getattr(s, "check_interval", 1000))
        self._cv_target.setEnabled(adaptive)
        self._check_interval.setEnabled(adaptive)
        self._uq_batches.setValue(getattr(s, "uq_batches", 10))
        self._uq_include_spectral.setChecked(getattr(s, "uq_include_spectral", True))
        self._loading = False
        del blockers

    def _on_adaptive_toggled(self, checked: bool):
        self._cv_target.setEnabled(checked)
        self._check_interval.setEnabled(checked)

    def _apply_preset(self, vals: dict):
        self._rays.setValue(vals["rays"])
        self._bounce.setValue(vals["bounces"])
        self._rec.setValue(vals["rec"])
        if "cv" in vals:
            self._cv_target.setValue(vals["cv"])
        # _apply fires automatically via valueChanged signals

    def _apply(self):
        if self._s is None or self._loading:
            return
        changes = [
            ('rays_per_source', self._rays.value()),
            ('max_bounces', self._bounce.value()),
            ('energy_threshold', self._thresh.value()),
            ('random_seed', self._seed.value()),
            ('record_ray_paths', self._rec.value()),
            ('distance_unit', self._unit.currentText()),
            ('flux_unit', self._flux_unit.currentText()),
            ('angle_unit', self._angle_unit.currentText()),
            ('use_multiprocessing', self._mp.isChecked()),
        ]
        if hasattr(self._s, "adaptive_sampling"):
            changes.extend([
                ('adaptive_sampling', self._adaptive.isChecked()),
                ('convergence_cv_target', self._cv_target.value()),
                ('check_interval', self._check_interval.value()),
            ])
        if hasattr(self._s, "uq_batches"):
            changes.extend([
                ('uq_batches', self._uq_batches.value()),
                ('uq_include_spectral', self._uq_include_spectral.isChecked()),
            ])
        _push_or_apply_changes(self._s, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


class BatchForm(QWidget):
    """Batch-edit form for multiple selected objects of the same type.

    For sources, dynamically shows ALL PointSource fields.  Each field
    displays the shared value when all selected sources agree, or a
    placeholder "--" when they differ.  Changing a value applies it
    immediately to every selected source.
    """

    changed = Signal()

    _PLACEHOLDER = "--"

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_content = QWidget()
        self._scroll_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._form_layout = QFormLayout(self._scroll_content)

        self._header = QLabel("Batch Edit")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        self._form_layout.addRow(self._header)

        scroll.setWidget(self._scroll_content)
        outer.addWidget(scroll)

        self._objects: list = []
        self._group: str = ""
        self._loading: bool = False
        # Dynamic source widgets — created on load
        self._src_widgets: dict[str, QWidget] = {}
        # Surface batch widgets
        self._surf_mat: QComboBox | None = None

    def _clear_dynamic(self):
        """Remove all dynamically-created rows from the form (keep header)."""
        while self._form_layout.rowCount() > 1:
            self._form_layout.removeRow(1)
        self._src_widgets.clear()
        self._surf_mat = None

    # ------------------------------------------------------------------

    def load(self, group: str, objects: list, distribution_names=None, mat_names=None):
        self._loading = True
        self._group = group
        self._objects = objects
        self._clear_dynamic()
        self._header.setText(f"Batch Edit \u2014 {len(objects)} {group}")

        if group == "Sources":
            self._build_source_fields(objects, distribution_names)
        elif group == "Surfaces":
            self._build_surface_fields(objects, mat_names)
        elif group == "Materials":
            pass  # No batch fields needed for materials currently
        elif group == "Detectors":
            pass

        self._loading = False

    # ------------------------------------------------------------------
    # Source batch — dynamic fields
    # ------------------------------------------------------------------

    def _shared_value(self, attr: str):
        """Return the shared value if all objects agree, else None."""
        vals = set()
        for obj in self._objects:
            v = getattr(obj, attr, None)
            if isinstance(v, np.ndarray):
                v = tuple(v.tolist())
            elif isinstance(v, tuple):
                v = tuple(v)
            vals.add(v)
        if len(vals) == 1:
            return vals.pop()
        return None

    def _build_source_fields(self, objects: list, distribution_names=None):
        fl = self._form_layout

        # Enabled
        self._src_widgets["enabled"] = cb = QCheckBox()
        shared = self._shared_value("enabled")
        if shared is not None:
            cb.setChecked(shared)
        else:
            cb.setTristate(True)
            cb.setCheckState(cb.checkState().__class__(1))  # Qt.CheckState.PartiallyChecked
        cb.toggled.connect(self._apply_live)
        fl.addRow("Enabled:", cb)

        # Position X, Y, Z
        pos_shared = self._shared_value("position")
        for i, axis in enumerate(("X", "Y", "Z")):
            key = f"pos_{axis.lower()}"
            w = _dspin()
            if pos_shared is not None:
                w.setValue(pos_shared[i])
            else:
                w.setSpecialValueText(self._PLACEHOLDER)
                w.setMinimum(w.minimum() - 1)
                w.setValue(w.minimum())
            w.valueChanged.connect(self._apply_live)
            self._src_widgets[key] = w
            fl.addRow(f"{axis}:", w)

        # Flux
        w = _dspin(0, 1e7, 1, 100.0, 10.0)
        shared = self._shared_value("flux")
        if shared is not None:
            w.setValue(shared)
        else:
            w.setSpecialValueText(self._PLACEHOLDER)
            w.setMinimum(w.minimum() - 1)
            w.setValue(w.minimum())
        w.valueChanged.connect(self._apply_live)
        self._src_widgets["flux"] = w
        fl.addRow("Flux:", w)

        # Distribution
        w = QComboBox()
        base = ["isotropic", "lambertian"]
        extra = [n for n in (distribution_names or []) if n not in base]
        w.addItems(base + extra)
        shared = self._shared_value("distribution")
        if shared is not None:
            idx = w.findText(shared)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.addItem(shared)
                w.setCurrentText(shared)
        else:
            w.insertItem(0, self._PLACEHOLDER)
            w.setCurrentIndex(0)
        w.currentIndexChanged.connect(self._apply_live)
        self._src_widgets["distribution"] = w
        fl.addRow("Distribution:", w)

        # Flux tolerance
        w = _dspin(0, 100, 1, 0.0, 1.0)
        shared = self._shared_value("flux_tolerance")
        if shared is not None:
            w.setValue(shared)
        else:
            w.setSpecialValueText(self._PLACEHOLDER)
            w.setMinimum(w.minimum() - 1)
            w.setValue(w.minimum())
        w.valueChanged.connect(self._apply_live)
        self._src_widgets["flux_tolerance"] = w
        fl.addRow("Flux tolerance \u00b1%:", w)

        # Current (mA)
        w = _dspin(0, 1e5, 1, 0.0, 1.0)
        shared = self._shared_value("current_mA")
        if shared is not None:
            w.setValue(shared)
        else:
            w.setSpecialValueText(self._PLACEHOLDER)
            w.setMinimum(w.minimum() - 1)
            w.setValue(w.minimum())
        w.valueChanged.connect(self._apply_live)
        self._src_widgets["current_mA"] = w
        fl.addRow("Current (mA):", w)

        # Flux/mA
        w = _dspin(0, 1e5, 4, 0.0, 0.01)
        shared = self._shared_value("flux_per_mA")
        if shared is not None:
            w.setValue(shared)
        else:
            w.setSpecialValueText(self._PLACEHOLDER)
            w.setMinimum(w.minimum() - 1)
            w.setValue(w.minimum())
        w.valueChanged.connect(self._apply_live)
        self._src_widgets["flux_per_mA"] = w
        fl.addRow("Flux/mA:", w)

        # Thermal derate
        w = _dspin(0, 1, 3, 1.0, 0.01)
        shared = self._shared_value("thermal_derate")
        if shared is not None:
            w.setValue(shared)
        else:
            w.setSpecialValueText(self._PLACEHOLDER)
            w.setMinimum(w.minimum() - 1)
            w.setValue(w.minimum())
        w.valueChanged.connect(self._apply_live)
        self._src_widgets["thermal_derate"] = w
        fl.addRow("Thermal derate:", w)

        # LED Color R, G, B
        color_shared = self._shared_value("color_rgb")
        color_row = QHBoxLayout()
        for i, ch in enumerate(("R", "G", "B")):
            key = f"color_{ch.lower()}"
            w = _dspin(0, 1, 2, 1.0, 0.05)
            if color_shared is not None:
                w.setValue(color_shared[i])
            else:
                w.setSpecialValueText(self._PLACEHOLDER)
                w.setMinimum(w.minimum() - 1)
                w.setValue(w.minimum())
            w.valueChanged.connect(self._apply_live)
            self._src_widgets[key] = w
            color_row.addWidget(QLabel(f"{ch}:"))
            color_row.addWidget(w)
        fl.addRow("LED Color:", color_row)

        # SPD
        w = QComboBox()
        w.addItems(["white", "warm_white", "cool_white",
                     "mono_450", "mono_525", "mono_630"])
        w.setEditable(True)
        shared = self._shared_value("spd")
        if shared is not None:
            if w.findText(shared) < 0:
                w.addItem(shared)
            w.setCurrentText(shared)
        else:
            w.setEditText(self._PLACEHOLDER)
        w.currentTextChanged.connect(self._apply_live)
        self._src_widgets["spd"] = w
        fl.addRow("SPD:", w)

    # ------------------------------------------------------------------
    # Surface batch
    # ------------------------------------------------------------------

    def _build_surface_fields(self, objects: list, mat_names=None):
        fl = self._form_layout
        w = QComboBox()
        if mat_names:
            w.addItems(mat_names)
        w.currentIndexChanged.connect(self._apply_live)
        self._surf_mat = w
        fl.addRow("Material:", w)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _apply_live(self):
        if not self._objects or self._loading:
            return
        if self._group == "Sources":
            self._apply_sources()
        elif self._group == "Surfaces":
            self._apply_surfaces()
        self.changed.emit()

    def _apply_sources(self):
        ws = self._src_widgets
        push_fn = getattr(self, '_push_command', None)

        for src in self._objects:
            changes = []

            cb = ws.get("enabled")
            if cb is not None and not cb.isTristate():
                changes.append(('enabled', cb.isChecked()))

            px = ws.get("pos_x")
            py = ws.get("pos_y")
            pz = ws.get("pos_z")
            if px and py and pz:
                pos = list(src.position)
                if px.value() > px.minimum():
                    pos[0] = px.value()
                if py.value() > py.minimum():
                    pos[1] = py.value()
                if pz.value() > pz.minimum():
                    pos[2] = pz.value()
                new_pos = np.array(pos)
                if not np.array_equal(new_pos, src.position):
                    changes.append(('position', new_pos))

            for attr, key in [
                ("flux", "flux"),
                ("flux_tolerance", "flux_tolerance"),
                ("current_mA", "current_mA"),
                ("flux_per_mA", "flux_per_mA"),
                ("thermal_derate", "thermal_derate"),
            ]:
                w = ws.get(key)
                if w is not None and w.value() > w.minimum():
                    changes.append((attr, w.value()))

            w = ws.get("distribution")
            if w is not None and w.currentText() != self._PLACEHOLDER:
                changes.append(('distribution', w.currentText()))

            w = ws.get("spd")
            if w is not None and w.currentText() != self._PLACEHOLDER:
                changes.append(('spd', w.currentText()))

            cr = ws.get("color_r")
            cg = ws.get("color_g")
            cb_c = ws.get("color_b")
            if cr is not None and cg is not None and cb_c is not None:
                if (cr.value() > cr.minimum() and cg.value() > cg.minimum()
                        and cb_c.value() > cb_c.minimum()):
                    changes.append(('color_rgb', (cr.value(), cg.value(), cb_c.value())))

            if changes:
                _push_or_apply_changes(
                    src, changes,
                    push_fn,
                    getattr(self, '_begin_macro', None),
                    getattr(self, '_end_macro', None),
                    getattr(self, '_undo_stack', None),
                    getattr(self, '_undo_refresh', None),
                    self.changed,
                )

    def _apply_surfaces(self):
        if self._surf_mat is None:
            return
        mat = self._surf_mat.currentText()
        if not mat:
            return
        push_fn = getattr(self, '_push_command', None)
        for surf in self._objects:
            _push_or_apply_changes(
                surf, [('material_name', mat)],
                push_fn,
                getattr(self, '_begin_macro', None),
                getattr(self, '_end_macro', None),
                getattr(self, '_undo_stack', None),
                getattr(self, '_undo_refresh', None),
                self.changed,
            )


class SolidBoxForm(QWidget):
    """Property editor for a SolidBox (box-level properties)."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._mat = QComboBox()
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Material:", self._mat)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        fl_pos.addRow("Center X:", self._cx)
        fl_pos.addRow("Center Y:", self._cy)
        fl_pos.addRow("Center Z:", self._cz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Dimensions section ----
        sec_dim = CollapsibleSection("Dimensions", collapsed=False)
        fl_dim = QFormLayout()
        self._dw = _dspin(0.1, 9999, 2, 50.0)
        self._dh = _dspin(0.1, 9999, 2, 30.0)
        self._dd = _dspin(0.1, 9999, 2, 3.0)
        fl_dim.addRow("Width (X):", self._dw)
        fl_dim.addRow("Height (Y):", self._dh)
        fl_dim.addRow("Depth (Z):", self._dd)
        sec_dim.addLayout(fl_dim)
        vbox.addWidget(sec_dim)

        # ---- Coupling Edges section (collapsed by default) ----
        sec_edges = CollapsibleSection("Coupling Edges", collapsed=True)
        fl_edges = QFormLayout()
        self._edge_checks: dict[str, QCheckBox] = {}
        for edge_id in ("left", "right", "front", "back"):
            cb = QCheckBox(edge_id)
            fl_edges.addRow("", cb)
            self._edge_checks[edge_id] = cb
        sec_edges.addLayout(fl_edges)
        vbox.addWidget(sec_edges)
        vbox.addStretch()

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
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('dimensions', (self._dw.value(), self._dh.value(), self._dd.value())),
            ('coupling_edges', [eid for eid, cb in self._edge_checks.items() if cb.isChecked()]),
        ]
        if self._mat.currentText():
            changes.append(('material_name', self._mat.currentText()))
        _push_or_apply_changes(self._box, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


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
        new_optics = dict(self._box.face_optics)
        if selected == "(use bulk material)" or not selected:
            new_optics.pop(self._face_id, None)
        else:
            new_optics[self._face_id] = selected
        changes = [('face_optics', new_optics)]
        _push_or_apply_changes(self._box, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


class SolidCylinderForm(QWidget):
    """Property editor for a SolidCylinder."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._mat = QComboBox()
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Material:", self._mat)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        fl_pos.addRow("Center X:", self._cx)
        fl_pos.addRow("Center Y:", self._cy)
        fl_pos.addRow("Center Z:", self._cz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Orientation section ----
        sec_orient = CollapsibleSection("Orientation", collapsed=True)
        fl_orient = QFormLayout()
        self._ax = _dspin(-1.0, 1.0, 4, 0.0, 0.01)
        self._ay = _dspin(-1.0, 1.0, 4, 0.0, 0.01)
        self._az = _dspin(-1.0, 1.0, 4, 1.0, 0.01)
        fl_orient.addRow("Axis X:", self._ax)
        fl_orient.addRow("Axis Y:", self._ay)
        fl_orient.addRow("Axis Z:", self._az)
        sec_orient.addLayout(fl_orient)
        vbox.addWidget(sec_orient)

        # ---- Dimensions section ----
        sec_dim = CollapsibleSection("Dimensions", collapsed=False)
        fl_dim = QFormLayout()
        self._radius = _dspin(0.01, 9999, 3, 5.0, 0.5)
        self._length = _dspin(0.01, 9999, 3, 10.0, 0.5)
        fl_dim.addRow("Radius:", self._radius)
        fl_dim.addRow("Length:", self._length)
        sec_dim.addLayout(fl_dim)
        vbox.addWidget(sec_dim)
        vbox.addStretch()

        self._cyl: SolidCylinder | None = None
        self._loading = False

        for w in (self._cx, self._cy, self._cz, self._ax, self._ay, self._az,
                  self._radius, self._length):
            w.valueChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, cyl: SolidCylinder, mat_names: list[str]):
        self._loading = True
        self._cyl = cyl
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._cx), QSignalBlocker(self._cy), QSignalBlocker(self._cz),
            QSignalBlocker(self._ax), QSignalBlocker(self._ay), QSignalBlocker(self._az),
            QSignalBlocker(self._radius), QSignalBlocker(self._length),
            QSignalBlocker(self._mat),
        ]
        self._name.setText(cyl.name)
        self._cx.setValue(float(cyl.center[0]))
        self._cy.setValue(float(cyl.center[1]))
        self._cz.setValue(float(cyl.center[2]))
        self._ax.setValue(float(cyl.axis[0]))
        self._ay.setValue(float(cyl.axis[1]))
        self._az.setValue(float(cyl.axis[2]))
        self._radius.setValue(float(cyl.radius))
        self._length.setValue(float(cyl.length))
        self._mat.clear()
        self._mat.addItems(mat_names)
        midx = self._mat.findText(cyl.material_name)
        if midx >= 0:
            self._mat.setCurrentIndex(midx)
        self._loading = False
        del blockers

    def _apply(self):
        if self._cyl is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        axis = np.array([self._ax.value(), self._ay.value(), self._az.value()])
        norm = np.linalg.norm(axis)
        if norm > 1e-9:
            axis = axis / norm
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('axis', axis),
            ('radius', self._radius.value()),
            ('length', self._length.value()),
        ]
        if self._mat.currentText():
            changes.append(('material_name', self._mat.currentText()))
        _push_or_apply_changes(self._cyl, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)


class SolidPrismForm(QWidget):
    """Property editor for a SolidPrism."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ---- Identity section ----
        sec_identity = CollapsibleSection("Identity", collapsed=False)
        fl_identity = QFormLayout()
        self._name = _name_edit()
        self._mat = QComboBox()
        fl_identity.addRow("Name:", self._name)
        fl_identity.addRow("Material:", self._mat)
        sec_identity.addLayout(fl_identity)
        vbox.addWidget(sec_identity)

        # ---- Position section ----
        sec_pos = CollapsibleSection("Position", collapsed=False)
        fl_pos = QFormLayout()
        self._cx = _dspin()
        self._cy = _dspin()
        self._cz = _dspin()
        fl_pos.addRow("Center X:", self._cx)
        fl_pos.addRow("Center Y:", self._cy)
        fl_pos.addRow("Center Z:", self._cz)
        sec_pos.addLayout(fl_pos)
        vbox.addWidget(sec_pos)

        # ---- Orientation section ----
        sec_orient = CollapsibleSection("Orientation", collapsed=True)
        fl_orient = QFormLayout()
        self._ax = _dspin(-1.0, 1.0, 4, 0.0, 0.01)
        self._ay = _dspin(-1.0, 1.0, 4, 0.0, 0.01)
        self._az = _dspin(-1.0, 1.0, 4, 1.0, 0.01)
        fl_orient.addRow("Axis X:", self._ax)
        fl_orient.addRow("Axis Y:", self._ay)
        fl_orient.addRow("Axis Z:", self._az)
        sec_orient.addLayout(fl_orient)
        vbox.addWidget(sec_orient)

        # ---- Dimensions section ----
        sec_dim = CollapsibleSection("Dimensions", collapsed=False)
        fl_dim = QFormLayout()
        self._n_sides = QSpinBox()
        self._n_sides.setRange(3, 12)
        self._n_sides.setValue(6)
        self._n_sides.setToolTip("Number of prism sides (3=triangle, 4=square, 6=hexagon, etc.)")
        self._circ_r = _dspin(0.01, 9999, 3, 5.0, 0.5)
        self._circ_r.setToolTip("Circumscribed radius: distance from center to corner vertex")
        self._length = _dspin(0.01, 9999, 3, 10.0, 0.5)
        fl_dim.addRow("Sides:", self._n_sides)
        fl_dim.addRow("Circ. radius:", self._circ_r)
        fl_dim.addRow("Length:", self._length)
        sec_dim.addLayout(fl_dim)
        vbox.addWidget(sec_dim)
        vbox.addStretch()

        self._prism: SolidPrism | None = None
        self._loading = False

        for w in (self._cx, self._cy, self._cz, self._ax, self._ay, self._az,
                  self._circ_r, self._length):
            w.valueChanged.connect(self._apply)
        self._n_sides.valueChanged.connect(self._apply)
        self._mat.currentIndexChanged.connect(self._apply)
        self._name.editingFinished.connect(self._apply)

    def load(self, prism: SolidPrism, mat_names: list[str]):
        self._loading = True
        self._prism = prism
        blockers = [
            QSignalBlocker(self._name),
            QSignalBlocker(self._cx), QSignalBlocker(self._cy), QSignalBlocker(self._cz),
            QSignalBlocker(self._ax), QSignalBlocker(self._ay), QSignalBlocker(self._az),
            QSignalBlocker(self._n_sides), QSignalBlocker(self._circ_r),
            QSignalBlocker(self._length), QSignalBlocker(self._mat),
        ]
        self._name.setText(prism.name)
        self._cx.setValue(float(prism.center[0]))
        self._cy.setValue(float(prism.center[1]))
        self._cz.setValue(float(prism.center[2]))
        self._ax.setValue(float(prism.axis[0]))
        self._ay.setValue(float(prism.axis[1]))
        self._az.setValue(float(prism.axis[2]))
        self._n_sides.setValue(int(prism.n_sides))
        self._circ_r.setValue(float(prism.circumscribed_radius))
        self._length.setValue(float(prism.length))
        self._mat.clear()
        self._mat.addItems(mat_names)
        midx = self._mat.findText(prism.material_name)
        if midx >= 0:
            self._mat.setCurrentIndex(midx)
        self._loading = False
        del blockers

    def _apply(self):
        if self._prism is None or self._loading:
            return
        name = self._name.text().strip()
        if not name:
            return
        axis = np.array([self._ax.value(), self._ay.value(), self._az.value()])
        norm = np.linalg.norm(axis)
        if norm > 1e-9:
            axis = axis / norm
        changes = [
            ('name', name),
            ('center', np.array([self._cx.value(), self._cy.value(), self._cz.value()])),
            ('axis', axis),
            ('n_sides', self._n_sides.value()),
            ('circumscribed_radius', self._circ_r.value()),
            ('length', self._length.value()),
        ]
        if self._mat.currentText():
            changes.append(('material_name', self._mat.currentText()))
        _push_or_apply_changes(self._prism, changes,
                               getattr(self, '_push_command', None),
                               getattr(self, '_begin_macro', None),
                               getattr(self, '_end_macro', None),
                               getattr(self, '_undo_stack', None),
                               getattr(self, '_undo_refresh', None),
                               self.changed)
