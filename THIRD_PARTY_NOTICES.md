# Third-party notices

Icarus Server Mod Manager is released under the MIT License (see [LICENSE](LICENSE)).
It builds on the work of others:

## NetPak (Apache-2.0)

`icarus_manager/uepak.py` is a Python port of the Icarus `.pak` file handling implemented
by NetPak, Copyright 2022 Crystal Ferrai - https://github.com/CrystalFerrai/NetPak -
licensed under the Apache License 2.0. The full license text is included at
[licenses/NetPak-Apache-2.0.txt](licenses/NetPak-Apache-2.0.txt).

## repak (MIT / Apache-2.0)

Reading game paks (including Oodle decompression) uses the `repak` Python bindings
(https://pypi.org/project/repak/) around the repak Rust crate
(https://github.com/trumank/repak), licensed MIT/Apache-2.0. The Oodle runtime itself is
proprietary, is not redistributed by this project, and is fetched on first use (or taken
from an installed copy of Icarus when available).

## Other dependencies

Streamlit, requests, BeautifulSoup4, paramiko and their transitive dependencies are
licensed under their respective open-source licenses.

## Community data

Mod listings come from the community index at https://www.projectdaedalus.app. Mods
themselves belong to their authors and are downloaded from their original release links.
