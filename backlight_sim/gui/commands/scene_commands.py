"""Undo commands for detectors, materials, optical properties, and solid bodies."""

import copy
from PySide6.QtGui import QUndoCommand

from backlight_sim.gui.commands.base import ProjectCommand


# ---------------------------------------------------------------------------
# Generic property command (works on any object with setattr)
# ---------------------------------------------------------------------------

class SetPropertyCommand(QUndoCommand):
    """Generic single-attribute set with merge support.

    Works on any object (PointSource, Rectangle, Material, etc.).
    Merge policy: consecutive commands on the same object + same attribute collapse.
    """

    def __init__(self, target_obj, attr: str, old_val, new_val, refresh_fn):
        obj_name = getattr(target_obj, "name", repr(target_obj))
        super().__init__(f"Edit {obj_name}.{attr}")
        self._obj = target_obj
        self._attr = attr
        self._old_val = copy.deepcopy(old_val)
        self._new_val = copy.deepcopy(new_val)
        self._refresh = refresh_fn

    def id(self) -> int:  # noqa: A003
        return hash((id(self._obj), self._attr)) & 0x7FFFFFFF

    def mergeWith(self, other: "QUndoCommand") -> bool:
        if not isinstance(other, SetPropertyCommand):
            return False
        if id(self._obj) != id(other._obj) or self._attr != other._attr:
            return False
        self._new_val = copy.deepcopy(other._new_val)
        return True

    def redo(self):
        setattr(self._obj, self._attr, copy.deepcopy(self._new_val))
        self._refresh()

    def undo(self):
        setattr(self._obj, self._attr, copy.deepcopy(self._old_val))
        self._refresh()


# ---------------------------------------------------------------------------
# Detector commands
# ---------------------------------------------------------------------------

class AddDetectorCommand(ProjectCommand):
    """Add a DetectorSurface to project.detectors."""

    def __init__(self, project, detector, refresh_fn):
        super().__init__(f"Add {detector.name}", project, refresh_fn)
        self._detector = detector

    def redo(self):
        self._project.detectors.append(self._detector)
        self._refresh()

    def undo(self):
        self._project.detectors = [d for d in self._project.detectors if d.name != self._detector.name]
        self._refresh()


class DeleteDetectorCommand(ProjectCommand):
    """Remove a DetectorSurface from project.detectors."""

    def __init__(self, project, detector, index: int, refresh_fn):
        super().__init__(f"Delete {detector.name}", project, refresh_fn)
        self._detector = detector
        self._index = index

    def redo(self):
        self._project.detectors = [d for d in self._project.detectors if d.name != self._detector.name]
        self._refresh()

    def undo(self):
        self._project.detectors.insert(self._index, self._detector)
        self._refresh()


# ---------------------------------------------------------------------------
# Sphere Detector commands
# ---------------------------------------------------------------------------

class AddSphereDetectorCommand(ProjectCommand):
    """Add a SphereDetector to project.sphere_detectors."""

    def __init__(self, project, detector, refresh_fn):
        super().__init__(f"Add {detector.name}", project, refresh_fn)
        self._detector = detector

    def redo(self):
        self._project.sphere_detectors.append(self._detector)
        self._refresh()

    def undo(self):
        self._project.sphere_detectors = [
            d for d in self._project.sphere_detectors if d.name != self._detector.name
        ]
        self._refresh()


class DeleteSphereDetectorCommand(ProjectCommand):
    """Remove a SphereDetector from project.sphere_detectors."""

    def __init__(self, project, detector, index: int, refresh_fn):
        super().__init__(f"Delete {detector.name}", project, refresh_fn)
        self._detector = detector
        self._index = index

    def redo(self):
        self._project.sphere_detectors = [
            d for d in self._project.sphere_detectors if d.name != self._detector.name
        ]
        self._refresh()

    def undo(self):
        self._project.sphere_detectors.insert(self._index, self._detector)
        self._refresh()


# ---------------------------------------------------------------------------
# Material commands (dict-based)
# ---------------------------------------------------------------------------

class AddMaterialCommand(ProjectCommand):
    """Add a Material to project.materials dict."""

    def __init__(self, project, name: str, material, refresh_fn):
        super().__init__(f"Add {name}", project, refresh_fn)
        self._name = name
        self._material = material

    def redo(self):
        self._project.materials[self._name] = self._material
        self._refresh()

    def undo(self):
        self._project.materials.pop(self._name, None)
        self._refresh()


