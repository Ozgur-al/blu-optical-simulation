"""3D sphere receiver visualization — displays sphere detector results."""

from __future__ import annotations

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel

from backlight_sim.core.detectors import SimulationResult
from backlight_sim.gui.theme import GL_BG


def _colormap_array(grid: np.ndarray) -> np.ndarray:
    """Map a 2D grid to RGBA colors using an inferno-like colormap.

    Returns (ny, nx, 4) float array with values in [0, 1].
    """
    ny, nx = grid.shape
    mn, mx = float(grid.min()), float(grid.max())
    if mx <= mn:
        return np.ones((ny, nx, 4), dtype=float) * 0.5

    norm = (grid - mn) / (mx - mn)  # 0-1

    # Simple inferno-like: black -> purple -> orange -> yellow
    r = np.clip(1.5 * norm - 0.25, 0, 1)
    g = np.clip(1.5 * norm - 0.5, 0, 1)
    b = np.clip(2.0 * (0.5 - abs(norm - 0.35)), 0, 1)
    a = np.ones_like(norm)

    colors = np.stack([r, g, b, a], axis=-1)
    return colors.astype(np.float32)


def _build_sphere_mesh(grid: np.ndarray, radius: float):
    """Build a sphere mesh from (n_theta, n_phi) grid data.

    Returns (verts, faces, face_colors) for GLMeshItem.
    """
    n_theta, n_phi = grid.shape
    colors = _colormap_array(grid)

    # Vertex grid: (n_theta+1) x (n_phi+1)
    # Offset poles slightly to avoid degenerate triangles (pyqtgraph MeshData norm warning)
    theta = np.linspace(1e-4, np.pi - 1e-4, n_theta + 1)
    phi = np.linspace(0, 2.0 * np.pi, n_phi + 1)
    theta_g, phi_g = np.meshgrid(theta, phi, indexing="ij")

    x = radius * np.sin(theta_g) * np.cos(phi_g)
    y = radius * np.sin(theta_g) * np.sin(phi_g)
    z = radius * np.cos(theta_g)

    # Flatten vertices
    verts = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=-1).astype(np.float32)
    n_v_phi = n_phi + 1

    faces = []
    face_colors = []
    for it in range(n_theta):
        for ip in range(n_phi):
            v00 = it * n_v_phi + ip
            v01 = it * n_v_phi + ip + 1
            v10 = (it + 1) * n_v_phi + ip
            v11 = (it + 1) * n_v_phi + ip + 1
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])
            c = colors[it, ip]
            face_colors.append(c)
            face_colors.append(c)

    return verts, np.array(faces, dtype=np.int32), np.array(face_colors, dtype=np.float32)


