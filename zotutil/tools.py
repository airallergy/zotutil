from pathlib import Path
import sys


def remove_empty_directories(root_directory, parent_directory=None):
    root_directory = Path(root_directory)
    if parent_directory:
        parent_directory = Path(parent_directory)
    else:
        parent_directory = root_directory
    if sys.platform == "darwin":
        remove_ds_store(parent_directory)
    for directory in tuple(
        item for item in parent_directory.iterdir() if item.is_dir()
    ):
        if not tuple(directory.glob("*")):
            directory.rmdir()
            if root_directory <= parent_directory.parent:
                remove_empty_directories(root_directory, parent_directory.parent)
        else:
            remove_empty_directories(root_directory, directory)


def remove_ds_store(root_directory):
    root_directory = Path(root_directory)
    for path in root_directory.glob("**/.DS_Store"):
        path.unlink()
