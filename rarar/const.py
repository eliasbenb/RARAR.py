# RAR marker and block types
RAR_MARKER = b"\x52\x61\x72\x21\x1a\x07\x00"
RAR_BLOCK_FILE = 0x74
RAR_BLOCK_HEADER = 0x73
RAR_BLOCK_MARKER = 0x72
RAR_BLOCK_END = 0x7B

# Default chunk size for searching and reading
DEFAULT_CHUNK_SIZE = 4096
MAX_SEARCH_SIZE = 1024 * 1024  # 1MB

# Header flags
FLAG_DIRECTORY = 0xE0  # File is a directory
FLAG_HAS_HIGH_SIZE = 0x100  # Has 64-bit size values
FLAG_HAS_UNICODE_NAME = 0x200  # Has Unicode filename
FLAG_HAS_DATA = 0x8000  # Has additional data

# Compression methods
COMPRESSION_METHODS: dict[int, str] = {
    0x30: "Store",
    0x31: "Fastest",
    0x32: "Fast",
    0x33: "Normal",
    0x34: "Good",
    0x35: "Best",
}
COMPRESSION_METHODS_REVERSE: dict[str, int] = {
    v: k for k, v in COMPRESSION_METHODS.items()
}
