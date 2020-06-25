import pytest

from sys import platform
from pathlib import PurePath

from zotutil.tools import *


def tmp_file_sys(root_path):
    """
    pytest-*/*
    ├── folder_0
    │   ├── folder_0_0
    │   └── file_0_0.txt
    ├── folder_1
    │   └── folder_1_0
    │       └── (.DS_Store)
    ├── (.DS_Store)
    └── file_0.txt

    """
    paths_parts = (
        ("folder_0", "folder_0_0"),
        ("folder_0", "file_0_0.txt"),
        ("folder_1", "folder_1_0", ".DS_Store"),
        (".DS_Store",),
        ("file_0.txt",),
    )

    for path_parts in paths_parts:
        path = root_path
        for path_part in path_parts:
            if (path_part == ".DS_Store") and (platform != "darwin"):
                if path == root_path:
                    continue
                else:
                    if not path.is_dir():
                        path.mkdir()
                    break
            path /= path_part
            if "." in path_part:
                with path.open("wt") as fh:
                    pass
            else:
                if not path.is_dir():
                    path.mkdir()


def test_remove_empty_directories(tmp_path):
    tmp_file_sys(tmp_path)
    remove_empty_directories(tmp_path)
    test_cases = (
        (PurePath(""), True),
        (PurePath("folder_0", "folder_0_0"), False),
        (PurePath("folder_0"), True),
        (PurePath("folder_1"), False),
    )
    for sub_path, expected in test_cases:
        assert (tmp_path / sub_path).is_dir() == expected
