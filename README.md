# RARAR.py - Random Access RAR

RARAR is a Python package that enables random access to RAR archives, allowing you to list and extract files without downloading the entire archive.

While the main use case for RARAR is to access RAR archives stored over HTTP, it can also be used to access any file-like object that supports seeking and reading. This includes local files, in-memory files, and other file-like objects.

> [!IMPORTANT]  
> Unfortunately, due to limitations in the RAR format, RARAR cannot currently access RAR archives that are either:
>
> - Compressed with any compression method other than `Store`
> - Encrypted
> - Multi-part
>
> Additionally, if using an HTTP URL, the server must support `Range` requests to allow for partial downloads.

## Features

- Remote RAR Access: Read RAR archives directly from URLs without downloading the entire file
- Random Access: Extract specific files from an archive efficiently
- Support for Multiple Sources: Works with local file paths, file-like objects, and HTTP URLs

## Installation

```shell
pip install git+https://github.com/eliasbenb/RARAR.py.git
```

## Usage

```python
from rarar import RarReader

# From a URL
reader = RarReader("https://example.com/archive.rar")
for file in reader.list_files():
    print(f"{file.name} - {file.size} bytes")

# From a local file
reader = RarReader("/path/to/archive.rar")
for file in reader.list_files():
    print(f"{file.name} - {file.size} bytes")

# From a file-like object
from io import BytesIO

data = b"..."  # Your RAR data
reader = RarReader(BytesIO(data))
file = next(reader.iter_files())
reader.download_file(file, "/path/to/save/file.txt")
```

