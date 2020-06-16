from pyzotero.zotero import Zotero
from configparser import ConfigParser
from pathlib import PurePath, Path
import re
import datetime as dt


class Zot:
    """
    Create a Zotero library object.

    Parameters
    ----------
    library_id : str
        Zotero API user ID.
    library_type : str
        Zotero API library type: user or group.
    api_key : str
        Zotero API user key
    locale : str
        Zotero bibliography locale, see https://github.com/citation-style-language/locales.

    """

    def __init__(
        self, library_id=None, library_type=None, api_key=None, locale="en-GB"
    ):
        self._library_id = library_id
        self._library_type = library_type
        self._api_key = api_key
        self._locale = locale
        self._zot_directory = None
        self._get_library()

    def _get_library(self):
        self._library = Zotero(
            self._library_id, self._library_type, self._api_key, self._locale
        )

    def _get_preference_path(self):
        config = ConfigParser()
        config.read(self._zot_directory / "profiles.ini")
        self._zot_preference_path = (
            self._zot_directory / config["Profile0"]["Path"] / "prefs.js"
        )

    def _get_preference(self, preference_key):
        self._get_preference_path()
        re_pattern = '(?<=user_pref\("' + preference_key + '", ").*(?="\);)'
        with open(self._zot_preference_path, "r") as f:
            preferences = f.read()
        return re.search(re_pattern, preferences).group(0)

    # def get_entries(self, **kwargs):
    #     if "limit" in kwargs:
    #         entries = self._library.top(**kwargs)
    #     else:
    #         entries = self._library.everything(self.__library.top(**kwargs))
    #     return entries

    def add_args(self, zot_directory):
        """
        Add additional arguments where necessary.

        Parameters
        ----------
        zot_directory : str
            Directory that stores the Zotero preferences file.

        """
        self._zot_directory = PurePath(zot_directory)

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

    def remove_unlinked_files(self, zotfile=True, delete=False):
        """
        Remove unlinked files from the Zotero attachment directory.

        Parameters
        ----------
        zotfile : boolean
            Use of ZotFile to manage the attachment links.
        delete : boolean
            Delete or remove the unlined files.

        Returns
        -------
        fileRemoveCount : int
            Count of the files removed.
        fileRemainCount : int
            Count of the files remained.
        
        TODO: Only pdf files are inspected currently, this can be expanded to all file types set in ZotFile.

        """
        # Retrieve the attachment paths
        attachment_relative_paths = self.get_attachment_relative_paths()
        attachment_base_directory = Path(
            self._get_preference("extensions.zotfile.dest_dir")
            if zotfile
            else self._get_preference("extensions.zotero.baseAttachmentPath")
        )
        attachment_paths = [
            attachment_base_directory / path for path in attachment_relative_paths
        ]

        # Remove unlinked files to a designated directory
        file_types = (".pdf",)
        file_relative_paths = [
            path
            for path in attachment_base_directory.rglob("*")
            if path.is_file()
            and (path.suffix in file_types)
            and (not path.parts[-2].startswith("unlinked_files"))
        ]
        unlinked_file_paths = set(file_relative_paths) - set(attachment_paths)
        unlinked_file_removal_directory = attachment_base_directory / PurePath(
            "_".join(["unlinked_files", dt.datetime.now().strftime("%Y%m%d%H%M%S")])
        )
        unlinked_file_removal_directory.mkdir()
        for unlinked_file_path in unlinked_file_paths:
            unlinked_file_path.rename(
                unlinked_file_removal_directory / unlinked_file_path.name
            )
