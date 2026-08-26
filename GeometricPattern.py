# Geometric Pattern Fusion 360 Add-in Entry Point
from . import commands
from .lib import fusionAddInUtils as futil


def run(context):
    """Called by Fusion 360 when the add-in is started."""
    try:
        commands.start()
    except:
        futil.handle_error('run')


def stop(context):
    """Called by Fusion 360 when the add-in is stopped or unloaded."""
    try:
        # Clear global handlers
        futil.clear_handlers()

        # Stop command controls and definitions
        commands.stop()
    except:
        futil.handle_error('stop')
