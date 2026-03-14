# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Blu Optical Simulation
#
# Build with:   python build_exe.py
#           or: pyinstaller BluOpticalSim.spec

import sys
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Source tree root
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH)

# ---------------------------------------------------------------------------
# Hidden imports that PyInstaller cannot auto-detect
# ---------------------------------------------------------------------------
hidden_imports = [
    # PySide6 OpenGL support
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    # pyqtgraph internals
    "pyqtgraph.opengl",
    "pyqtgraph.opengl.items",
    "pyqtgraph.opengl.items.GLMeshItem",
    "pyqtgraph.opengl.items.GLLinePlotItem",
    "pyqtgraph.opengl.items.GLGridItem",
    "pyqtgraph.opengl.items.GLScatterPlotItem",
    "pyqtgraph.opengl.items.GLSurfacePlotItem",
    "pyqtgraph.opengl.GLViewWidget",
    "pyqtgraph.graphicsItems.ColorBarItem",
    "pyqtgraph.graphicsItems.ImageItem",
    # PyOpenGL
    "OpenGL",
    "OpenGL.GL",
    "OpenGL.GLU",
    "OpenGL.platform",
    "OpenGL.platform.win32",
    "OpenGL.platform.darwin",
    "OpenGL.platform.glx",
    # numpy internals sometimes missed
    "numpy.core._methods",
    "numpy.lib.format",
    # Numba JIT acceleration (optional — app works without it)
    # Note: pyinstaller-hooks-contrib >= 2025.1 handles Numba's _RedirectSubpackage
    # modules automatically. Install it alongside PyInstaller when building with Numba.
    "numba",
    "numba.core",
    "numba.typed",
    "numba.np",
    "numba.np.ufunc",
    "llvmlite",
    "llvmlite.binding",
]

# ---------------------------------------------------------------------------
# Data files to bundle (non-Python assets)
# ---------------------------------------------------------------------------
datas = [
    # Built-in angular distribution CSV profiles
    (str(ROOT / "backlight_sim" / "data"), "backlight_sim/data"),
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy unused packages to keep bundle size down
        "matplotlib",
        "tkinter",
        "unittest",
        "xmlrpc",
        "email",
        "html",
        "http",
        "urllib",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BluOpticalSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Uncomment and provide an .ico file to set app icon
)

# ---------------------------------------------------------------------------
# COLLECT — one-folder distribution (easier to zip and ship)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BluOpticalSim",
)
