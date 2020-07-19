from pathlib import Path


def remove_empty_directories(root_directory):
    ignore_files = (".DS_Store", "desktop.ini", "Thumbs.db")
    root_directory = Path(root_directory)
    directories = tuple(item for item in root_directory.iterdir() if item.is_dir())
    for directory in directories:
        if set(item.name for item in directory.glob("*")) < set(ignore_files):
            remove_directory(directory)
        else:
            remove_empty_directories(directory)
    if set(item.name for item in root_directory.glob("*")) < set(ignore_files):
        remove_directory(root_directory)


def remove_directory(directory):
    # the target directory should contains no subdirectories
    for path in directory.glob("*"):
        path.unlink()
    directory.rmdir()
