"""3D OpenGL viewport - scene preview, selection highlight, and view modes."""

from __future__ import annotations

import datetime

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from backlight_sim.gui.theme import GL_BG

_PANEL_SS = (
    "background-color: #1d1b18; border: 1px solid #48433e; border-radius: 8px;"
)
_HDR_SS = (
    "color: #807c74; font-size: 8pt; font-weight: 600;"
    "font-family: 'JetBrains Mono', 'Consolas', monospace;"
    "letter-spacing: 1px; background: transparent;"
)
_VAL_SS = "color: #f1ede4; font-size: 9pt; background: transparent; font-family: 'JetBrains Mono', 'Consolas', monospace;"
_MUT_SS = "color: #807c74; font-size: 8pt; background: transparent;"


class Viewport3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = gl.GLViewWidget()
        self._view.setCameraPosition(distance=180, elevation=30, azimuth=45)
        # GLViewWidget uses OpenGL rendering and ignores QSS — set background explicitly
        self._view.setBackgroundColor(*GL_BG)
        layout.addWidget(self._view)

        self._grid = gl.GLGridItem()
        self._grid.setSize(2000, 2000)
        self._grid.setSpacing(50, 50)
        self._view.addItem(self._grid)

        self._axis_items: list = []
        self._add_reference_axes()

        self._scene_items: list = []
        self._cavity_items: list = []
        self._path_items: list = []
        self._farfield_lobe_item = None
        self._last_project = None
        self._selected_group: str | None = None
        self._selected_name: str | None = None
        self._view_mode = "wireframe"
        self._default_distance = 180

        self._setup_hud()
        self._setup_legend_bar()

    # ── HUD overlay ───────────────────────────────────────────────────────

    def _make_panel(self, parent: QWidget) -> tuple[QFrame, QGridLayout]:
        panel = QFrame(parent)
        panel.setStyleSheet(_PANEL_SS)
        panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QGridLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        return panel, layout

    def _setup_hud(self):
        # ── Sim panel (top-left) ─────────────────────────────────────────
        self._hud_sim, sl = self._make_panel(self)
        self._hud_sim_header = QLabel("● SIMULATION · 00:00:00")
        self._hud_sim_header.setStyleSheet(_HDR_SS)
        sl.addWidget(self._hud_sim_header, 0, 0, 1, 2)
        for row, (lbl_text, attr) in enumerate([
            ("Rays traced", "_hud_rays_val"),
            ("Convergence", "_hud_cv_val"),
        ], 1):
            lbl = QLabel(lbl_text); lbl.setStyleSheet(_MUT_SS)
            val = QLabel("—"); val.setStyleSheet(_VAL_SS)
            setattr(self, attr, val)
            sl.addWidget(lbl, row, 0); sl.addWidget(val, row, 1)
        self._hud_sim.hide()

        # ── Scene panel (top-right) ──────────────────────────────────────
        self._hud_scene, scl = self._make_panel(self)
        scene_hdr = QLabel("SCENE"); scene_hdr.setStyleSheet(_HDR_SS)
        scl.addWidget(scene_hdr, 0, 0, 1, 2)
        for row, (lbl_text, attr) in enumerate([
            ("Sources",  "_hud_src_val"),
            ("Surfaces", "_hud_surf_val"),
            ("Detectors","_hud_det_val"),
        ], 1):
            lbl = QLabel(lbl_text); lbl.setStyleSheet(_MUT_SS)
            val = QLabel("0"); val.setStyleSheet(_VAL_SS)
            setattr(self, attr, val)
            scl.addWidget(lbl, row, 0); scl.addWidget(val, row, 1)

        # ── Camera panel (bottom-right) ──────────────────────────────────
        self._hud_cam, ccl = self._make_panel(self)
        cam_hdr = QLabel("CAMERA · orbit"); cam_hdr.setStyleSheet(_HDR_SS)
        ccl.addWidget(cam_hdr, 0, 0, 1, 2)
        for row, (lbl_text, attr) in enumerate([
            ("Azimuth",   "_hud_az_val"),
            ("Elevation", "_hud_el_val"),
            ("Distance",  "_hud_dist_val"),
        ], 1):
            lbl = QLabel(lbl_text); lbl.setStyleSheet(_MUT_SS)
            val = QLabel("—"); val.setStyleSheet(_VAL_SS)
            setattr(self, attr, val)
            ccl.addWidget(lbl, row, 0); ccl.addWidget(val, row, 1)

        # Sim elapsed-time state
        self._hud_sim_start: datetime.datetime | None = None
        self._hud_sim_elapsed = QTimer(self)
        self._hud_sim_elapsed.setInterval(1000)
        self._hud_sim_elapsed.timeout.connect(self._tick_sim_time)

        # Camera live update
        self._hud_cam_timer = QTimer(self)
        self._hud_cam_timer.setInterval(400)
        self._hud_cam_timer.timeout.connect(self._update_hud_camera)
        self._hud_cam_timer.start()

        self._position_hud()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_hud()

    def _position_hud(self):
        pad, w, h = 12, self.width(), self.height()
        if not hasattr(self, "_hud_sim"):
            return
        self._hud_sim.adjustSize()
        self._hud_scene.adjustSize()
        self._hud_cam.adjustSize()
        sw, sh = self._hud_sim.sizeHint().width(), self._hud_sim.sizeHint().height()
        scw, sch = self._hud_scene.sizeHint().width(), self._hud_scene.sizeHint().height()
        cw, ch = self._hud_cam.sizeHint().width(), self._hud_cam.sizeHint().height()
        self._hud_sim.setGeometry(pad, pad, max(sw, 180), max(sh, 90))
        self._hud_scene.setGeometry(w - max(scw, 160) - pad, pad, max(scw, 160), max(sch, 90))
        self._hud_cam.setGeometry(w - max(cw, 160) - pad, h - max(ch, 80) - pad, max(cw, 160), max(ch, 80))
        for panel in (self._hud_sim, self._hud_scene, self._hud_cam):
            panel.raise_()

    # ── HUD update API ────────────────────────────────────────────────────

    def update_hud_scene(self, project) -> None:
        if not hasattr(self, "_hud_src_val"):
            return
        self._hud_src_val.setText(str(len(project.sources)))
        self._hud_surf_val.setText(str(len(project.surfaces)))
        self._hud_det_val.setText(str(len(project.detectors)))

    def show_hud_sim(self, visible: bool) -> None:
        if not hasattr(self, "_hud_sim"):
            return
        if visible:
            self._hud_sim_start = datetime.datetime.now()
            self._hud_sim_header.setText("● SIMULATION · 00:00:00")
            self._hud_rays_val.setText("—")
            self._hud_cv_val.setText("—")
            self._hud_sim_elapsed.start()
            self._hud_sim.show()
            self._position_hud()
        else:
            self._hud_sim_elapsed.stop()

    def update_hud_sim(self, n_rays: int, cv_pct: float) -> None:
        if not hasattr(self, "_hud_rays_val"):
            return
        self._hud_rays_val.setText(f"{n_rays:,}")
        self._hud_cv_val.setText(f"{cv_pct:.1f} %")

    def _tick_sim_time(self) -> None:
        if self._hud_sim_start is None:
            return
        elapsed = datetime.datetime.now() - self._hud_sim_start
        total = int(elapsed.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        self._hud_sim_header.setText(f"● SIMULATION · {h:02d}:{m:02d}:{s:02d}")

    def _update_hud_camera(self) -> None:
        if not hasattr(self, "_hud_az_val"):
            return
        opts = self._view.opts
        self._hud_az_val.setText(f"{opts.get('azimuth', 0):.1f}°")
        self._hud_el_val.setText(f"{opts.get('elevation', 0):.1f}°")
        self._hud_dist_val.setText(f"{opts.get('distance', 0):.0f}")

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
            self._axis_items.append(axis_item)

    # ── Legend chip bar ───────────────────────────────────────────────────

    @staticmethod
    def _chip_ss(fg: str) -> str:
        return (
            f"QPushButton {{ background: #2d2a26; border: 1px solid #48433e;"
            f"border-radius: 10px; padding: 2px 10px; font-size: 8pt;"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"color: {fg}; min-height: 20px; }}"
            f"QPushButton:!checked {{ background: #1c1a18; border-color: #2f2c28; color: #4a4640; }}"
        )

    def _setup_legend_bar(self):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background: #272421; border-top: 1px solid #48433e;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 12, 0)
        bar_layout.setSpacing(6)

        for label, fg, handler, attr in [
            ("● Rays",   "#e8b04a", self._toggle_rays,  "_chip_rays"),
            ("⊙ Cavity", "#7ec3d6", self._toggle_cavity, "_chip_cavity"),
            ("▦ Grid",   "#807c74", self._toggle_grid,  "_chip_grid"),
            ("✕ Axes",   "#df7565", self._toggle_axes,  "_chip_axes"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setStyleSheet(self._chip_ss(fg))
            if handler:
                btn.toggled.connect(handler)
            bar_layout.addWidget(btn)
            setattr(self, attr, btn)

        bar_layout.addStretch(1)
        hint = QLabel("drag to orbit · scroll to zoom")
        hint.setStyleSheet(
            "color: #4a4640; font-size: 7pt;"
            "font-family: 'JetBrains Mono', Consolas, monospace; background: transparent;"
        )
        bar_layout.addWidget(hint)
        self.layout().addWidget(bar)

    def _toggle_rays(self, checked: bool) -> None:
        for item in self._path_items:
            item.setVisible(checked)

    def _toggle_cavity(self, checked: bool) -> None:
        for item in self._cavity_items:
            item.setVisible(checked)

    def _toggle_grid(self, checked: bool) -> None:
        self._grid.setVisible(checked)

    def _toggle_axes(self, checked: bool) -> None:
        for item in self._axis_items:
            item.setVisible(checked)

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

        _cav_start = len(self._scene_items)
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
        self._cavity_items = self._scene_items[_cav_start:]

        # Respect current chip state after rebuild
        if hasattr(self, "_chip_cavity") and not self._chip_cavity.isChecked():
            for item in self._cavity_items:
                item.setVisible(False)

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

        _hl_wire = (0.0, 1.0, 1.0)  # cyan for wireframe face highlight

        if self._view_mode == "wireframe":
            top_color = (*_hl_wire, 1.0) if selected_face == "top_cap" else edge_color
            bot_color = (*_hl_wire, 1.0) if selected_face == "bottom_cap" else edge_color
            side_color = (*_hl_wire, 1.0) if selected_face == "side" else edge_color
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
            highlight_color = (1.0, 1.0, 0.0, min(alpha + 0.3, 0.8))
            # Build separate meshes per face group so caps get flat shading
            verts_list = list(ring_top) + list(ring_bot) + [top_center, bot_center]
            verts = np.array(verts_list, dtype=float)
            tc_idx = n_seg * 2
            bc_idx = n_seg * 2 + 1
            # Group triangles by face
            groups = {"side": [], "top_cap": [], "bottom_cap": []}
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                groups["side"].append([i, ni, ni + n_seg])
                groups["side"].append([i, ni + n_seg, i + n_seg])
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                groups["top_cap"].append([tc_idx, ni, i])
                groups["bottom_cap"].append([bc_idx, i + n_seg, ni + n_seg])
            for gname, tri_list in groups.items():
                if not tri_list:
                    continue
                faces = np.array(tri_list, dtype=int)
                is_hl = selected_face is not None and gname == selected_face
                fc = highlight_color if is_hl else normal_color
                colors = np.array([fc] * len(faces), dtype=float)
                # Caps: smooth=False for flat shading; side: smooth=True
                smooth = gname == "side"
                mesh = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                                     smooth=smooth, drawEdges=True, edgeColor=edge_color)
                mesh.setGLOptions("translucent")
                self._view.addItem(mesh)
                self._scene_items.append(mesh)

    def _draw_solid_prism(self, prism, color, edge_color, selected_face=None):
        """Render a SolidPrism as a faceted mesh or wireframe."""
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

        _hl_wire = (0.0, 1.0, 1.0)  # cyan for wireframe face highlight

        if self._view_mode == "wireframe":
            top_color = (*_hl_wire, 1.0) if selected_face == "cap_top" else edge_color
            bot_color = (*_hl_wire, 1.0) if selected_face == "cap_bottom" else edge_color
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
                s_color = (*_hl_wire, 1.0) if is_side_sel else edge_color
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
            highlight_color = (1.0, 1.0, 0.0, min(alpha + 0.3, 0.8))
            verts_list = list(ring_top) + list(ring_bot) + [top_center, bot_center]
            verts = np.array(verts_list, dtype=float)
            tc_idx = n * 2
            bc_idx = n * 2 + 1
            # Group triangles by face
            groups: dict[str, list] = {}
            for i in range(n):
                ni = (i + 1) % n
                groups.setdefault(f"side_{i}", []).append([i, ni, ni + n])
                groups[f"side_{i}"].append([i, ni + n, i + n])
            for i in range(n):
                ni = (i + 1) % n
                groups.setdefault("cap_top", []).append([tc_idx, ni, i])
                groups.setdefault("cap_bottom", []).append([bc_idx, i + n, ni + n])
            for gname, tri_list in groups.items():
                if not tri_list:
                    continue
                faces = np.array(tri_list, dtype=int)
                is_hl = selected_face is not None and gname == selected_face
                fc = highlight_color if is_hl else normal_color
                colors = np.array([fc] * len(faces), dtype=float)
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

        # Per-face color from average of three vertex t-values (vectorized)
        norm_flat = norm_grid.reshape(-1)
        face_t = (norm_flat[faces[:, 0]] + norm_flat[faces[:, 1]] + norm_flat[faces[:, 2]]) / 3.0
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
            except RuntimeError:
                pass  # item already removed from scene
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
            color=(0.91, 0.69, 0.29, 0.45),  # #e8b04a amber
            width=1,
            mode="line_strip",
            antialias=True,
        )
        self._view.addItem(ray_item)
        self._path_items.append(ray_item)
        if hasattr(self, "_chip_rays"):
            self._chip_rays.setChecked(True)

    def clear_ray_paths(self):
        for item in self._path_items:
            self._view.removeItem(item)
        self._path_items.clear()
        if hasattr(self, "_chip_rays"):
            self._chip_rays.setChecked(False)


def _material_color(mat) -> tuple[float, float, float]:
    if mat is None or mat.color is None:
        return (0.55, 0.65, 1.0)
    return tuple(float(c) for c in mat.color[:3])


def _cool_warm(t):
    """Map t in [0,1] to RGBA using a cool-to-warm colormap.

    Keypoints: blue(0) -> cyan(0.25) -> green(0.5) -> yellow(0.75) -> red(1).
    """
    r_keys = np.array([0.2, 0.2, 0.2, 1.0, 1.0])
    g_keys = np.array([0.2, 0.7, 1.0, 1.0, 0.2])
    b_keys = np.array([1.0, 1.0, 0.2, 0.2, 0.2])
    xp = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    r_c = np.interp(t, xp, r_keys)
    g_c = np.interp(t, xp, g_keys)
    b_c = np.interp(t, xp, b_keys)
    a_c = np.full_like(t, 0.8)
    return np.stack([r_c, g_c, b_c, a_c], axis=-1)


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
