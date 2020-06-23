from configparser import ConfigParser
from pathlib import PurePath, Path
from io import TextIOWrapper
from zipfile import ZipFile
import datetime as dt
import json
import sys
import re

from pyzotero.zotero import Zotero

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
            if not preference_owner:
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
                    plugin_xpi_path = tuple(
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

    def _retrieve_preference(self, preference_key, **kwargs):
        """Retrieve the preference file path.

        Parameters
        ----------
        preference_key : str
            Key to requested preference defined by Zotero.
        **kwargs:
            Parameters for `self._retrieve_preference_path`.

        Returns
        -------
        out : str
            Preference information string.

        TODO: future revision for `zipfile` for Python 3.8 and above

        """
        preference_type = kwargs.pop("preference_type", "user")
        preference_owner = kwargs.pop("preference_owner", None)

        re_pattern = '(?<=pref\("' + preference_key + '", ").*(?="\);)'
        if preference_type == "default" and (not preference_owner == "zotero"):
            plugin_xpi_path, preference_path_in_xpi = self._retrieve_preference_path(
                preference_type, preference_owner
            )
            # ZipFile.open() needs TextIOWrapper to read as text in the current Python verison, might be enhanced in the future
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

    def _retrieve_unlinked_files_relocation_maps(self, **kwargs):
        this_relocation = kwargs.pop("this_relocation", False)
        past_relocation = kwargs.pop("past_relocation", False)
        non_relocation = kwargs.pop("non_relocation", False)

        relocation_maps = []
        if this_relocation:
            if hasattr(self, "_unlinked_files_relocation_map"):
                relocation_maps.append(self._unlinked_files_relocation_map)
            else:
                raise ValueError("no relocation done previously in this session")
        if past_relocation:
            include = kwargs.pop("include", None)
            exclude = kwargs.pop("exclude", None)
            relocation_foldername_parts = ["_unlinked_files"]
            if hasattr(self, "_unlinked_files_relocation_map"):
                if hasattr(self, "_foldername_suffix"):
                    relocation_foldername_parts.append(self._foldername_suffix)
                this_relocation_foldername = "_".join(relocation_foldername_parts)
                exclude = (
                    (
                        (this_relocation_foldername, exclude)
                        if isinstance(exclude, str)
                        else (this_relocation_foldername, *exclude)
                    )
                    if exclude
                    else this_relocation_foldername
                )
            relocation_maps.extend(
                self.retrieve_unlinked_files_relocation_maps_by_file(
                    include=include, exclude=exclude
                )
            )
        if non_relocation:
            zotfile = kwargs.pop("zotfile", True)
            file_types = kwargs.pop("file_types", None)
            foldername_suffix = kwargs.pop(
                "foldername_suffix", dt.datetime.now().strftime("%Y%m%d%H%M%S")
            )
            self.relocate_unlinked_files(zotfile, file_types, foldername_suffix)
            relocation_maps.append(self._unlinked_files_relocation_map)
        return tuple(relocation_maps)

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
                continue
            attachment_relative_paths.append(attachment_relative_path)
        return tuple(attachment_relative_paths)

    def retrieve_unlinked_files_relocation_maps_by_file(
        self, include=None, exclude=None
    ):
        """Retrieve the files relocation maps written into json files.

        Parameters
        ----------
        include : str or iterable(str), optional
            Relocation foldernames to be included.
        exclude : str or iterable(str), optional
            Relocation foldernames to be excluded.

        Yields
        ----------
        out : generator
            A generator of maps derived from different relocated files directories.

        """
        include = (include,) if isinstance(include, str) else include
        exclude = (exclude,) if isinstance(exclude, str) else exclude
        if include and exclude:
            same_suffixes = set(include) & set(exclude)
            if same_suffixes:
                raise ValueError(
                    ", ".join(same_suffixes) + " found in both 'include' and 'exclude'"
                )
        include = tuple(set(include)) if include else tuple()
        exclude = tuple(set(exclude)) if exclude else tuple()

        for relocation_map_path in [
            path
            for path in self._attachment_root_directory.glob("**/_relocation_map.json")
            if path.parts[-2].startswith("_unlinked_files")
            and (path.parents[1] == self._attachment_root_directory)
        ]:
            if (include and (relocation_map_path.parts[-2] not in include)) or (
                exclude and (relocation_map_path.parts[-2] in exclude)
            ):
                continue
            with relocation_map_path.open("rt") as fh:
                yield json.load(fh)

    def relocate_unlinked_files(
        self, zotfile=True, file_types=None, foldername_suffix=None
    ):
        """Relocate unlinked files from the Zotero attachment directory.

        Parameters
        ----------
        zotfile : bool, optional
            Whether or not ZotFile is used to manage the attachment links,
            when True, any input for `file_types` will be ignored.
        file_types : str or iterable(str), optional
            File types to inspect when `zotfile` is `False`,
            e.g. ["pdf", "doc"], ("docx", "txt"), numpy.array(["rtf", "djvu"]), etc.
            e.g. "pdf, doc, docx, txt, rtf, djvu"
        foldername_suffix : str, optional
            Suffix to "_unlinked_files" as the relocation folder name,
            e.g. a timestamp `dt.datetime.now().strftime("%Y%m%d%H%M%S")`

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
            if not file_types:
                raise ValueError("neither ZotFile used or file types specified")
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
        relocation_foldername_parts = ["_unlinked_files"]
        if foldername_suffix:
            self._foldername_suffix = foldername_suffix
            relocation_foldername_parts.append(foldername_suffix)
        relocation_directory = self._attachment_root_directory / "_".join(
            relocation_foldername_parts
        )
        if not relocation_directory.is_dir():
            relocation_directory.mkdir()

        file_relative_paths = tuple(
            item
            for item in self._attachment_root_directory.glob("**/*")
            if item.is_file()
            and (item.suffix.strip(".") in file_types)
            and (not item.parts[-2].startswith("_unlinked_files"))
        )
        unlinked_file_paths = set(file_relative_paths) - set(attachment_paths)
        relocation_map = {}
        for unlinked_file_path in unlinked_file_paths:
            unlinked_file_relocated_path = (
                relocation_directory / unlinked_file_path.name
            )
            relocation_map.update(
                {str(unlinked_file_relocated_path): str(unlinked_file_path)}
            )
            unlinked_file_path.rename(unlinked_file_relocated_path)
        if relocation_map:
            self._unlinked_files_relocation_map = relocation_map
            relocation_map_path = relocation_directory / "_relocation_map.json"
            if relocation_map_path.is_file():
                with relocation_map_path.open("rt") as fh:
                    relocation_map = dict(json.load(fh), **relocation_map)
            with open(relocation_map_path, "wt") as fh:
                json.dump(relocation_map, fh, indent=4)
        else:
            remove_empty_directories(relocation_directory)

        # Remove the empty directories
        remove_empty_directories(self._attachment_root_directory)

    def remove_unlinked_files(
        self,
        this_relocation=True,
        past_relocation=False,
        non_relocation=False,
        **kwargs,
    ):
        """Remove the linked files by the given criterion, only those relocated in the same session are removed by default.

        Parameters
        ----------
        this_relocation : bool, optional
            Whether or not to remove files relocated in the current session.
        past_relocation : bool, optional
            Whether or not to remove files that have been relocated in previous sessions.
        non_relocation : bool, optional
            Whether or not to remove files that have yet to be identified and relocated,
            `this_relocation` and `non_relocation` should not be both True.
        **kwargs:
            Parameters for `self.retrieve_unlinked_files_relocation_maps_by_file` and/or `self.relocate_unlinked_files`.

        """
        if this_relocation and non_relocation:
            raise ValueError(
                "'this_relocation' and 'non_relocation' cannot be both True"
            )

        relocation_maps = self._retrieve_unlinked_files_relocation_maps(
            this_relocation=this_relocation,
            past_relocation=past_relocation,
            non_relocation=non_relocation,
            **kwargs,
        )

        # Remove the unlinked files
        # pathlib.Path.unlink(missing_ok=True) in Python 3.8
        for relocation_map in relocation_maps:
            relocation_map_path = None
            for path in map(lambda x: Path(x), relocation_map.keys()):
                if path.is_file():
                    if not relocation_map_path:
                        relocation_map_path = path.parent / "_relocation_map.json"
                    path.unlink()
            if relocation_map_path.is_file():
                relocation_map_path.unlink()

        # Remove the empty directories
        remove_empty_directories(self._attachment_root_directory)

    def restore_unlinked_files(
        self, this_relocation=True, past_relocation=False, **kwargs
    ):
        """Restore the linked files by the given criterion, only those relocated in the same session are removed by default.

        Parameters
        ----------
        this_relocation : bool, optional
            Whether or not to restore relocated files in the current session.
        past_relocation : bool, optional
            Whether or not to restore files that have been relocated in previous sessions.
        **kwargs:
            Parameters for `self.retrieve_unlinked_files_relocation_maps_by_file()`.

        """
        relocation_maps = self._retrieve_unlinked_files_relocation_maps(
            this_relocation=this_relocation, past_relocation=past_relocation, **kwargs
        )

        # Restore the unlinked files
        for relocation_map in relocation_maps:
            relocation_map_path = None
            for relocated_path, original_path in relocation_map.items():
                relocated_path = Path(relocated_path)
                original_path = Path(original_path)
                if relocated_path.is_file():
                    if not relocation_map_path:
                        relocation_map_path = (
                            relocated_path.parent / "_relocation_map.json"
                        )
                    if not original_path.parent.is_dir():
                        original_path.parent.mkdir(parents=True)
                    if original_path.is_file():
                        # very rare, just in case
                        raise ValueError("'" + str(original_path) + "' already exists")
                    relocated_path.rename(original_path)
            if relocation_map_path.is_file():
                relocation_map_path.unlink()

        # Remove the empty directories
        remove_empty_directories(self._attachment_root_directory)
