import argparse
import json
import logging
import sys

from .exceptions import RaRarError
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


def list_rar_contents(source: str, json_output: bool = False) -> list[RarFile]:
    """List contents of a RAR archive and display results.

    Args:
        source (str): URL or path to the RAR archive
        json_output (bool): Whether to output as JSON

    Returns:
        list[RarFile]: List of RarFile objects representing the contents of the RAR archive
    """
    logger = logging.getLogger("rarar")
    try:
        logger.debug(f"Analyzing RAR archive at: {source}")
        reader = RarReader(source)

        files = []
        if not json_output:
            logger.info(f"RAR Archive: {source}")

            for i, file in enumerate(reader.iter_files(), 1):
                files.append(file)
                logger.info(f"  {i}. {file.path} ({file.size} bytes)")

            logger.info(f"Found {len(files)} files/directories:")
        else:
            files = reader.list_files()
            json_data = [file.to_dict() for file in files]
            print(json.dumps(json_data, indent=2))

        return files
    except RaRarError as e:
        logger.error(e)
        return []
    except Exception as e:
        logger.error(f"Unknown error occured while listing RAR archive: {e}")
        return []


def download_file(source: str, file_index: int) -> bool:
    """Download a specific file from the RAR archive.

    Args:
        source (str): URL or path to the RAR archive
        file_index (int): 1-based index of the file to download

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger("rarar")
    try:
        reader = RarReader(source)

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
    except RaRarError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(f"Unknown error occurred while downloading: {e}")
        return False


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Random Access RAR Reader - Access RAR archives without loading the entire file into memory"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    list_parser = subparsers.add_parser("list", help="List contents of a RAR archive")
    list_parser.add_argument("source", help="URL or path to the RAR archive")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    download_parser = subparsers.add_parser(
        "download", help="Download a file from a RAR archive"
    )
    download_parser.add_argument("source", help="URL or path to the RAR archive")
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
        files = list_rar_contents(args.source, args.json)
        if not files:
            sys.exit(1)

    elif args.command == "download":
        success = download_file(args.source, args.file_index)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