class Receiver3DWidget(QWidget):
    """3D sphere receiver visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Detector:"))
        self._det_cb = QComboBox()
        self._det_cb.setAccessibleName("Detector selector")
        self._det_cb.setToolTip("Select a sphere or planar detector to visualize")
        self._det_cb.currentTextChanged.connect(self._on_det_changed)
        ctrl.addWidget(self._det_cb)

        ctrl.addWidget(QLabel("View:"))
        self._view_mode = QComboBox()
        self._view_mode.setAccessibleName("3D view mode")
        self._view_mode.setToolTip("Switch between sphere and flat map visualization")
        self._view_mode.addItems(["Sphere", "Flat map"])
        self._view_mode.currentIndexChanged.connect(self._refresh)
        ctrl.addWidget(self._view_mode)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._view = gl.GLViewWidget()
        self._view.setBackgroundColor(*GL_BG)
        self._view.setCameraPosition(distance=80, elevation=30, azimuth=45)
        layout.addWidget(self._view)

        self._mesh_item = None
        self._surface_item = None
        self._grid_item = None
        self._sim_result: SimulationResult | None = None

    def update_results(self, result: SimulationResult):
        self._sim_result = result
        self._det_cb.blockSignals(True)
        self._det_cb.clear()

        # Sphere detectors first, then planar
        names = []
        for name in result.sphere_detectors:
            names.append(f"[sphere] {name}")
        for name in result.detectors:
            names.append(f"[planar] {name}")
        self._det_cb.addItems(names)
        self._det_cb.blockSignals(False)

        if names:
            self._refresh()

    def _on_det_changed(self, _name: str):
        self._refresh()

    def _clear_items(self):
        for item in (self._mesh_item, self._surface_item, self._grid_item):
            if item is not None:
                self._view.removeItem(item)
        self._mesh_item = None
        self._surface_item = None
        self._grid_item = None

    def _refresh(self, _=None):
        self._clear_items()
        if self._sim_result is None:
            return

        text = self._det_cb.currentText()
        if not text:
            return

        if text.startswith("[sphere] "):
            name = text[len("[sphere] "):]
            sdr = self._sim_result.sphere_detectors.get(name)
            if sdr is None:
                return
            # Find the sphere detector for radius
            from backlight_sim.core.detectors import SphereDetector
            radius = 10.0  # fallback
            # We store radius in the result indirectly; use grid shape
            self._show_sphere(sdr.grid, radius)
        elif text.startswith("[planar] "):
            name = text[len("[planar] "):]
            dr = self._sim_result.detectors.get(name)
            if dr is None:
                return
            self._show_flat(dr.grid)

    def _show_sphere(self, grid: np.ndarray, radius: float):
        """Render sphere detector as a colored sphere mesh."""
        if grid.shape[0] < 2 or grid.shape[1] < 2:
            return

        view_mode = self._view_mode.currentText()
        if view_mode == "Flat map":
            self._show_flat_map_of_sphere(grid)
            return

        # Scale radius for nice display
        display_r = 30.0
        verts, faces, face_colors = _build_sphere_mesh(grid, display_r)

        self._mesh_item = gl.GLMeshItem(
            vertexes=verts,
            faces=faces,
            faceColors=face_colors,
            smooth=True,
            drawEdges=False,
        )
        self._mesh_item.setGLOptions("opaque")
        self._view.addItem(self._mesh_item)

    def _show_flat_map_of_sphere(self, grid: np.ndarray):
        """Show sphere data as a flat (theta x phi) surface plot."""
        n_theta, n_phi = grid.shape
        x = np.linspace(0, 360, n_phi)
        y = np.linspace(0, 180, n_theta)

        # GLSurfacePlotItem expects z shape (len(x), len(y)) = (n_phi, n_theta)
        z_data = grid.T.copy()
        mx = z_data.max()
        if mx > 0:
            z_data = z_data / mx * 20.0

        colors = _colormap_array(grid).transpose(1, 0, 2)  # (n_phi, n_theta, 4)
        self._surface_item = gl.GLSurfacePlotItem(
            x=x, y=y, z=z_data,
            colors=colors,
            shader="shaded",
            smooth=True,
        )
        self._view.addItem(self._surface_item)

        self._grid_item = gl.GLGridItem()
        self._grid_item.setSize(360, 180)
        self._grid_item.setSpacing(36, 18)
        self._view.addItem(self._grid_item)

    def _show_flat(self, grid: np.ndarray):
        """Show planar detector as surface plot (legacy behavior)."""
        ny, nx = grid.shape
        if ny < 2 or nx < 2:
            return

        x = np.linspace(-nx / 2, nx / 2, nx)
        y = np.linspace(-ny / 2, ny / 2, ny)

        # GLSurfacePlotItem expects z shape (len(x), len(y)) = (nx, ny)
        z_data = grid.T.copy()
        mx = z_data.max()
        if mx > 0:
            z_data = z_data / mx * 20.0

        colors = _colormap_array(grid).transpose(1, 0, 2)  # (nx, ny, 4)
        self._surface_item = gl.GLSurfacePlotItem(
            x=x, y=y, z=z_data,
            colors=colors,
            shader="shaded",
            smooth=True,
        )
        self._view.addItem(self._surface_item)

        self._grid_item = gl.GLGridItem()
        self._grid_item.setSize(nx, ny)
        self._grid_item.setSpacing(nx / 10, ny / 10)
        self._view.addItem(self._grid_item)

    def clear(self):
        self._clear_items()
        self._det_cb.clear()
        self._sim_result = None
