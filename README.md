# ZotUtil

This is a repository of utilities to assist the use of [Zotero](https://www.zotero.org) and its [plugins](https://www.zotero.org/support/plugins) via [pyzotero](https://github.com/urschrei/pyzotero).

## Utilities

- **Unlinked Files Clean**

  - Motivation

    This is to resolve situations when attachment files are left behind whilst their formerly linked entries have been deleted from the Zotero library. This happens when the [Linked Files](https://www.zotero.org/support/attaching_files#stored_files_and_linked_files) is used, most likely together with [ZotFile](https://github.com/jlegewie/zotfile).

  - Functions

    ```bash
    clean unlinked files
    ├── relocate unlinked files
    ├── remove unlinked files
    └── restore unlinked files
    ```

- **Tags Case Unification** (To Do)

  - Motivation

    This is to resolve situations when literally same tags co-exist in different cases (e.g. climate change, Climate change & Climate Change), due to diverse bibliography import sources and the case sensitivity in Zotero. Some regard this as a feature though, see discussion [here](https://forums.zotero.org/discussion/comment/317212).
