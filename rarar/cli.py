import argparse
import json
import logging
import sys

from .models import RarFile
from .reader import RarReader


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration.

    Args:
        debug (bool): Whether to enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("rarar")
    logger.setLevel(level)

    if debug:
        logger.debug("Debug logging enabled")


def list_rar_contents(url: str, json_output: bool = False) -> list[RarFile]:
    """List contents of a RAR archive and display results.

    Args:
        url (str): URL of the RAR archive
        json_output (bool): Whether to output as JSON

    Returns:
        list[RarFile]: List of RarFile objects representing the contents of the RAR archive
    """
    logger = logging.getLogger("rarar")
    try:
        logger.debug(f"Analyzing RAR archive at: {url}")
        reader = RarReader(url)
        files = reader.list_files()

        if not json_output:
            logger.info(f"RAR Archive: {url}")
            logger.info(f"Found {len(files)} files/directories:")

            for i, file in enumerate(files, 1):
                logger.info(f"  {i}. {file}")
        else:
            json_data = [file.to_dict() for file in files]
            print(json.dumps(json_data, indent=2))

        return files
    except Exception as e:
        logger.error(f"Error: {e}")
        return []


def download_file(url: str, file_index: int) -> bool:
    """Download a specific file from the RAR archive.

    Args:
        url (str): URL of the RAR archive
        file_index (int): 1-based index of the file to download

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger("rarar")
    try:
        reader = RarReader(url)

        i = 0
        file_to_download: RarFile | None = None

        for file in reader.iter_files():
            i += 1
            if i == file_index:
                file_to_download = file
                break

        if i == 0:
            logger.error("No files found in the RAR archive")
            return False
        if file_to_download is None:
            logger.error(f"Invalid index. Please choose between 1 and {i}")
            return False

        reader.download_file(file_to_download)
        return True
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return False


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Random Access RAR Reader - Access RAR archives without loading the entire file into memory"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    list_parser = subparsers.add_parser("list", help="List contents of a RAR archive")
    list_parser.add_argument("url", help="URL or path to the RAR archive")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    download_parser = subparsers.add_parser(
        "download", help="Download a file from a RAR archive"
    )
    download_parser.add_argument("url", help="URL or path to the RAR archive")
    download_parser.add_argument(
        "file_index", type=int, help="1-based index of the file to download"
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.debug)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        files = list_rar_contents(args.url, args.json)
        if not files:
            sys.exit(1)

    elif args.command == "download":
        success = download_file(args.url, args.file_index)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
