"""Undo commands for Rectangle (surface) mutations."""

import copy
from PySide6.QtGui import QUndoCommand

from backlight_sim.gui.commands.base import ProjectCommand


class AddSurfaceCommand(ProjectCommand):
    """Add a Rectangle to project.surfaces."""

    def __init__(self, project, surface, refresh_fn):
        super().__init__(f"Add {surface.name}", project, refresh_fn)
        self._surface = surface

    def redo(self):
        self._project.surfaces.append(self._surface)
        self._refresh()

    def undo(self):
        self._project.surfaces = [s for s in self._project.surfaces if s.name != self._surface.name]
        self._refresh()


class DeleteSurfaceCommand(ProjectCommand):
    """Remove a Rectangle from project.surfaces, storing its index for undo re-insertion."""

    def __init__(self, project, surface, index: int, refresh_fn):
        super().__init__(f"Delete {surface.name}", project, refresh_fn)
        self._surface = surface
        self._index = index

    def redo(self):
        self._project.surfaces = [s for s in self._project.surfaces if s.name != self._surface.name]
        self._refresh()

    def undo(self):
        self._project.surfaces.insert(self._index, self._surface)
        self._refresh()


class SetSurfacePropertyCommand(QUndoCommand):
    """Set a single attribute on a Rectangle, with merge support for rapid edits.

    Merge policy: consecutive commands on the same surface object + same attribute
    are merged into a single undo step.
    """

    def __init__(self, surface, attr: str, old_val, new_val, refresh_fn):
        super().__init__(f"Edit {surface.name}.{attr}")
        self._surface = surface
        self._attr = attr
        self._old_val = copy.deepcopy(old_val)
        self._new_val = copy.deepcopy(new_val)
        self._refresh = refresh_fn

    def id(self) -> int:  # noqa: A003
        return hash((id(self._surface), self._attr)) & 0x7FFFFFFF

    def mergeWith(self, other: "QUndoCommand") -> bool:
        if not isinstance(other, SetSurfacePropertyCommand):
            return False
        if id(self._surface) != id(other._surface) or self._attr != other._attr:
            return False
        self._new_val = copy.deepcopy(other._new_val)
        return True

    def redo(self):
        setattr(self._surface, self._attr, copy.deepcopy(self._new_val))
        self._refresh()

    def undo(self):
        setattr(self._surface, self._attr, copy.deepcopy(self._old_val))
        self._refresh()
