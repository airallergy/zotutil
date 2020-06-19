from pathlib import Path
import sys


def remove_empty_directories(root_directory):
    root_directory = Path(root_directory)
    if sys.platform == "darwin":
        remove_ds_store(root_directory)
    for directory in tuple(item for item in root_directory.iterdir() if item.is_dir()):
        if len(list(directory.glob("*"))) == 0:
            directory.rmdir()
        else:
            remove_empty_directories(directory)


def remove_ds_store(root_directory):
    root_directory = Path(root_directory)
    for path in root_directory.glob("**/.DS_Store"):
        path.unlink()
