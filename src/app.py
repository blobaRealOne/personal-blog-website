import json
import os
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import ParamSpec, cast, overload

from flask import Flask, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

P = ParamSpec("P")

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"
ARTICLE_PATH.mkdir(parents=True, exist_ok=True)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


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


@overload
def json_data_parser(file_id: int, raw_date: bool = False) -> dict[str, str]: ...


@overload
def json_data_parser(
    file_id: None = None, raw_date: bool = False
) -> list[dict[str, str]]: ...


def json_data_parser(
    file_id: int | None = None,
    raw_date: bool = False,
) -> dict[str, str] | list[dict[str, str]]:
    if file_id is not None:
        article_path = ARTICLE_PATH / f"{file_id}.json"
        if not article_path.exists():
            raise FileNotFoundError
        with article_path.open("r", encoding="utf-8") as f:
            json_data = cast(dict[str, str], json.load(f))
        if not raw_date:
            try:
                raw_iso_date = datetime.fromisoformat(json_data.get("timestamp", ""))
                date = f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
            except ValueError, TypeError:
                date = "Nan"
            json_data["timestamp"] = date
        return json_data
    result: list[dict[str, str]] = []
    for article in sorted(ARTICLE_PATH.glob("*.json"), key=lambda path: int(path.stem)):
        with article.open("r", encoding="utf-8") as f:
            data = cast(dict[str, str], json.load(f))
        try:
            raw_iso_date = datetime.fromisoformat(data.get("timestamp", ""))
            date = f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
        except ValueError, TypeError:
            date = "Nan"
        result.append(
            {
                "article_title": data.get("title", ""),
                "article_timestamp": date,
                "article_name": article.stem,
            }
        )
    return result


def article_creator(
    title: str, content: str, timestamp: str, edit_by_id: int | None = None
) -> None:
    filename = edit_by_id
    payload = {"title": title, "content": content, "timestamp": timestamp}
    if filename is None:
        articles_ids = (int(path.stem) for path in ARTICLE_PATH.glob("*.json"))
        filename = max(articles_ids, default=0) + 1
    new_path = ARTICLE_PATH / f"{filename}.json"
    temp_path = new_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _ = temp_path.replace(new_path)


app = Flask(__name__)


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
    return render_template("webpage_article.html", article=article_data)


@app.get("/admin")
@admin_auth
def adminpage_get_handler():
    articles_data = json_data_parser()
    return render_template("webpage_admin.html", articles_data=articles_data)


@app.post("/delete/<int:delete_id>")
@admin_auth
def deletepage_post_handler(delete_id: int):
    path = ARTICLE_PATH / f"{delete_id}.json"
    if path.exists():
        path.unlink()
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

    try:
        create_timestamp = datetime.fromisoformat(article_publishing_date)
    except ValueError:
        abort(400)

    _ = article_creator(article_title, article_content, create_timestamp.isoformat())

    return redirect(url_for("adminpage_get_handler"))


@app.get("/edit/<int:edit_article_id>")
@admin_auth
def editpage_get_handler(edit_article_id: int):
    try:
        article_data = json_data_parser(edit_article_id, raw_date=True)
    except FileNotFoundError:
        abort(404)
    return render_template("webpage_edit.html", article=article_data)


@app.post("/edit/<int:edit_article_id>")
@admin_auth
def editpage_post_handler(edit_article_id: int):
    article_edition_dict = {
        "title": request.form.get("title", "").strip(),
        "content": request.form.get("content", "").strip(),
        "timestamp": request.form.get("publishing_date", "").strip(),
    }
    try:
        article_dict = json_data_parser(edit_article_id, raw_date=True)
    except FileNotFoundError:
        abort(404)

    if any(not value for value in article_edition_dict.values()):
        abort(400)

    try:
        article_edition_dict["timestamp"] = datetime.fromisoformat(
            article_edition_dict["timestamp"]
        ).isoformat()
    except ValueError:
        abort(400)

    article_dict.update(
        {
            key: value
            for key, value in article_edition_dict.items()
            if value != article_dict[key]
        }
    )
    _ = article_creator(
        title=article_dict["title"],
        content=article_dict["content"],
        timestamp=article_dict["timestamp"],
        edit_by_id=edit_article_id,
    )
    return redirect(url_for("adminpage_get_handler"))
