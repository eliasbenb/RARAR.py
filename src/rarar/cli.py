"""Command line interface for RARAR."""

import argparse
import json
import logging
import sys

from rarar.exceptions import RaRarError
from rarar.models import RarFile
from rarar.reader import RarReader


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration.

    Args:
        debug (bool): Whether to enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if debug
        else "%(message)s",
    )
    logger = logging.getLogger("rarar")
    logger.setLevel(level)

    if debug:
        logging.getLogger("httpx").setLevel(logging.INFO)
        logger.debug("Debug logging enabled")


def list_rar_contents(source: str, json_output: bool = False) -> list[RarFile]:
    """List contents of a RAR archive and display results.

    Args:
        source (str): URL or path to the RAR archive
        json_output (bool): Whether to output as JSON

    Returns:
        list[RarFile]: List of RarFile objects representing the contents
            of the RAR archive
    """
    logger = logging.getLogger("rarar")
    try:
        logger.debug(f"Analyzing RAR archive at: {source}")
        reader = RarReader(source)

        files = []
        files_count = 0
        dir_count = 0

        if not json_output:
            logger.info(f"RAR Archive: {source}")

            for i, file in enumerate(reader, 1):
                files.append(file)
                if file.is_directory:
                    dir_count += 1
                else:
                    files_count += 1
                logger.info(f"{i:>3}. {file}")

            logger.info(f"Found {files_count} files and {dir_count} directories")
        else:
            json_data = [file.to_dict() for file in list(reader)]
            print(json.dumps(json_data, indent=2))

        return files
    except RaRarError as e:
        logger.error(e)
        return []
    except Exception as e:
        logger.error(f"Unknown error occured while listing RAR archive: {e}")
        return []


def extract(
    source: str, file_indices: set[int] | None = None, output_path: str = "."
) -> None:
    """Extract files from the RAR archive.

    Args:
        source (str): URL or path to the RAR archive
        file_indices (set[int] | None): Set of indices of files to extract.
            If None, extracts all files
        output_path (str): Path to save the extracted files
    """
    logger = logging.getLogger("rarar")
    try:
        reader = RarReader(source)

        # If no indices provided, extract all files
        if file_indices is None:
            logger.info("Extracting all files from the archive")
            reader.extract(None, output_path)
            return

        for i, file in enumerate(reader, 1):
            if i not in file_indices:
                continue
            if file.is_directory:
                logger.warning(f"Skipping directory: {file.path}")
                continue
            file_indices.remove(i)

            extract_path = output_path / file.path
            if reader.extract(file, extract_path):
                logger.info(f"Extracted file: {file.path}")
            else:
                logger.error(f"Failed to extract file: {file.path}")

            if not file_indices:
                break
    except RaRarError as e:
        logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(f"Unknown error occurred while extracting: {e}", exc_info=True)


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Random Access RAR Reader - Access RAR archives without "
        "loading the entire file into memory"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    list_parser = subparsers.add_parser("list", help="List contents of a RAR archive")
    list_parser.add_argument("source", help="URL or path to the RAR archive")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract files from a RAR archive"
    )
    extract_parser.add_argument("source", help="URL or path to the RAR archive")
    extract_parser.add_argument(
        "file_indices",
        type=int,
        nargs="*",
        help="1-based indices of files to extract. If not provided, "
        "extracts all files.",
    )
    extract_parser.add_argument(
        "-o", "--output", type=str, help="Path to save the extracted files"
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.debug)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        list_rar_contents(args.source, args.json)
    elif args.command == "extract":
        file_indices = None if not args.file_indices else set(args.file_indices)
        extract(args.source, file_indices, args.output or ".")


if __name__ == "__main__":
    main()
