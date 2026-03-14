"""Undo/redo command classes for scene mutations.

All commands follow the QUndoCommand pattern:
- redo() performs the mutation
- undo() reverses it
- QUndoStack.push() calls redo() automatically — do NOT call it in __init__
"""

from backlight_sim.gui.commands.base import ProjectCommand
from backlight_sim.gui.commands.source_commands import (
    AddSourceCommand,
    DeleteSourceCommand,
    SetSourcePropertyCommand,
)
from backlight_sim.gui.commands.surface_commands import (
    AddSurfaceCommand,
    DeleteSurfaceCommand,
    SetSurfacePropertyCommand,
)
from backlight_sim.gui.commands.scene_commands import (
    SetPropertyCommand,
    AddDetectorCommand,
    DeleteDetectorCommand,
    AddSphereDetectorCommand,
    DeleteSphereDetectorCommand,
    AddMaterialCommand,
    DeleteMaterialCommand,
    AddOpticalPropertiesCommand,
    DeleteOpticalPropertiesCommand,
    AddSolidBodyCommand,
    DeleteSolidBodyCommand,
    BatchCommand,
)

__all__ = [
    "ProjectCommand",
    "AddSourceCommand",
    "DeleteSourceCommand",
    "SetSourcePropertyCommand",
    "AddSurfaceCommand",
    "DeleteSurfaceCommand",
    "SetSurfacePropertyCommand",
    "SetPropertyCommand",
    "AddDetectorCommand",
    "DeleteDetectorCommand",
    "AddSphereDetectorCommand",
    "DeleteSphereDetectorCommand",
    "AddMaterialCommand",
    "DeleteMaterialCommand",
    "AddOpticalPropertiesCommand",
    "DeleteOpticalPropertiesCommand",
    "AddSolidBodyCommand",
    "DeleteSolidBodyCommand",
    "BatchCommand",
]
