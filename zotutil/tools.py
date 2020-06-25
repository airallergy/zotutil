from pathlib import Path
from sys import platform


def remove_empty_directories(root_directory):
    root_directory = Path(root_directory)
    if platform == "darwin":  # Windonws equivalent desktop.ini?
        remove_ds_store(root_directory)
    directories = tuple(item for item in root_directory.iterdir() if item.is_dir())
    for directory in directories:
        if not tuple(directory.glob("*")):
            directory.rmdir()
        else:
            remove_empty_directories(directory)
    if not tuple(root_directory.glob("*")):
        root_directory.rmdir()


def remove_ds_store(root_directory):
    root_directory = Path(root_directory)
    for path in root_directory.glob("**/.DS_Store"):
        path.unlink()
