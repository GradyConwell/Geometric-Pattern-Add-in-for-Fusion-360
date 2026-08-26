import sys
import traceback
import adsk.core

app = adsk.core.Application.get()
ui = app.userInterface if app else None


def log(message: str, level: adsk.core.LogLevels = adsk.core.LogLevels.InfoLogLevel, force_console: bool = False):
    """Utility function to log messages to the Fusion 360 TEXT COMMANDS palette."""
    if app:
        app.log(f'[GeometricPattern] {message}', level)

    if force_console:
        print(f'[GeometricPattern] {message}')


def handle_error(name: str = 'Error', show_message_box: bool = True):
    """Utility function to report and log errors."""
    log_msg = f'Failed:\n{traceback.format_exc()}'
    log(f'{name} {log_msg}', adsk.core.LogLevels.ErrorLogLevel, True)
    if show_message_box and ui:
        ui.messageBox(f'{name} encountered an error:\n{traceback.format_exc()}')
