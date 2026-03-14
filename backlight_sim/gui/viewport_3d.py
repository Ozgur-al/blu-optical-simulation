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
        self._view.setCameraPosition(distance=180, elevation=30, azimuth=45)
        layout.addWidget(self._view)

        grid = gl.GLGridItem()
        grid.setSize(2000, 2000)
        grid.setSpacing(50, 50)
        self._view.addItem(grid)
        self._add_reference_axes()

        self._scene_items: list = []
        self._path_items: list = []
        self._last_project = None
        self._selected_group: str | None = None
        self._selected_name: str | None = None
        self._view_mode = "wireframe"
        self._default_distance = 180

    def _add_reference_axes(self):
        axis_len = 120.0
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

    def set_camera_preset(self, preset: str):
        presets = {
            "xy+": (90, 0),
            "xy-": (-90, 0),
            "yz+": (0, 0),
            "yz-": (0, 180),
            "xz+": (0, 90),
            "xz-": (0, -90),
        }
        if preset not in presets:
            return
        elevation, azimuth = presets[preset]
        self._view.setCameraPosition(distance=self._default_distance, elevation=elevation, azimuth=azimuth)

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

        # Sphere detectors
        for sd in project.sphere_detectors:
            is_selected = self._selected_group == "Sphere Detectors" and sd.name == self._selected_name
            color = (0.0, 1.0, 1.0, 0.35) if not is_selected else (1.0, 1.0, 0.0, 0.5)
            self._draw_sphere_wire(sd.center, sd.radius, color)

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

        # Solid Bodies (LGP slabs)
        for box in getattr(project, "solid_bodies", []):
            is_selected = (
                self._selected_group == "Solid Bodies" and
                (self._selected_name == box.name or
                 (self._selected_name and self._selected_name.startswith(f"{box.name}::")))
            )
            self._draw_solid_box(box, is_selected)

    def _draw_solid_box(self, box, is_selected: bool = False):
        """Render a SolidBox as a semi-transparent solid with visible edges."""
        lgp_color = (0.4, 0.7, 1.0)
        edge_color = (1.0, 1.0, 0.0, 1.0) if is_selected else (0.4, 0.7, 1.0, 1.0)
        edge_width = 4 if is_selected else 2

        faces = box.get_faces()
        for face_rect in faces:
            if self._view_mode == "wireframe":
                self._draw_rect_wire(
                    face_rect.center, face_rect.u_axis, face_rect.v_axis,
                    face_rect.size, edge_color, edge_width
                )
            else:
                alpha = 0.25 if self._view_mode == "transparent" else 0.5
                verts, face_indices = _rect_mesh(face_rect.center, face_rect.u_axis, face_rect.v_axis, face_rect.size)
                colors = np.array([[lgp_color[0], lgp_color[1], lgp_color[2], alpha]] * len(face_indices))
                mesh = gl.GLMeshItem(
                    vertexes=verts,
                    faces=face_indices,
                    faceColors=colors,
                    smooth=False,
                    drawEdges=True,
                    edgeColor=edge_color,
                )
                if self._view_mode == "transparent":
                    mesh.setGLOptions("translucent")
                else:
                    mesh.setGLOptions("translucent")  # solid box always uses translucent for see-through
                self._view.addItem(mesh)
                self._scene_items.append(mesh)

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

    def _draw_sphere_wire(self, center, radius, color, n_pts=48):
        """Draw three orthogonal circle rings to represent a sphere."""
        t = np.linspace(0, 2 * np.pi, n_pts + 1)
        for pts_arr in (
            np.column_stack([np.cos(t) * radius + center[0],
                             np.sin(t) * radius + center[1],
                             np.full(n_pts + 1, center[2])]),
            np.column_stack([np.cos(t) * radius + center[0],
                             np.full(n_pts + 1, center[1]),
                             np.sin(t) * radius + center[2]]),
            np.column_stack([np.full(n_pts + 1, center[0]),
                             np.cos(t) * radius + center[1],
                             np.sin(t) * radius + center[2]]),
        ):
            item = gl.GLLinePlotItem(pos=pts_arr.astype(float), color=color, width=2, mode="line_strip")
            self._view.addItem(item)
            self._scene_items.append(item)

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
