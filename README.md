# RARAR.py

RARAR is a Python package that enables random access to RAR archives, allowing you to list and extract files without downloading the entire archive.

While the main use case for RARAR is to access RAR archives stored over HTTP, it can also be used to access any file-like object that supports seeking and reading. This includes local files, in-memory files, and other file-like objects.

## Installation

```shell
pip install git+https://github.com/eliasbenb/RARAR.py.git
```

## Features

- Remote RAR Access: Read RAR archives directly from URLs without downloading the entire file
- Random Access: Extract specific files from an archive efficiently
- Support for Multiple Sources: Works with local file paths, file-like objects, and HTTP URLs

## TODO

> [!IMPORTANT]  
> Unfortunately, due to limitations in the RAR format, RARAR cannot currently access RAR archives that are either:
>
> - Multi-part over HTTP
>
> Compressed files (non-`Store`) and encrypted file data are supported via a fallback to the external `unrar` binary, which must be installed and available in `PATH`.
>
> Encrypted extraction requires a password (`RarReader(..., password="...")` or CLI `--password`).
>
> Multi-part archives are supported for local files when opening the first volume (`.part1.rar` or `.rar` + `.r00/.r01/...`).
>
> Additionally, if using an HTTP URL, the server must support `Range` requests to allow for partial downloads.

- TUI for the CLI
- Support for directory downloads
- Create file tree UI for CLI's list output

## Python Usage

### Listing Contents of a RAR Archive

```python
from rarar import RarReader

source = "https://example.com/archive.rar"  # URL, file, or file-like object
reader = RarReader(source)
for file in reader:
    print(f"{file.name} - {file.size} bytes")
```

### Extracting a File from a RAR Archive

```python
from rarar import RarReader

source = "./archives/archive.rar"  # URL, file, or file-like object
reader = RarReader("https://example.com/archive.rar", password="my-password")
file = next(reader) # Get the first file in the archive
reader.extract(file, output_path="/path/to/save/file.dat")
```

## CLI Usage

You can also use the RARAR package via the command-line interface to list and extract files from a RAR archive.

```
usage: rarar [-h] [--debug] {list,extract} ...

Random Access RAR Reader - Access RAR archives without loading the entire file into memory

positional arguments:
  {list,extract}  Command to execute
    list          List contents of a RAR archive
    extract       Extract files from a RAR archive

options:
  -h, --help      show this help message and exit
  --debug         Enable debug logging
```

### Listing Contents of a RAR Archive

```bash
rarar list [--json] [--password PASSWORD] source
```

### Extracting a File from a RAR Archive

```bash
rarar extract [-o OUTPUT] [--password PASSWORD] source [file_indices ...]
```
