import json
import os
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import TypedDict, overload

from flask import Flask, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue


class Comment(TypedDict):
    comment_id: str
    username: str
    content: str
    timestamp: str
    timestamp_raw: str


class Article(TypedDict):
    title: str
    content: str
    timestamp: str
    timestamp_raw: str
    comments: list[Comment]


class ArticlePreview(TypedDict):
    title: str
    timestamp: str
    timestamp_raw: str
    article_id: str


BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

ARTICLE_LOCK = Lock()

MAX_TITLE_LENGTH = 120
MAX_CONTENT_LENGTH = 50_000
MAX_USERNAME_LENGTH = 40
MAX_COMMENT_LENGTH = 3_000


def admin_auth[**P](
    view: Callable[P, ResponseReturnValue],
) -> Callable[P, ResponseReturnValue]:
    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> ResponseReturnValue:
        auth = request.authorization
        if (
            auth is None
            or auth.username != ADMIN_USER
            or auth.password != ADMIN_PASSWORD
        ):
            return (
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin"'},
            )
        return view(*args, **kwargs)

    return wrapped


def _format_date(date: str) -> str:
    try:
        raw_iso_date = datetime.fromisoformat(date)
        return f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
    except ValueError, TypeError:
        return "NaN"


def _exceeds_max_length(value: str, limit: int) -> bool:
    return len(value) > limit


def _read_article(path: Path) -> Article:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise TypeError(f"Invalid article structure: {path.name}")

    required_fields = {"title", "content", "timestamp", "timestamp_raw", "comments"}

    if not required_fields.issubset(data):
        raise ValueError(f"Missing article fields: {path.name}")

    string_fields = {"title", "content", "timestamp", "timestamp_raw"}

    try:
        if not all(isinstance(data[key], str) for key in string_fields):
            raise ValueError(f"Invalid article field types: {path.name}")
    except KeyError:
        raise KeyError(f"Invalid article field types: {path.name}")

    if not isinstance(data["comments"], list):
        raise TypeError(f"Invalid comments field: {path.name}")

    comment_fields = {"comment_id", "username", "content", "timestamp", "timestamp_raw"}

    for comment in data["comments"]:
        if not isinstance(comment, dict):
            raise TypeError(f"Invalid comment structure: {path.name}")

        if not comment_fields.issubset(comment):
            raise ValueError(f"Missing comment fields: {path.name}")

        try:
            if not all(isinstance(comment[key], str) for key in comment_fields):
                raise ValueError(f"Invalid comment field types: {path.name}")
        except KeyError:
            raise KeyError(f"Invalid comment field types: {path.name}")
    return data


def _get_article_paths() -> list[Path]:
    return sorted(
        (path for path in ARTICLE_PATH.glob("*.json") if path.stem.isdecimal()),
        key=lambda path: int(path.stem),
    )


@overload
def json_data_parser(file_id: int) -> Article: ...


@overload
def json_data_parser(file_id: None = None) -> list[ArticlePreview]: ...


def json_data_parser(
    file_id: int | None = None,
) -> Article | list[ArticlePreview]:
    if file_id is not None:
        article_path = ARTICLE_PATH / f"{file_id}.json"

        if not article_path.exists():
            raise FileNotFoundError

        try:
            json_data = _read_article(article_path)
        except ValueError, TypeError, KeyError:
            # TODO
            # Add logging
            raise FileNotFoundError
        except OSError, json.JSONDecodeError:
            raise RuntimeError

        return json_data

    result: list[ArticlePreview] = []

    for article in _get_article_paths():
        try:
            data = _read_article(article)
        except json.JSONDecodeError, ValueError, OSError, TypeError, KeyError:
            # TODO
            # Put logging.exception() here, and just add more logging generally
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
    with ARTICLE_LOCK:
        filename = edit_by_id
        if filename is None:
            # TODO
            # Somehow put there _get_article_paths() fucn, as
            # they almost identical, but putting directly breaking it
            articles_ids = (
                int(path.stem)
                for path in ARTICLE_PATH.glob("*.json")
                if path.stem.isdecimal()
            )
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
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _ = temp_path.replace(new_path)


def create_app() -> Flask:
    app = Flask(__name__)
    ARTICLE_PATH.mkdir(parents=True, exist_ok=True)
    return app


app = create_app()


@app.get("/")
def mainpage_get_handler():
    return redirect(url_for("homepage_get_handler"))


@app.get("/home")
def homepage_get_handler() -> str:
    articles_data = json_data_parser()
    return render_template("webpage_head.html", articles_data=articles_data)


@app.get("/article/<int:article_id>")
def articlepage_get_handler(article_id: int):
    try:
        article_data = json_data_parser(article_id)
    except FileNotFoundError:
        abort(404)
    except RuntimeError:
        abort(500)
    return render_template(
        "webpage_article.html", article=article_data, article_id=article_id
    )


@app.get("/article/<int:article_id>/comment")
def commentpage_get_handler(article_id: int):
    return render_template("webpage_comment.html", article_id=article_id)


@app.post("/article/<int:article_id>/comment")
def commentpage_post_handler(article_id: int):
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
    except FileNotFoundError:
        abort(400)
    except RuntimeError:
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
    return redirect(url_for("articlepage_get_handler", article_id=article_id))


@app.get("/admin")
@admin_auth
def adminpage_get_handler():
    articles_data = json_data_parser()
    return render_template("webpage_admin.html", articles_data=articles_data)


@app.post("/delete/<int:delete_id>")
@admin_auth
def deletepage_post_handler(delete_id: int):
    path = ARTICLE_PATH / f"{delete_id}.json"
    with ARTICLE_LOCK:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return redirect(url_for("adminpage_get_handler"))


@app.get("/new")
@admin_auth
def newpage_get_handler():
    return render_template("webpage_new.html")


@app.post("/new")
@admin_auth
def newpage_post_handler():
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
    try:
        article_data = json_data_parser(edit_article_id)
    except FileNotFoundError:
        abort(404)
    except RuntimeError:
        abort(500)

    return render_template(
        "webpage_edit.html", article=article_data, edit_article_id=edit_article_id
    )


@app.post("/edit/<int:edit_article_id>")
@admin_auth
def editpage_post_handler(edit_article_id: int):
    try:
        article_dict = json_data_parser(edit_article_id)
    except FileNotFoundError:
        abort(404)
    except RuntimeError:
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
        ) or _exceeds_max_length(article_edition_dict["content"], MAX_CONTENT_LENGTH):
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

    return redirect(url_for("adminpage_get_handler"))
