"""JSON article storage parsing and validation.

Provides functions for reading, parsing, and validating article
records stored as individual JSON files.

Defines article-related data structures and custom exceptions
for missing, invalid, or unreadable article records.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict, TypeGuard, cast, overload

from . import config


class ArticleNotFoundError(Exception):
    """Raised when the requested article does not exist."""


class InvalidArticleError(Exception):
    """Raised when an article contains invalid or malformed data."""


class ArticleReadError(Exception):
    """Raised when an article cannot be read due to an I/O error."""


class Comment(TypedDict):
    """Represents a comment stored in an article.

    Attributes:
        comment_id: Unique numeric identifier of the comment, stored as a string.
        username: Name of the comment author.
        content: Text content of the comment.
        timestamp: Human-readable formatted comment publication date.
        timestamp_raw: Original ISO 8601 timestamp.
    """

    comment_id: str
    username: str
    content: str
    timestamp: str
    timestamp_raw: str


class Article(TypedDict):
    """Represents a complete blog article.

    Attributes:
        title: Article title.
        content: Main article content.
        timestamp: Human-readable formatted publication date.
        timestamp_raw: Original ISO 8601 publication timestamp.
        comments: List of comments associated with the article.
    """

    title: str
    content: str
    timestamp: str
    timestamp_raw: str
    comments: list[Comment]


class ArticlePreview(TypedDict):
    """Represents a shortened article structure used in article listings.

    Attributes:
        title: Article title.
        timestamp: Human-readable formatted publication date.
        timestamp_raw: Original ISO 8601 publication timestamp.
        article_id: Numeric article identifier, stored as a string.
    """

    title: str
    timestamp: str
    timestamp_raw: str
    article_id: str


def format_date(date: str) -> str:
    """Converts an ISO 8601 timestamp into a human-readable date.

    Args:
        date: ISO 8601 formatted date or datetime string.

    Returns:
        A formatted date in the 'Month day year' format.
        Returns 'NaN' if the input cannot be parsed.
    """
    try:
        raw_iso_date = datetime.fromisoformat(date)
        return f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
    except ValueError, TypeError:
        return "NaN"


def exceeds_max_length(value: str, limit: int) -> bool:
    """Checks whether a string exceeds the specified character limit.

    Args:
    value: String to check.
    limit: Maximum permitted string length.

    Returns:
    True if the string is longer than the limit, otherwise False.
    """
    return len(value) > limit


def _validate_string(
    value: object,
    field: str,
    filename: str,
    *,
    max_length: int | None = None,
    allow_empty: bool = False,
) -> str:
    """Validates a string field loaded from an article JSON file.

    Checks the value type, optionally rejects empty or whitespace-only
    strings, and enforces an optional maximum length.

    Args:
        value: Value to validate.
        field: Name of the field being validated.
        filename: Name of the source file, used in error messages.
        max_length: Optional maximum permitted string length.
        allow_empty: Whether empty or whitespace-only strings are allowed.

    Returns:
        The validated string.

    Raises:
        TypeError: If the value is not a string.
        ValueError: If the value is empty when not allowed or exceeds
            the specified maximum length.
    """
    if not isinstance(value, str):
        raise TypeError(f"Invalid type for '{field}' in {filename}")

    if not allow_empty and not value.strip():
        raise ValueError(f"Empty field '{field}' in {filename}")

    if max_length is not None and len(value) > max_length:
        raise ValueError(f"Field '{field}' exceeds maximum length in {filename}")

    return value


def _validate_timestamp(value: str, field: str, filename: str) -> None:
    """Validates an ISO 8601 timestamp.

    Args:
        value: Timestamp string to validate.
        field: Name of the timestamp field.
        filename: Name of the source file, used in error messages.

    Raises:
        ValueError: If the timestamp cannot be parsed as an ISO 8601 date
            or datetime.
    """
    try:
        _ = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp '{field}' in {filename}") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Builds a dictionary while rejecting duplicate JSON object keys.

    Used as an object_pairs_hook for json.load() to prevent silently
    overwriting previously encountered keys.

    Args:
        pairs: Key-value pairs extracted from a JSON object.

    Returns:
        A dictionary containing the validated key-value pairs.

    Raises:
        ValueError: If a duplicate key is encountered.
    """
    result: dict[str, object] = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")

        result[key] = value

    return result


