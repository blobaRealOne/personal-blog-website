"""Flask-based personal blog application.

Provides article management, public commenting, administrator
authentication, JSON-based article storage, and file logging.

Article data is stored as individual JSON files in the articles directory.
"""
import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import TypedDict, overload, Any

from flask import Flask, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_wtf.csrf import CSRFProtect


class ArticleNotFoundError(Exception):
    """Raised when the requested article does not exist."""
    pass


class InvalidArticleError(Exception):
    """Raised when an article contains invalid or malformed data."""
    pass


class ArticleReadError(Exception):
    """Raised when an article cannot be read due to an I/O error."""
    pass


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


BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
SECRET_KEY = os.environ.get("SECRET_KEY", "secret_key")

ARTICLE_LOCK = Lock()

MAX_TITLE_LENGTH = 120
MAX_CONTENT_LENGTH = 50_000
MAX_USERNAME_LENGTH = 40
MAX_COMMENT_LENGTH = 3_000


logger = logging.getLogger("personal_blog")


def admin_auth[**P](
    view: Callable[P, ResponseReturnValue],
) -> Callable[P, ResponseReturnValue]:
    """Restricts access to a view to authenticated administrators.

    Validates HTTP Basic Authentication credentials against the configured
    administrator username and password.

    Failed authentication attempts are logged and result in an HTTP 401
    response with a Basic Authentication challenge.

    Args:
        view: Flask view function requiring administrator authentication.

    Returns:
        A wrapped view function that performs authentication before
        executing the original view.
    """
    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> ResponseReturnValue:
        auth = request.authorization
        if (
            auth is None
            or auth.username != ADMIN_USER
            or auth.password != ADMIN_PASSWORD
        ):
            logger.warning(
                "Failed admin authentication attempt from %s",
                request.remote_addr,
            )

            return (
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin"'},
            )
        return view(*args, **kwargs)

    return wrapped


def _format_date(date: str) -> str:
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


def _exceeds_max_length(value: str, limit: int) -> bool:
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


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
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
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")

        result[key] = value

    return result

def _validate_fields(
    data: dict[str, Any],
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
        data = json.load(f, object_pairs_hook=_reject_duplicate_keys)

    filename = path.name

    if not isinstance(data, dict):
        raise TypeError(f"Invalid article structure: {path.name}")

    required_fields = {"title", "content", "timestamp", "timestamp_raw", "comments"}

    _ = _validate_fields(data, required_fields, "article", filename)

    _ = _validate_string(
        data["title"],
        "title",
        filename,
        max_length=MAX_TITLE_LENGTH,
    )

    _ = _validate_string(
        data["content"],
        "content",
        filename,
        max_length=MAX_CONTENT_LENGTH,
    )

    _ = _validate_string(data["timestamp"], "timestamp", filename)

    timestamp_raw = _validate_string(
        data["timestamp_raw"],
        "timestamp_raw",
        filename,
    )
    _ = _validate_timestamp(timestamp_raw, "timestamp_raw", filename)

    comments = data["comments"]

    if not isinstance(comments, list):
        raise TypeError(f"Invalid comments field: {path.name}")

    comment_fields = {"comment_id", "username", "content", "timestamp", "timestamp_raw"}

    comment_ids = set()

    for comment in comments:
        if not isinstance(comment, dict):
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
            max_length=MAX_USERNAME_LENGTH,
        )

        _ = _validate_string(
            comment["content"],
            "comment content",
            filename,
            max_length=MAX_COMMENT_LENGTH,
        )

        _ = _validate_string(comment["timestamp"], "comment timestamp", filename)

        comment_timestamp_raw = _validate_string(
            comment["timestamp_raw"], "comment timestamp_raw", filename
        )
        _ = _validate_timestamp(
            comment_timestamp_raw, "comment timestamp_raw", filename
        )
    return data

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
        (path for path in ARTICLE_PATH.glob("*.json") if path.stem.isdecimal()),
        key=lambda path: int(path.stem),
    )


