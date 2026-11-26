"""Application services for article management.

Provides functions responsible for creating and updating article
records in JSON files.

Article data is serialized using UTF-8 encoding and written through
temporary files to reduce the risk of partially written records.
"""
import json

from . import config
from .json_parsers import Article, Comment, _format_date, _get_article_ids, json_data_parser


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

    new_path = config.ARTICLE_PATH / f"{filename}.json"

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
        config.logger.exception(
            "Failed to save article: %s",
            new_path.name,
        )
        raise

    action = "Updated" if edit_by_id is not None else "Created"

    config.logger.info(
        "%s article: id=%s, title=%r",
        action,
        filename,
        title,
    )
