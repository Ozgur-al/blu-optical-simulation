"""Base class for all project-mutating undo commands."""

from PySide6.QtGui import QUndoCommand  # NOTE: Qt6 moved QUndoCommand to QtGui, NOT QtWidgets


class ProjectCommand(QUndoCommand):
    """Base for all project-mutating commands.

    Subclasses must implement redo() and undo().
    The constructor must NOT perform the mutation — QUndoStack.push() calls redo() automatically.
    """

    def __init__(self, description: str, project, refresh_fn):
        super().__init__(description)
        self._project = project
        self._refresh = refresh_fn
