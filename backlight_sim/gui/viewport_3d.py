"""3D OpenGL viewport - scene preview, selection highlight, and view modes."""

from __future__ import annotations

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QVBoxLayout, QWidget


class Viewport3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = gl.GLViewWidget()
        self._view.setCameraPosition(distance=80, elevation=30, azimuth=45)
        layout.addWidget(self._view)

        grid = gl.GLGridItem()
        grid.setSize(200, 200)
        grid.setSpacing(10, 10)
        self._view.addItem(grid)
        self._add_reference_axes()

        self._scene_items: list = []
        self._path_items: list = []
        self._last_project = None
        self._selected_group: str | None = None
        self._selected_name: str | None = None
        self._view_mode = "wireframe"

    def _add_reference_axes(self):
        axis_len = 25.0
        axes = [
            (np.array([[-axis_len, 0, 0], [axis_len, 0, 0]], dtype=float), (1.0, 0.25, 0.25, 1.0)),
            (np.array([[0, -axis_len, 0], [0, axis_len, 0]], dtype=float), (0.25, 1.0, 0.25, 1.0)),
            (np.array([[0, 0, -axis_len], [0, 0, axis_len]], dtype=float), (0.25, 0.55, 1.0, 1.0)),
        ]
        for pts, color in axes:
            axis_item = gl.GLLinePlotItem(pos=pts, color=color, width=2, mode="lines")
            self._view.addItem(axis_item)

    def set_view_mode(self, mode: str):
        if mode not in ("wireframe", "solid", "transparent"):
            return
        self._view_mode = mode
        if self._last_project is not None:
            self.refresh(self._last_project)

    def set_selected(self, group: str | None, name: str | None, redraw: bool = True):
        self._selected_group = group
        self._selected_name = name
        if redraw and self._last_project is not None:
            self.refresh(self._last_project)

    def clear_selection(self, redraw: bool = True):
        self.set_selected(None, None, redraw=redraw)

    def refresh(self, project):
        self._last_project = project
        for item in self._scene_items:
            self._view.removeItem(item)
        self._scene_items.clear()

        selected_material = self._selected_name if self._selected_group == "Materials" else None

        for source in project.sources:
            is_selected = self._selected_group == "Sources" and source.name == self._selected_name
            size = 20 if is_selected else 14
            color = (1.0, 1.0, 0.2, 1.0) if is_selected else (1.0, 1.0, 0.1, 1.0)
            item = gl.GLScatterPlotItem(
                pos=np.array([source.position]),
                size=size,
                color=color,
                pxMode=True,
            )
            self._view.addItem(item)
            self._scene_items.append(item)

        for surf in project.surfaces:
            mat = project.materials.get(surf.material_name)
            base = _material_color(mat)
            is_selected = self._selected_group == "Surfaces" and surf.name == self._selected_name
            by_material = selected_material is not None and surf.material_name == selected_material

            self._draw_rect(surf.center, surf.u_axis, surf.v_axis, surf.size, base)
            if is_selected or by_material:
                self._draw_rect_wire(
                    surf.center,
                    surf.u_axis,
                    surf.v_axis,
                    surf.size,
                    color=(1.0, 1.0, 0.0, 1.0),
                    width=4,
                )

        det_base = (0.0, 0.85, 0.85)
        for det in project.detectors:
            is_selected = self._selected_group == "Detectors" and det.name == self._selected_name
            self._draw_rect(det.center, det.u_axis, det.v_axis, det.size, det_base, is_detector=True)
            if is_selected:
                self._draw_rect_wire(
                    det.center,
                    det.u_axis,
                    det.v_axis,
                    det.size,
                    color=(1.0, 1.0, 0.0, 1.0),
                    width=4,
                )

    def _draw_rect(self, center, u_axis, v_axis, size, base_rgb, is_detector=False):
        if self._view_mode == "wireframe":
            alpha = 1.0
            if is_detector:
                alpha = 0.9
            self._draw_rect_wire(center, u_axis, v_axis, size, (*base_rgb, alpha), 2)
            return

        if self._view_mode == "transparent":
            alpha = 0.25 if not is_detector else 0.18
        else:
            alpha = 0.95 if not is_detector else 0.45

        verts, faces = _rect_mesh(center, u_axis, v_axis, size)
        colors = np.array([[base_rgb[0], base_rgb[1], base_rgb[2], alpha]] * len(faces))
        mesh = gl.GLMeshItem(
            vertexes=verts,
            faces=faces,
            faceColors=colors,
            smooth=False,
            drawEdges=True,
            edgeColor=(base_rgb[0], base_rgb[1], base_rgb[2], 1.0),
        )
        if self._view_mode == "transparent":
            mesh.setGLOptions("translucent")
        self._view.addItem(mesh)
        self._scene_items.append(mesh)

    def _draw_rect_wire(self, center, u_axis, v_axis, size, color, width=2):
        pts = _rect_loop(center, u_axis, v_axis, size)
        item = gl.GLLinePlotItem(pos=pts, color=color, width=width, mode="line_strip")
        self._view.addItem(item)
        self._scene_items.append(item)

    def show_ray_paths(self, paths: list[list[np.ndarray]]):
        for item in self._path_items:
            self._view.removeItem(item)
        self._path_items.clear()

        if not paths:
            return

        segments = []
        nan_row = np.array([[np.nan, np.nan, np.nan]])
        for path in paths:
            if len(path) < 2:
                continue
            segments.append(np.array(path, dtype=float))
            segments.append(nan_row)

        if not segments:
            return

        all_pts = np.concatenate(segments, axis=0)
        ray_item = gl.GLLinePlotItem(
            pos=all_pts,
            color=(1.0, 0.6, 0.0, 0.35),
            width=1,
            mode="line_strip",
            antialias=True,
        )
        self._view.addItem(ray_item)
        self._path_items.append(ray_item)

    def clear_ray_paths(self):
        for item in self._path_items:
            self._view.removeItem(item)
        self._path_items.clear()


def _material_color(mat) -> tuple[float, float, float]:
    if mat is None or mat.color is None:
        return (0.55, 0.65, 1.0)
    return tuple(float(c) for c in mat.color[:3])


def _rect_loop(center, u_axis, v_axis, size) -> np.ndarray:
    hw, hh = size[0] / 2.0, size[1] / 2.0
    corners = [
        center + u_axis * (-hw) + v_axis * (-hh),
        center + u_axis * (hw) + v_axis * (-hh),
        center + u_axis * (hw) + v_axis * (hh),
        center + u_axis * (-hw) + v_axis * (hh),
        center + u_axis * (-hw) + v_axis * (-hh),
    ]
    return np.array(corners, dtype=float)


def _rect_mesh(center, u_axis, v_axis, size):
    hw, hh = size[0] / 2.0, size[1] / 2.0
    verts = np.array(
        [
            center + u_axis * (-hw) + v_axis * (-hh),
            center + u_axis * (hw) + v_axis * (-hh),
            center + u_axis * (hw) + v_axis * (hh),
            center + u_axis * (-hw) + v_axis * (hh),
        ],
        dtype=float,
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=int)
    return verts, faces
