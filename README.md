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
> - Compressed with any compression method other than `Store`
> - Encrypted
> - Multi-part
>
> Additionally, if using an HTTP URL, the server must support `Range` requests to allow for partial downloads.

- Support for RAR5 archives
- Look into support compression methods other than `Store`
- TUI for the CLI
- Support for multi-file downloads
- Support for directory downloads
- Create file tree UI for CLI's list output

## Python Usage

### Listing Contents of a RAR Archive

```python
from rarar import RarReader

source = "https://example.com/archive.rar"  # URL, file, or file-like object
reader = RarReader(source) 
for file in reader.list_files():
    print(f"{file.name} - {file.size} bytes")
```

### Extracting a File from a RAR Archive

```python
from rarar import RarReader

source = "./archives/archive.rar"  # URL, file, or file-like object
reader = RarReader("https://example.com/archive.rar")
file = next(reader.iter_files()) # Get the first file in the archive
reader.extract_file(file, "/path/to/save/file.dat")
```

## CLI Usage

You can also use the RARAR package via the command-line interface to list and extract files from a RAR archive.


```
usage: rarar [-h] [--debug] {list,extract} ...

Random Access RAR Reader - Access RAR archives without loading the entire file into memory

positional arguments:
  {list,extract}  Command to execute
    list          List contents of a RAR archive
    extract       Extract a file from a RAR archive

options:
  -h, --help      show this help message and exit
  --debug         Enable debug logging
```

### Listing Contents of a RAR Archive

```bash
rarar list <source> [--json]
```

### Extracting a File from a RAR Archive

```bash
rarar extract <source> <file_index> [-o <output_path>]
```
