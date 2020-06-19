from pyzotero.zotero import Zotero
from configparser import ConfigParser
from pathlib import PurePath, Path
import re
import datetime as dt
import sys
from zipfile import ZipFile
from io import TextIOWrapper
import json

from .tools import remove_empty_directories

_ZOT_DEFAULT_INSTALLATION_PATHS_PARTS = {
    "darwin": ("/", "Applications", "Zotero.app", "Contents", "Resources"),
    "win32": ("C:\\", "Program Files (x86)", "Zotero"),
}

_ZOT_DEFAULT_PROFILE_RELATIVE_PATHS_PARTS = {
    "darwin": ("Library", "Application Support", "Zotero"),
    "win32": ("AppData", "Roaming", "Zotero", "Zotero"),
}


class Zot:
    """A Zotero library object.
    Default directories:
        installation directory:
            Mac: /Applications/Zotero.app/Contents/Resources
            Windows 10/8/7/Vista: C:\\Program Files (x86)\\Zotero
        profile directory:
            Mac: /Users/\<username\>/Library/Application Support/Zotero
            Windows 10/8/7/Vista: C:\\Users\\\<User Name\>\\AppData\\Roaming\\Zotero\\Zotero
    they need to be specified if customised.

    Parameters
    ----------
    library_id : str
        Zotero API user ID.
    library_type : str
        Zotero API library type: user or group.
    api_key : str
        Zotero API user key.
    locale : str, optional
        Zotero bibliography locale, see https://github.com/citation-style-language/locales.

    """

    def __init__(
        self, library_id=None, library_type=None, api_key=None, locale="en-GB"
    ):
        self._library_id = library_id
        self._library_type = library_type
        self._api_key = api_key
        self._locale = locale
        self._installation_directory = self._retrieve_default_installation_directory()
        self._profile_directory = self._retrieve_default_profile_directory()
        self._retrieve_data_directory()
        self._retrieve_attachment_root_directory()
        self._retrieve_library()

    def _retrieve_library(self):
        self._library = Zotero(
            self._library_id, self._library_type, self._api_key, self._locale
        )

    @staticmethod
    def _retrieve_default_installation_directory():
        return Path(*_ZOT_DEFAULT_INSTALLATION_PATHS_PARTS[sys.platform])

    @staticmethod
    def _retrieve_default_profile_directory():
        # Windows >= Vista, https://www.zotero.org/support/kb/profile_directory#profile_directory_location
        return Path.home().joinpath(
            *_ZOT_DEFAULT_PROFILE_RELATIVE_PATHS_PARTS[sys.platform]
        )

    def _retrieve_data_directory(self):
        self._data_directory = Path(
            self._retrieve_preference("extensions.zotero.dataDir")
        )

    def _retrieve_attachment_root_directory(self):
        try:
            self._attachment_root_directory = Path(
                self._retrieve_preference("extensions.zotfile.dest_dir")
            )
        except:
            self._attachment_root_directory = Path(
                self._retrieve_preference("extensions.zotero.baseAttachmentPath")
            )

    def _retrieve_preference_path(self, preference_type="user", preference_owner=None):
        """Retrieve the preference file path.

        Parameters
        ----------
        preference_type : str, optional
            "user" or "default",
            when "user" is input, any input for `preference_owner` will be ignored.
        preference_owner : str, optional
            The name of Zotero or its plugins whose preference is being retrieved,
            e.g. "zotero", "zotfile", etc.

        Returns
        -------
        out : pathlib.Path
            A pathlib.Path object that represents the requested preference path.
            NOTE: For a Zotero plugin will return its xpi `zipfile.ZipFile` object and its default preference `pathlib.PurePath` relative to the former. A new class `zipfile.Path` is introduced in Python 3.8.

        TODO: future revision for `zipfile` for Python 3.8 and above.

        """
        if preference_type.lower() == "user":
            profile_config = ConfigParser()
            profile_config.read(self._profile_directory / "profiles.ini")
            return (
                self._profile_directory
                / profile_config["Profile0"]["Path"]
                / "prefs.js"
            )
        elif preference_type.lower() == "default":
            if preference_owner is None:
                raise ValueError("preference owner undefined")
            elif preference_owner.lower() == "zotero":
                return (
                    self._installation_directory
                    / "defaults"
                    / "preferences"
                    / "zotero.js"
                )
            else:
                profile_config = ConfigParser()
                profile_config.read(self._profile_directory / "profiles.ini")
                try:
                    plugin_xpi_path = list(
                        (
                            self._profile_directory
                            / profile_config["Profile0"]["Path"]
                            / "extensions"
                        ).glob(preference_owner.lower() + "*.xpi")
                    )[
                        0
                    ]  # can there be duplicate plugin packages?
                except:
                    raise ValueError("no preference owner found")
                return (
                    ZipFile(plugin_xpi_path),
                    PurePath("defaults", "preferences", "defaults.js"),
                )
        else:
            raise ValueError("invalid preference type: " + str(preference_type))

    def _retrieve_preference(
        self, preference_key, preference_type="user", preference_owner=None
    ):
        """Retrieve the preference file path.

        Parameters
        ----------
        preference_key : str
            Key to requested preference defined by Zotero.
        preference_type : str, optional
            "user" or "default",
            when "user" is input, any input for `preference_owner` will be ignored.
        preference_owner : str, optional
            The name of Zotero or its plugins whose preference is being retrieved,
            e.g. "zotero", "zotfile", etc.

        Returns
        -------
        out : str
            Preference information string.

        TODO: future revision for `zipfile` for Python 3.8 and above

        """
        re_pattern = '(?<=pref\("' + preference_key + '", ").*(?="\);)'
        if preference_type == "default" and (not preference_owner == "zotero"):
            plugin_xpi_path, preference_path_in_xpi = self._retrieve_preference_path(
                preference_type, preference_owner
            )
            # ZipFile.open() needs TextIOWrapper to read as text
            with TextIOWrapper(
                plugin_xpi_path.open(str(preference_path_in_xpi), "r"), encoding="utf-8"
            ) as fh:
                preferences = fh.read()
        else:
            preference_path = self._retrieve_preference_path(
                preference_type, preference_owner
            )
            with preference_path.open("rt") as fh:
                preferences = fh.read()
        try:
            return re.search(re_pattern, preferences).group(0)
        except:
            raise ValueError('no "' + preference_key + '" information found')

    # def retrieve_entries(self, **kwargs):
    #     if "limit" in kwargs:
    #         entries = self._library.top(**kwargs)
    #     else:
    #         entries = self._library.everything(self.__library.top(**kwargs))
    #     return entries

    @property
    def installation_directory(self):
        return self._installation_directory

    @property
    def profile_directory(self):
        return self._profile_directory

    @installation_directory.setter
    def installation_directory(self, installation_directory):
        installation_directory = Path(installation_directory)
        if installation_directory.is_dir():
            self._installation_directory = installation_directory
        else:
            raise ValueError("invalid directory: " + installation_directory)

    @profile_directory.setter
    def profile_directory(self, profile_directory):
        profile_directory = Path(profile_directory)
        if profile_directory.is_dir():
            self._profile_directory = profile_directory
        else:
            raise ValueError("invalid directory: " + profile_directory)
        self._retrieve_data_directory()
        self._retrieve_attachment_root_directory()

    def retrieve_attachment_relative_paths(self, **kwargs):
        attachment_entries = self._library.everything(
            self._library.items(itemType="attachment", **kwargs)
        )
        attachment_relative_paths = []
        for attachment_entry in attachment_entries:
            try:
                attachment_relative_path = PurePath(
                    attachment_entry["data"]["path"].split("attachments:")[-1]
                )
            except:
                # Attachments that are not managed by linked file
                pass
            attachment_relative_paths.append(attachment_relative_path)
        return tuple(attachment_relative_paths)

    def retrieve_files_relocation_maps(self):
        """Retrieve all path maps generated in the unlinked files relocation.

        Yields
        ----------
        out : generator
            A generator of all maps derived from different relocated files directories.

        """
        for files_relocation_map_path in self._attachment_root_directory.glob(
            "**/_files_relocation_map.json"
        ):
            with files_relocation_map_path.open("rt") as fh:
                yield json.load(fh)

    def relocate_unlinked_files(self, zotfile=True, file_types=None):
        """Relocate unlinked files from the Zotero attachment directory.

        Parameters
        ----------
        zotfile : bool, optional
            Whether or not ZotFile is used to manage the attachment links,
            when True, any input for `file_types` will be ignored.
        file_types : iterable or string, optional
            File types to inspect when `zotfile` is `False`,
            e.g. ["pdf", "doc"], ("docx", "txt"), numpy.array(["rtf", "djvu"]), etc.
            e.g. "pdf, doc, docx, txt, rtf, djvu"

        """
        # Retrieve the attachment paths
        attachment_relative_paths = self.retrieve_attachment_relative_paths()
        attachment_paths = tuple(
            self._attachment_root_directory / path for path in attachment_relative_paths
        )

        # Retrieve the file types
        if zotfile:
            try:
                file_types = self._retrieve_preference("extensions.zotfile.filetypes")
            except:
                file_types = self._retrieve_preference(
                    "extensions.zotfile.filetypes",
                    preference_type="default",
                    preference_owner="zotfile",
                )
            file_types = tuple(file_type.strip() for file_type in file_types.split(","))
        else:
            if file_types is None:
                raise ValueError("no file types specified")
            try:
                if isinstance(file_types, str):
                    file_types = tuple(
                        file_type.strip() for file_type in file_types.split(",")
                    )
                else:
                    file_types = tuple(file_types)
            except:
                raise ValueError("invalid file types")

        # Relocate the unlinked files to a designated directory with a map to their orginal paths
        file_relative_paths = tuple(
            item
            for item in self._attachment_root_directory.glob("**/*")
            if item.is_file()
            and (item.suffix.strip(".") in file_types)
            and (not item.parts[-2].startswith("_unlinked_files"))
        )
        unlinked_files_relocation_directory = (
            self._attachment_root_directory
            / "_".join(("_unlinked_files", dt.datetime.now().strftime("%Y%m%d%H%M%S")))
        )
        unlinked_files_relocation_directory.mkdir()
        unlinked_file_paths = set(file_relative_paths) - set(attachment_paths)
        files_relocation_map = {}
        for unlinked_file_path in unlinked_file_paths:
            unlinked_file_relocated_path = (
                unlinked_files_relocation_directory / unlinked_file_path.name
            )
            files_relocation_map.update(
                {str(unlinked_file_relocated_path): str(unlinked_file_path)}
            )
            unlinked_file_path.rename(unlinked_file_relocated_path)
        if files_relocation_map:
            files_relocation_map_path = (
                unlinked_files_relocation_directory / "_files_relocation_map.json"
            )
            with open(files_relocation_map_path, "w") as fh:
                json.dump(files_relocation_map, fh, indent=4)
        else:
            remove_empty_directories(unlinked_files_relocation_directory)

        # Remove the empty directories
        remove_empty_directories(self._attachment_root_directory)

    def remove_unlinked_files(
        self,
        unrelocated_unlinked_files=True,
        relocated_unlinked_files=True,
        files_relocation_maps=None,
    ):
        """Remove the linked files by the given criterion, all are removed by default.

        Parameters
        ----------
        files_relocation_maps : dict or ierable(dict), optional
            Files relocation map for removal.
            Warning! If not specified, all the relocated files will be removed

        TODO: add an option to specify `files_relocation_map_paths`, consider recursive.

        """
        if files_relocation_maps:
            # ugly and unreliable workaround to separate a single dict and a generator, revision needed
            try:
                files_relocation_maps = (files_relocation_maps,)
            except:
                files_relocation_maps = tuple(files_relocation_maps)
        else:
            files_relocation_maps = self.retrieve_files_relocation_maps()

        for files_relocation_map in files_relocation_maps:
            files_relocation_map_path = None
            for path in map(lambda x: Path(x), files_relocation_map.keys()):
                # path.unlink(missing_ok=True) in Python 3.8
                if path.is_file():
                    path.unlink()
                    if files_relocation_map_path is None:
                        files_relocation_map_path = (
                            path.parent / "_files_relocation_map.json"
                        )
                else:
                    pass
            try:
                files_relocation_map_path.unlink()
            except:
                pass

    def restore_unlinked_files(self):
        pass