class DeleteMaterialCommand(ProjectCommand):
    """Remove a Material from project.materials dict."""

    def __init__(self, project, name: str, material, refresh_fn):
        super().__init__(f"Delete {name}", project, refresh_fn)
        self._name = name
        self._material = material

    def redo(self):
        self._project.materials.pop(self._name, None)
        self._refresh()

    def undo(self):
        self._project.materials[self._name] = self._material
        self._refresh()


# ---------------------------------------------------------------------------
# Optical Properties commands (dict-based)
# ---------------------------------------------------------------------------

class AddOpticalPropertiesCommand(ProjectCommand):
    """Add an OpticalProperties entry to project.optical_properties dict."""

    def __init__(self, project, name: str, opt_props, refresh_fn):
        super().__init__(f"Add {name}", project, refresh_fn)
        self._name = name
        self._opt_props = opt_props

    def redo(self):
        self._project.optical_properties[self._name] = self._opt_props
        self._refresh()

    def undo(self):
        self._project.optical_properties.pop(self._name, None)
        self._refresh()


class DeleteOpticalPropertiesCommand(ProjectCommand):
    """Remove an OpticalProperties entry from project.optical_properties dict."""

    def __init__(self, project, name: str, opt_props, refresh_fn):
        super().__init__(f"Delete {name}", project, refresh_fn)
        self._name = name
        self._opt_props = opt_props

    def redo(self):
        self._project.optical_properties.pop(self._name, None)
        self._refresh()

    def undo(self):
        self._project.optical_properties[self._name] = self._opt_props
        self._refresh()


# ---------------------------------------------------------------------------
# Solid body commands
# ---------------------------------------------------------------------------

_SOLID_BODY_ATTR_MAP = {
    "box": "solid_bodies",
    "cylinder": "solid_cylinders",
    "prism": "solid_prisms",
}


class AddSolidBodyCommand(ProjectCommand):
    """Add a solid body (box/cylinder/prism) to the appropriate project list.

    body_type: "box" | "cylinder" | "prism"
    """

    def __init__(self, project, body, body_type: str, refresh_fn):
        super().__init__(f"Add {body.name}", project, refresh_fn)
        self._body = body
        self._body_type = body_type
        self._list_attr = _SOLID_BODY_ATTR_MAP[body_type]

    def _get_list(self):
        return getattr(self._project, self._list_attr, [])

    def _set_list(self, lst):
        setattr(self._project, self._list_attr, lst)

    def redo(self):
        lst = self._get_list()
        lst.append(self._body)
        self._refresh()

    def undo(self):
        lst = self._get_list()
        self._set_list([b for b in lst if b.name != self._body.name])
        self._refresh()


class DeleteSolidBodyCommand(ProjectCommand):
    """Remove a solid body from the appropriate project list."""

    def __init__(self, project, body, body_type: str, index: int, refresh_fn):
        super().__init__(f"Delete {body.name}", project, refresh_fn)
        self._body = body
        self._body_type = body_type
        self._index = index
        self._list_attr = _SOLID_BODY_ATTR_MAP[body_type]

    def _get_list(self):
        return getattr(self._project, self._list_attr, [])

    def _set_list(self, lst):
        setattr(self._project, self._list_attr, lst)

    def redo(self):
        lst = self._get_list()
        self._set_list([b for b in lst if b.name != self._body.name])
        self._refresh()

    def undo(self):
        lst = self._get_list()
        lst.insert(self._index, self._body)
        self._refresh()


# ---------------------------------------------------------------------------
# Batch command (macro wrapper)
# ---------------------------------------------------------------------------

class BatchCommand(QUndoCommand):
    """Macro wrapper: groups multiple commands into a single undo step.

    Usage:
        batch = BatchCommand("Build Cavity")
        batch.add(AddSurfaceCommand(...))
        batch.add(AddSurfaceCommand(...))
        stack.push(batch)
    """

    def __init__(self, description: str):
        super().__init__(description)
        self._commands: list[QUndoCommand] = []

    def add(self, cmd: QUndoCommand):
        self._commands.append(cmd)

    def redo(self):
        for cmd in self._commands:
            cmd.redo()

    def undo(self):
        for cmd in reversed(self._commands):
            cmd.undo()
