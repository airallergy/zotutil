from pyzotero.zotero import Zotero
from configparser import ConfigParser
from pathlib import PurePath, Path
import re
import datetime as dt
import sys
from zipfile import ZipFile
from io import TextIOWrapper
import json


_ZOT_PROFILE_RELATIVE_PATHS = {
    "darwin": ("Library", "Application Support", "Zotero"),
    "win32": ("AppData", "Roaming", "Zotero", "Zotero"),
}


class Zot:
    """Create a Zotero library object.

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
        self._installation_directory = self._get_installation_directory()
        self._profile_directory = self._get_profile_directory()
        self._get_library()

    def _get_library(self):
        self._library = Zotero(
            self._library_id, self._library_type, self._api_key, self._locale
        )

    @staticmethod
    def _get_installation_directory():
        return None

    @staticmethod
    def _get_profile_directory():
        # Windows >= Vista, https://www.zotero.org/support/kb/profile_directory#profile_directory_location
        return Path.home().joinpath(*_ZOT_PROFILE_RELATIVE_PATHS[sys.platform])

    def _get_data_directory(self):
        # https://www.zotero.org/support/zotero_data#default_locations
        return Path(self._get_preference("extensions.zotero.dataDir"))

    def _get_preference_path(self, preference_type="user", preference_owner=None):
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
                return Path(
                    "/Applications/Zotero.app/Contents/Resources/defaults/preferences/zotero.js"
                )  # revision needed for other os
            else:
                profile_config = ConfigParser()
                profile_config.read(self._profile_directory / "profiles.ini")
                try:
                    extension_xpi_path = list(
                        (
                            self._profile_directory
                            / profile_config["Profile0"]["Path"]
                            / "extensions"
                        ).glob(preference_owner.lower() + "*.xpi")
                    )[0]
                except:
                    raise ValueError("no preference owner found")
                return (
                    ZipFile(extension_xpi_path),
                    PurePath("defaults", "preferences", "defaults.js"),
                )
        else:
            raise ValueError("invalid preference type: " + str(preference_type))

    def _get_preference(
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
            plugin_xpi_path, preference_path_in_xpi = self._get_preference_path(
                preference_type, preference_owner
            )
            # ZipFile.open() needs TextIOWrapper to read as text
            with TextIOWrapper(
                plugin_xpi_path.open(str(preference_path_in_xpi), "r"), encoding="utf-8"
            ) as fh:
                preferences = fh.read()
        else:
            preference_path = self._get_preference_path(
                preference_type, preference_owner
            )
            with preference_path.open("r") as fh:
                preferences = fh.read()
        try:
            return re.search(re_pattern, preferences).group(0)
        except:
            raise ValueError("no preference infomation found")

    # def get_entries(self, **kwargs):
    #     if "limit" in kwargs:
    #         entries = self._library.top(**kwargs)
    #     else:
    #         entries = self._library.everything(self.__library.top(**kwargs))
    #     return entries

    def set_directory(
        self,
        zot_installation_directory=None,
        zot_profile_directory=None,
        zot_data_directory=None,
    ):
        """Set user defined directories.

        Parameters
        ----------
        zot_installation_directory : str
            User defined directory where Zotero is installed.
        zot_profile_directory : str
            User defined directory where the Zotero profile is stored.
        zot_data_directory : str
            User defined directory where the Zotero local library data is stored.

        """
        if zot_installation_directory:
            self._installation_directory = Path(zot_installation_directory)
        if zot_profile_directory:
            self._profile_directory = Path(zot_profile_directory)
        if zot_data_directory:
            self._data_directory = Path(zot_data_directory)

    def get_attachment_relative_paths(self, **kwargs):
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
        return attachment_relative_paths

    def remove_unlinked_files(self, zotfile=True, delete=False, file_types=None):
        """Remove unlinked files from the Zotero attachment directory.

        Parameters
        ----------
        zotfile : bool, optional
            Use of ZotFile to manage the attachment links,
            when True, any input for `file_types` will be ignored.
        delete : bool, optional
            Delete or remove the unlined files.
        file_types : iterable or string, optional
            File types to inspect when `zotfile` is `False`,
            e.g. ["pdf", "doc"], ("docx", "txt"), numpy.array(["rtf", "djvu"]), etc.
            e.g. "pdf, doc, docx, txt, rtf, djvu"

        """
        # Retrieve the attachment paths
        attachment_relative_paths = self.get_attachment_relative_paths()
        attachment_base_directory = Path(
            self._get_preference(
                "extensions.zotfile.dest_dir"
                if zotfile
                else "extensions.zotero.baseAttachmentPath"
            )
        )
        attachment_paths = [
            attachment_base_directory / path for path in attachment_relative_paths
        ]

        # Retrieve the file types
        if zotfile:
            try:
                file_types = self._get_preference("extensions.zotfile.filetypes")
            except:
                file_types = self._get_preference(
                    "extensions.zotfile.filetypes",
                    preference_type="default",
                    preference_owner="zotfile",
                )
            file_types = tuple(
                [file_type.strip() for file_type in file_types.split(",")]
            )
        else:
            if file_types is None:
                raise ValueError("no file types specified")
            try:
                if isinstance(file_types, str):
                    file_types = tuple(
                        [file_type.strip() for file_type in file_types.split(",")]
                    )
                else:
                    file_types = tuple(file_types)
            except:
                raise ValueError("invalid file types")

        # Remove the unlinked files to a designated directory with a map to their orginal paths
        file_relative_paths = [
            path
            for path in attachment_base_directory.glob("**/*")
            if path.is_file()
            and (path.suffix.strip(".") in file_types)
            and (not path.parts[-2].startswith("_unlinked_files"))
        ]
        unlinked_file_removal_directory = attachment_base_directory / "_".join(
            ["_unlinked_files", dt.datetime.now().strftime("%Y%m%d%H%M%S")]
        )
        unlinked_file_removal_directory.mkdir()
        unlinked_file_paths = set(file_relative_paths) - set(attachment_paths)
        unlinked_files_removal_map = {}
        for unlinked_file_path in unlinked_file_paths:
            unlinked_file_path_new = (
                unlinked_file_removal_directory / unlinked_file_path.name
            )
            unlinked_files_removal_map.update(
                {str(unlinked_file_path_new): str(unlinked_file_path)}
            )
            unlinked_file_path.rename(unlinked_file_path_new)
        with open(
            unlinked_file_removal_directory / "_unlinked_files_removal_map.json", "w"
        ) as fh:
            json.dump(unlinked_files_removal_map, fh, indent=4)