def _get_article_ids() -> set[int]:
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
        article_path = ARTICLE_PATH / f"{file_id}.json"

        try:
            return _load_article(article_path)

        except ArticleNotFoundError:
            raise

        except InvalidArticleError:
            logger.exception(
                "Invalid JSON in article file: %s",
                article_path.name,
            )
            raise

        except ArticleReadError:
            logger.exception(
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
            logger.warning(
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


def save_article(
    title: str,
    content: str,
    timestamp_raw: str,
    comments: list[Comment] | None = None,
    edit_by_id: int | None = None,
) -> None:
    """Creates a new article or updates an existing one.

    Serializes article data into JSON and writes it to a temporary file
    before replacing the destination file. Existing comments are preserved
    when updating an article without explicitly providing a comment list.

    New article identifiers are generated using the highest existing
    numeric identifier plus one.

    Args:
        title: Article title.
        content: Main article content.
        timestamp_raw: Original ISO 8601 publication timestamp.
        comments: Optional list of comments. If omitted, existing comments
            are preserved when updating an article.
        edit_by_id: Identifier of the article to update. If None, a new
            article is created.

    Raises:
        OSError: If the article cannot be written or the destination
            file cannot be replaced.
        TypeError: If the data cannot be serialized into JSON.
        ValueError: If the data contains values unsupported by JSON encoding.
    """
    filename = edit_by_id
    if filename is None:
        articles_ids = _get_article_ids()
        filename = max(articles_ids, default=0) + 1

    new_path = ARTICLE_PATH / f"{filename}.json"

    if comments is None:
        if new_path.exists():
            comments = json_data_parser(filename).get("comments", [])
        else:
            comments = []

    temp_path = new_path.with_suffix(".json.tmp")
    timestamp = _format_date(timestamp_raw)
    payload: Article = {
        "title": title,
        "content": content,
        "timestamp": timestamp,
        "timestamp_raw": timestamp_raw,
        "comments": comments,
    }
    try:
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _ = temp_path.replace(new_path)
    except OSError, TypeError, ValueError:
        logger.exception(
            "Failed to save article: %s",
            new_path.name,
        )
        raise

    action = "Updated" if edit_by_id is not None else "Created"

    logger.info(
        "%s article: id=%s, title=%r",
        action,
        filename,
        title,
    )


def configure_file_logging() -> None:
    """Configures rotating file logging for the application.

    Creates a RotatingFileHandler that writes logs to logfile.log.
    The log file is limited to 1 MB, with up to three backup files retained.

    Avoids registering another handler if the same log file is already
    configured.

    The application logger is configured at INFO level and propagation
    to parent loggers is disabled.
    """
    log_path = (BASE_PATH / "logfile.log").resolve()

    for handler in logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == log_path
        ):
            return

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - [%(levelname)s] %(name)s -> %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def create_app() -> Flask:
    """Creates and configures the Flask application.

    Configures the application secret key, maximum request size, CSRF
    protection, file logging, and the directory used to store articles.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    _ = configure_file_logging()
    _ = CSRFProtect(app)
    ARTICLE_PATH.mkdir(parents=True, exist_ok=True)
    return app


app = create_app()


@app.get("/")
def mainpage_get_handler():
    """Redirects visitors to the homepage."""
    return redirect(url_for("homepage_get_handler"))


@app.get("/home")
def homepage_get_handler() -> str:
    """Renders the homepage with a list of available article previews."""
    articles_data = json_data_parser()
    return render_template("webpage_head.html", articles_data=articles_data)


@app.get("/article/<int:article_id>")
def articlepage_get_handler(article_id: int):
    """Displays a complete article and its comments.

    Returns HTTP 404 if the article does not exist and HTTP 500 if
    its data is invalid or cannot be read.

    Args:
        article_id: Identifier of the requested article.
    """
    try:
        article_data = json_data_parser(article_id)

    except ArticleNotFoundError:
        abort(404)
    except InvalidArticleError,  ArticleReadError:
        abort(500)
    return render_template(
        "webpage_article.html", article=article_data, article_id=article_id
    )


@app.get("/article/<int:article_id>/comment")
def commentpage_get_handler(article_id: int):
    """Displays the comment submission form for an existing article.

    Args:
        article_id: Identifier of the article receiving the comment.
    """
    if article_id not in _get_article_ids():
        abort(404)
    return render_template("webpage_comment.html", article_id=article_id)


@app.post("/article/<int:article_id>/comment")
def commentpage_post_handler(article_id: int):
    """Validates and saves a new comment submitted by a visitor.

    Assigns a new comment identifier, preserves existing article data,
    and redirects the visitor to the updated article.

    The operation is protected by the article lock to prevent concurrent
    modifications within the current process.

    Args:
        article_id: Identifier of the article receiving the comment.
    """
    with ARTICLE_LOCK:
        comment_username = request.form.get("comment_username", "").strip()
        comment_content = request.form.get("comment_content", "").strip()

        if not comment_username or not comment_content:
            abort(400)

        if _exceeds_max_length(
            comment_username, MAX_USERNAME_LENGTH
        ) or _exceeds_max_length(comment_content, MAX_COMMENT_LENGTH):
            abort(400)

        comment_date_raw = datetime.now().isoformat()
        comment_date = _format_date(comment_date_raw)

        try:
            article = json_data_parser(article_id)
        except ArticleNotFoundError:
            abort(404)
        except InvalidArticleError, ArticleReadError:
            abort(500)

        comments = article.get("comments", [])
        comment_id = (
            max((int(comment["comment_id"]) for comment in comments), default=0) + 1
        )

        comment: Comment = {
            "comment_id": str(comment_id),
            "username": comment_username,
            "content": comment_content,
            "timestamp": comment_date,
            "timestamp_raw": comment_date_raw,
        }

        article["comments"].append(comment)

        _ = save_article(
            title=article["title"],
            content=article["content"],
            timestamp_raw=article["timestamp_raw"],
            comments=article["comments"],
            edit_by_id=article_id,
        )

        logger.info(
            "Added comment: article_id=%s, comment_id=%s",
            article_id,
            comment_id,
        )

        return redirect(url_for("articlepage_get_handler", article_id=article_id))


@app.get("/admin")
@admin_auth
def adminpage_get_handler():
    """Displays the administrator dashboard.

    Requires successful HTTP Basic Authentication.
    """
    articles_data = json_data_parser()
    return render_template("webpage_admin.html", articles_data=articles_data)


@app.post("/delete/<int:delete_id>")
@admin_auth
def deletepage_post_handler(delete_id: int):
    """Deletes an article.

    Requires administrator authentication and executes the deletion
    while holding the article lock.

    Args:
        delete_id: Identifier of the article to delete.
    """
    with ARTICLE_LOCK:
        path = ARTICLE_PATH / f"{delete_id}.json"
        try:
            path.unlink()
        except FileNotFoundError:
            logger.warning(
                "Attempted to delete non-existent article: id=%s",
                delete_id,
            )
        else:
            logger.info("Deleted article: id=%s", delete_id)
        return redirect(url_for("adminpage_get_handler"))


@app.get("/new")
@admin_auth
def newpage_get_handler():
    """Displays the form for creating a new article.

    Requires administrator authentication.
    """
    return render_template("webpage_new.html")


@app.post("/new")
@admin_auth
def newpage_post_handler():
    """Validates and creates a new article.

    Validates the submitted title, publication date, and content before
    saving the article and redirecting to the administrator dashboard.

    Requires administrator authentication.
    """
    with ARTICLE_LOCK:
        article_title = request.form.get("title", "").strip()
        article_publishing_date = request.form.get("publishing_date", "").strip()
        article_content = request.form.get("content", "").strip()

        if not article_title or not article_publishing_date or not article_content:
            abort(400)

        if (_exceeds_max_length(article_title, MAX_TITLE_LENGTH)) or (
            _exceeds_max_length(article_content, MAX_CONTENT_LENGTH)
        ):
            abort(400)

        try:
            timestamp = datetime.fromisoformat(article_publishing_date)
        except ValueError:
            abort(400)

        _ = save_article(
            title=article_title,
            content=article_content,
            timestamp_raw=timestamp.isoformat(),
        )

        return redirect(url_for("adminpage_get_handler"))


@app.get("/edit/<int:edit_article_id>")
@admin_auth
def editpage_get_handler(edit_article_id: int):
    """Displays the editing form for an existing article.

    Requires administrator authentication.

    Args:
        edit_article_id: Identifier of the article to edit.
    """
    try:
        article_data = json_data_parser(edit_article_id)
    except ArticleNotFoundError:
        abort(404)
    except InvalidArticleError, ArticleReadError:
        abort(500)

    return render_template(
        "webpage_edit.html", article=article_data, edit_article_id=edit_article_id
    )


@app.post("/edit/<int:edit_article_id>")
@admin_auth
def editpage_post_handler(edit_article_id: int):
    """Updates an article or removes one of its comments.

    When a comment deletion identifier is supplied, removes the matching
    comment while preserving the rest of the article.

    Otherwise, validates and updates the article title, content, and
    publication date.

    Requires administrator authentication.

    Args:
        edit_article_id: Identifier of the article to modify.
    """
    with ARTICLE_LOCK:
        try:
            article_dict = json_data_parser(edit_article_id)
        except ArticleNotFoundError:
            abort(404)
        except InvalidArticleError, ArticleReadError:
            abort(500)

        comment_to_delete = request.args.get("deletion_comment_id")

        if comment_to_delete is not None:
            article_dict["comments"] = [
                comment
                for comment in article_dict["comments"]
                if comment["comment_id"] != comment_to_delete
            ]
        else:
            article_edition_dict = {
                "title": request.form.get("title", "").strip(),
                "content": request.form.get("content", "").strip(),
                "timestamp_raw": request.form.get("publishing_date", "").strip(),
            }

            if any(not value for value in article_edition_dict.values()):
                abort(400)

            if _exceeds_max_length(
                article_edition_dict["title"], MAX_TITLE_LENGTH
            ) or _exceeds_max_length(
                article_edition_dict["content"], MAX_CONTENT_LENGTH
            ):
                abort(400)

            try:
                timestamp_raw = datetime.fromisoformat(
                    article_edition_dict["timestamp_raw"]
                ).isoformat()
            except ValueError:
                abort(400)

            article_dict["title"] = article_edition_dict["title"]
            article_dict["content"] = article_edition_dict["content"]
            article_dict["timestamp_raw"] = timestamp_raw

        _ = save_article(
            title=article_dict["title"],
            content=article_dict["content"],
            timestamp_raw=article_dict["timestamp_raw"],
            comments=article_dict["comments"],
            edit_by_id=edit_article_id,
        )

        if comment_to_delete is not None:
            logger.info(
                "Deleted comment: article_id=%s, comment_id=%s",
                edit_article_id,
                comment_to_delete,
            )

        return redirect(url_for("adminpage_get_handler"))