def _validate_fields(
    data: dict[str, object],
    required_fields: set[str],
    entity: str,
    filename: str,
) -> None:
    """Checks whether a dictionary contains exactly the required fields.

    Both missing and unexpected keys are treated as invalid data.

    Args:
        data: Dictionary containing the fields to validate.
        required_fields: Set of expected field names.
        entity: Name of the entity being validated.
        filename: Name of the source file, used in error messages.

    Raises:
        ValueError: If any required fields are missing or unexpected
            fields are present.
    """
    missing = required_fields - data.keys()
    unexpected = data.keys() - required_fields

    if missing or unexpected:
        raise ValueError(
            f"Invalid {entity} fields in {filename}: "
            + f"missing={missing}, unexpected={unexpected}"
        )


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Checks whether a value is a JSON object with string keys.

    Validates that the supplied value is a dictionary and that all
    its keys are strings, allowing its contents to be safely
    processed as JSON object values.
    """
    if not isinstance(value, dict):
        return False

    data = cast(dict[object, object], value)
    return all(isinstance(key, str) for key in data)


def _is_json_array(value: object) -> TypeGuard[list[object]]:
    """Checks whether a value is a JSON array.

    Validates that the supplied value is a list, allowing its
    elements to be processed as individual JSON values.
    """
    return isinstance(value, list)


def _read_article(path: Path) -> Article:
    """Reads and validates an article from a JSON file.

    Validates the article structure, required fields, string values,
    timestamps, comments, and comment identifiers. Duplicate JSON keys
    and duplicate comment identifiers are rejected.

    Args:
        path: Path to the article JSON file.

    Returns:
        A validated article dictionary.

    Raises:
        FileNotFoundError: If the article file does not exist.
        OSError: If the file cannot be read.
        json.JSONDecodeError: If the file contains invalid JSON.
        TypeError: If the article or comment structure contains invalid
            data types.
        ValueError: If required fields, values, timestamps, or identifiers
            are invalid.
    """
    with path.open("r", encoding="utf-8") as f:
        data = cast(object, json.load(f, object_pairs_hook=_reject_duplicate_keys))

    if not _is_json_object(data):
        raise TypeError(f"Invalid article structure: {path.name}")

    filename = path.name

    required_fields = {"title", "content", "timestamp", "timestamp_raw", "comments"}

    _ = _validate_fields(data, required_fields, "article", filename)

    _ = _validate_string(
        data["title"],
        "title",
        filename,
        max_length=config.MAX_TITLE_LENGTH,
    )

    _ = _validate_string(
        data["content"],
        "content",
        filename,
        max_length=config.MAX_CONTENT_LENGTH,
    )

    _ = _validate_string(data["timestamp"], "timestamp", filename)

    timestamp_raw = _validate_string(
        data["timestamp_raw"],
        "timestamp_raw",
        filename,
    )
    _ = _validate_timestamp(timestamp_raw, "timestamp_raw", filename)

    comments = data["comments"]

    if not _is_json_array(comments):
        raise TypeError(f"Invalid comments field: {path.name}")

    comment_fields = {"comment_id", "username", "content", "timestamp", "timestamp_raw"}

    comment_ids: set[str] = set()

    for comment in comments:
        if not _is_json_object(comment):
            raise TypeError(f"Invalid comment structure: {path.name}")

        _ = _validate_fields(comment, comment_fields, "comment", filename)

        comment_id = _validate_string(
            comment["comment_id"],
            "comment_id",
            filename,
        )

        if not comment_id.isascii() or not comment_id.isdecimal():
            raise ValueError(f"Invalid comment_id: {path.name}")
        if comment_id in comment_ids:
            raise ValueError(f"Duplicate comment_id: {filename}")

        comment_ids.add(comment_id)

        _ = _validate_string(
            comment["username"],
            "username",
            filename,
            max_length=config.MAX_USERNAME_LENGTH,
        )

        _ = _validate_string(
            comment["content"],
            "comment content",
            filename,
            max_length=config.MAX_COMMENT_LENGTH,
        )

        _ = _validate_string(comment["timestamp"], "comment timestamp", filename)

        comment_timestamp_raw = _validate_string(
            comment["timestamp_raw"], "comment timestamp_raw", filename
        )
        _ = _validate_timestamp(
            comment_timestamp_raw, "comment timestamp_raw", filename
        )
    return cast(Article, cast(object, data))


def _load_article(path: Path) -> Article:
    """Loads an article and translates low-level errors into application errors.

    Args:
        path: Path to the article JSON file.

    Returns:
        A validated article dictionary.

    Raises:
        ArticleNotFoundError: If the article file does not exist.
        InvalidArticleError: If the article contains malformed JSON
            or invalid data.
        ArticleReadError: If an operating system error prevents reading
            the article.
    """
    try:
        return _read_article(path)

    except FileNotFoundError as exc:
        raise ArticleNotFoundError(path.stem) from exc

    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise InvalidArticleError(path.stem) from exc

    except OSError as exc:
        raise ArticleReadError(path.stem) from exc


def _get_article_paths() -> list[Path]:
    """Returns paths to article JSON files with numeric filenames.

    Article files are sorted by their numeric identifiers in ascending order.
    Files with non-numeric names or unsupported extensions are ignored.

    Returns:
        A sorted list of paths to article JSON files.
    """
    return sorted(
        (path for path in config.ARTICLE_PATH.glob("*.json") if path.stem.isdecimal()),
        key=lambda path: int(path.stem),
    )


def get_article_ids() -> set[int]:
    """Collects identifiers of all existing articles.

    Returns:
        A set of numeric article identifiers.
    """
    return {int(path.stem) for path in _get_article_paths()}


@overload
def json_data_parser(file_id: int) -> Article: ...


@overload
def json_data_parser(file_id: None = None) -> list[ArticlePreview]: ...


def json_data_parser(
    file_id: int | None = None,
) -> Article | list[ArticlePreview]:
    """Loads and validates article data from the filesystem.

    When an article identifier is provided, loads the corresponding
    article and propagates application-level loading errors.

    When no identifier is provided, generates a list of article previews.
    Invalid or unreadable article files are logged and skipped rather
    than preventing the entire listing from being generated.

    Args:
        file_id: Optional numeric identifier of the article to load.
            If None, all available article previews are returned.

    Returns:
        A complete article dictionary when file_id is specified,
            otherwise a list of article previews.

    Raises:
        ArticleNotFoundError: If the requested article does not exist.
        InvalidArticleError: If the requested article contains invalid data.
        ArticleReadError: If the requested article cannot be read.
    """
    if file_id is not None:
        article_path = config.ARTICLE_PATH / f"{file_id}.json"

        try:
            return _load_article(article_path)

        except ArticleNotFoundError:
            raise

        except InvalidArticleError:
            config.logger.exception(
                "Invalid JSON in article file: %s",
                article_path.name,
            )
            raise

        except ArticleReadError:
            config.logger.exception(
                "Failed to read article file: %s",
                article_path.name,
            )
            raise

    result: list[ArticlePreview] = []

    for article in _get_article_paths():
        try:
            data = _load_article(article)
        except (
            ArticleNotFoundError,
            InvalidArticleError,
            ArticleReadError,
        ):
            config.logger.warning(
                "Skipping invalid or unreadable article file: %s",
                article.name,
                exc_info=True,
            )
            continue

        result.append(
            {
                "title": data["title"],
                "timestamp": data["timestamp"],
                "timestamp_raw": data["timestamp_raw"],
                "article_id": article.stem,
            }
        )
    return result
