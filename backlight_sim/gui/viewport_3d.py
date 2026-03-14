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
        # GLViewWidget uses OpenGL rendering and ignores QSS — set background explicitly
        self._view.setBackgroundColor(30, 30, 30, 255)
        layout.addWidget(self._view)

        grid = gl.GLGridItem()
        grid.setSize(2000, 2000)
        grid.setSpacing(50, 50)
        self._view.addItem(grid)
        self._add_reference_axes()

        self._scene_items: list = []
        self._path_items: list = []
        self._farfield_lobe_item = None
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

        # Solid Cylinders
        for cyl in getattr(project, "solid_cylinders", []):
            is_selected = (
                self._selected_group == "Solid Bodies" and
                (self._selected_name == cyl.name or
                 (self._selected_name and self._selected_name.startswith(f"{cyl.name}::")))
            )
            selected_face = None
            if is_selected and self._selected_name and "::" in self._selected_name:
                selected_face = self._selected_name.split("::", 1)[1]
            mat = project.materials.get(cyl.material_name)
            color = _material_color(mat)
            edge_color = (1.0, 1.0, 0.0, 1.0) if is_selected else (*color, 1.0)
            self._draw_solid_cylinder(cyl, color, edge_color, selected_face=selected_face)

        # Solid Prisms
        for prism in getattr(project, "solid_prisms", []):
            is_selected = (
                self._selected_group == "Solid Bodies" and
                (self._selected_name == prism.name or
                 (self._selected_name and self._selected_name.startswith(f"{prism.name}::")))
            )
            selected_face = None
            if is_selected and self._selected_name and "::" in self._selected_name:
                selected_face = self._selected_name.split("::", 1)[1]
            mat = project.materials.get(prism.material_name)
            color = _material_color(mat)
            edge_color = (1.0, 1.0, 0.0, 1.0) if is_selected else (*color, 1.0)
            self._draw_solid_prism(prism, color, edge_color, selected_face=selected_face)

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

    def _draw_solid_cylinder(self, cyl, color, edge_color, selected_face=None, n_seg=32):
        """Render a SolidCylinder as a smooth mesh or wireframe."""
        axis = np.asarray(cyl.axis, float)
        # Build orthonormal basis perpendicular to axis
        ref = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(axis, ref)) > 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        u = np.cross(axis, ref)
        u = u / np.linalg.norm(u)
        v = np.cross(axis, u)
        v = v / np.linalg.norm(v)

        angles = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
        half = cyl.length / 2.0
        top_center = cyl.center + axis * half
        bot_center = cyl.center - axis * half

        ring_top = top_center[None, :] + cyl.radius * (
            np.cos(angles)[:, None] * u[None, :] + np.sin(angles)[:, None] * v[None, :]
        )
        ring_bot = bot_center[None, :] + cyl.radius * (
            np.cos(angles)[:, None] * u[None, :] + np.sin(angles)[:, None] * v[None, :]
        )

        _hl = (1.0, 1.0, 0.0)  # highlight yellow

        if self._view_mode == "wireframe":
            top_color = (*_hl, 1.0) if selected_face == "top_cap" else edge_color
            bot_color = (*_hl, 1.0) if selected_face == "bottom_cap" else edge_color
            side_color = (*_hl, 1.0) if selected_face == "side" else edge_color
            top_w = 4 if selected_face == "top_cap" else 2
            bot_w = 4 if selected_face == "bottom_cap" else 2
            side_w = 4 if selected_face == "side" else 2
            loop_t = np.vstack([ring_top, ring_top[:1]])
            item = gl.GLLinePlotItem(pos=loop_t.astype(float), color=top_color, width=top_w, mode="line_strip")
            self._view.addItem(item); self._scene_items.append(item)
            loop_b = np.vstack([ring_bot, ring_bot[:1]])
            item = gl.GLLinePlotItem(pos=loop_b.astype(float), color=bot_color, width=bot_w, mode="line_strip")
            self._view.addItem(item); self._scene_items.append(item)
            for i in range(0, n_seg, n_seg // 4):
                pts = np.array([ring_bot[i], ring_top[i]], dtype=float)
                item = gl.GLLinePlotItem(pos=pts, color=side_color, width=side_w, mode="lines")
                self._view.addItem(item); self._scene_items.append(item)
        else:
            alpha = 0.25 if self._view_mode == "transparent" else 0.5
            normal_color = (*color, alpha)
            highlight_color = (*_hl, min(alpha + 0.3, 0.8))
            verts_list = list(ring_top) + list(ring_bot) + [top_center, bot_center]
            verts = np.array(verts_list, dtype=float)
            faces_list = []
            face_groups = []
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                faces_list.append([i, ni, ni + n_seg])
                face_groups.append("side")
                faces_list.append([i, ni + n_seg, i + n_seg])
                face_groups.append("side")
            tc_idx = n_seg * 2
            bc_idx = n_seg * 2 + 1
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                faces_list.append([tc_idx, ni, i])
                face_groups.append("top_cap")
                faces_list.append([bc_idx, i + n_seg, ni + n_seg])
                face_groups.append("bottom_cap")
            faces = np.array(faces_list, dtype=int)
            colors = np.array([
                highlight_color if selected_face is not None and g == selected_face else normal_color
                for g in face_groups
            ], dtype=float)
            mesh = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                                 smooth=True, drawEdges=True, edgeColor=edge_color)
            mesh.setGLOptions("translucent")
            self._view.addItem(mesh)
            self._scene_items.append(mesh)

    def _draw_solid_prism(self, prism, color, edge_color, selected_face=None):
        """Render a SolidPrism as a faceted mesh or wireframe."""
        import math
        axis = np.asarray(prism.axis, float)
        ref = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(axis, ref)) > 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        u = np.cross(axis, ref)
        u = u / np.linalg.norm(u)
        v = np.cross(axis, u)
        v = v / np.linalg.norm(v)

        n = prism.n_sides
        R = prism.circumscribed_radius
        half = prism.length / 2.0
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        top_center = prism.center + axis * half
        bot_center = prism.center - axis * half

        ring_top = top_center[None, :] + R * (
            np.cos(angles)[:, None] * u[None, :] + np.sin(angles)[:, None] * v[None, :]
        )
        ring_bot = bot_center[None, :] + R * (
            np.cos(angles)[:, None] * u[None, :] + np.sin(angles)[:, None] * v[None, :]
        )

        _hl = (1.0, 1.0, 0.0)

        if self._view_mode == "wireframe":
            top_color = (*_hl, 1.0) if selected_face == "cap_top" else edge_color
            bot_color = (*_hl, 1.0) if selected_face == "cap_bottom" else edge_color
            top_w = 4 if selected_face == "cap_top" else 2
            bot_w = 4 if selected_face == "cap_bottom" else 2
            loop_t = np.vstack([ring_top, ring_top[:1]])
            item = gl.GLLinePlotItem(pos=loop_t.astype(float), color=top_color, width=top_w, mode="line_strip")
            self._view.addItem(item); self._scene_items.append(item)
            loop_b = np.vstack([ring_bot, ring_bot[:1]])
            item = gl.GLLinePlotItem(pos=loop_b.astype(float), color=bot_color, width=bot_w, mode="line_strip")
            self._view.addItem(item); self._scene_items.append(item)
            for i in range(n):
                is_side_sel = selected_face == f"side_{i}"
                s_color = (*_hl, 1.0) if is_side_sel else edge_color
                s_w = 4 if is_side_sel else 2
                ni = (i + 1) % n
                for pts in [
                    np.array([ring_bot[i], ring_top[i]], dtype=float),
                    np.array([ring_top[i], ring_top[ni]], dtype=float),
                    np.array([ring_bot[i], ring_bot[ni]], dtype=float),
                ]:
                    item = gl.GLLinePlotItem(pos=pts, color=s_color, width=s_w, mode="lines")
                    self._view.addItem(item); self._scene_items.append(item)
        else:
            alpha = 0.25 if self._view_mode == "transparent" else 0.5
            normal_color = (*color, alpha)
            highlight_color = (*_hl, min(alpha + 0.3, 0.8))
            verts_list = list(ring_top) + list(ring_bot) + [top_center, bot_center]
            verts = np.array(verts_list, dtype=float)
            faces_list = []
            face_groups = []
            for i in range(n):
                ni = (i + 1) % n
                faces_list.append([i, ni, ni + n])
                face_groups.append(f"side_{i}")
                faces_list.append([i, ni + n, i + n])
                face_groups.append(f"side_{i}")
            tc_idx = n * 2
            bc_idx = n * 2 + 1
            for i in range(n):
                ni = (i + 1) % n
                faces_list.append([tc_idx, ni, i])
                face_groups.append("cap_top")
                faces_list.append([bc_idx, i + n, ni + n])
                face_groups.append("cap_bottom")
            faces = np.array(faces_list, dtype=int)
            colors = np.array([
                highlight_color if selected_face is not None and g == selected_face else normal_color
                for g in face_groups
            ], dtype=float)
            mesh = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                                 smooth=False, drawEdges=True, edgeColor=edge_color)
            mesh.setGLOptions("translucent")
            self._view.addItem(mesh)
            self._scene_items.append(mesh)

    def _draw_farfield_lobe(self, sd, result):
        """Render a 3D intensity lobe for far-field sphere detector results.

        The lobe is a color-mapped mesh surface centered at sd.center
        where the radius at each (theta, phi) direction is proportional to
        the candela value, using a cool-to-warm colormap.
        """
        if result.candela_grid is None:
            return
        grid = np.asarray(result.candela_grid, dtype=float)
        n_theta, n_phi = grid.shape
        peak = grid.max()
        if peak <= 0:
            return

        # Scale so peak radius = sd.radius * 0.8
        scale = sd.radius * 0.8 / peak
        norm_grid = grid / peak  # normalized [0,1] for coloring

        # Build (theta, phi) angles
        theta = (np.arange(n_theta) + 0.5) * np.pi / n_theta
        phi = np.arange(n_phi) * 2.0 * np.pi / n_phi

        # Build vertex grid
        # Shape: (n_theta, n_phi, 3)
        sin_t = np.sin(theta)[:, None]
        cos_t = np.cos(theta)[:, None]
        cos_p = np.cos(phi)[None, :]
        sin_p = np.sin(phi)[None, :]

        r = grid * scale  # (n_theta, n_phi) radii
        cx, cy, cz = sd.center
        vx = r * sin_t * cos_p + cx
        vy = r * sin_t * sin_p + cy
        vz = r * cos_t + cz

        verts = np.stack([vx, vy, vz], axis=-1)  # (n_theta, n_phi, 3)
        verts_flat = verts.reshape(-1, 3)         # (n_theta*n_phi, 3)

        # Build face indices (quads split into 2 triangles)
        faces_list = []
        for ti in range(n_theta - 1):
            for pi in range(n_phi):
                pn = (pi + 1) % n_phi
                v00 = ti * n_phi + pi
                v01 = ti * n_phi + pn
                v10 = (ti + 1) * n_phi + pi
                v11 = (ti + 1) * n_phi + pn
                faces_list.append([v00, v01, v11])
                faces_list.append([v00, v11, v10])
        faces = np.array(faces_list, dtype=int)

        # Color each face by normalized candela of the first vertex
        def _cool_warm(t):
            """Map t in [0,1] to RGBA using a cool-to-warm colormap."""
            # Keypoints: blue(0) -> cyan(0.25) -> green(0.5) -> yellow(0.75) -> red(1)
            r_keys = np.array([0.2, 0.2, 0.2, 1.0, 1.0])
            g_keys = np.array([0.2, 0.7, 1.0, 1.0, 0.2])
            b_keys = np.array([1.0, 1.0, 0.2, 0.2, 0.2])
            xp = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
            r_c = np.interp(t, xp, r_keys)
            g_c = np.interp(t, xp, g_keys)
            b_c = np.interp(t, xp, b_keys)
            a_c = np.full_like(t, 0.8)
            return np.stack([r_c, g_c, b_c, a_c], axis=-1)

        # Per-face color from average of three vertex t-values
        n_faces = len(faces)
        face_t = np.zeros(n_faces, dtype=float)
        norm_flat = norm_grid.reshape(-1)
        for fi in range(n_faces):
            v0, v1, v2 = faces[fi]
            face_t[fi] = (norm_flat[v0] + norm_flat[v1] + norm_flat[v2]) / 3.0
        # Gamma compression to spread color range across the full cool-to-warm map
        face_t = np.power(np.clip(face_t, 0.0, 1.0), 0.35)
        colors = _cool_warm(face_t)

        mesh = gl.GLMeshItem(
            vertexes=verts_flat.astype(np.float32),
            faces=faces,
            faceColors=colors.astype(np.float32),
            smooth=False,
            drawEdges=False,
        )
        mesh.setGLOptions("translucent")
        self._view.addItem(mesh)
        self._farfield_lobe_item = mesh

    def clear_farfield_lobe(self):
        """Remove the far-field intensity lobe mesh if present."""
        if self._farfield_lobe_item is not None:
            try:
                self._view.removeItem(self._farfield_lobe_item)
            except Exception:
                pass
            self._farfield_lobe_item = None

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
