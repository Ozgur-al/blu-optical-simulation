"""Undo commands for PointSource mutations."""

import copy
from PySide6.QtGui import QUndoCommand

from backlight_sim.gui.commands.base import ProjectCommand


class AddSourceCommand(ProjectCommand):
    """Add a PointSource to project.sources."""

    def __init__(self, project, source, refresh_fn):
        super().__init__(f"Add {source.name}", project, refresh_fn)
        self._source = source

    def redo(self):
        self._project.sources.append(self._source)
        self._refresh()

    def undo(self):
        self._project.sources = [s for s in self._project.sources if s.name != self._source.name]
        self._refresh()


class DeleteSourceCommand(ProjectCommand):
    """Remove a PointSource from project.sources, storing its index for undo re-insertion."""

    def __init__(self, project, source, index: int, refresh_fn):
        super().__init__(f"Delete {source.name}", project, refresh_fn)
        self._source = source
        self._index = index

    def redo(self):
        self._project.sources = [s for s in self._project.sources if s.name != self._source.name]
        self._refresh()

    def undo(self):
        self._project.sources.insert(self._index, self._source)
        self._refresh()


class SetSourcePropertyCommand(QUndoCommand):
    """Set a single attribute on a PointSource, with merge support for rapid edits.

    Merge policy: consecutive commands on the same source object + same attribute
    are merged into a single undo step (e.g. slider drag → single undo).
    """

    def __init__(self, source, attr: str, old_val, new_val, refresh_fn):
        super().__init__(f"Edit {source.name}.{attr}")
        self._source = source
        self._attr = attr
        self._old_val = copy.deepcopy(old_val)
        self._new_val = copy.deepcopy(new_val)
        self._refresh = refresh_fn

    def id(self) -> int:  # noqa: A003
        """Used by Qt to decide whether mergeWith() should be called."""
        return hash((id(self._source), self._attr)) & 0x7FFFFFFF  # keep positive int

    def mergeWith(self, other: "QUndoCommand") -> bool:
        """Merge: keep old_val from self, take new_val from other."""
        if not isinstance(other, SetSourcePropertyCommand):
            return False
        if id(self._source) != id(other._source) or self._attr != other._attr:
            return False
        self._new_val = copy.deepcopy(other._new_val)
        return True

    def redo(self):
        setattr(self._source, self._attr, copy.deepcopy(self._new_val))
        self._refresh()

    def undo(self):
        setattr(self._source, self._attr, copy.deepcopy(self._old_val))
        self._refresh()
