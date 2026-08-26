from . import geometricPattern

commands = [
    geometricPattern
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
