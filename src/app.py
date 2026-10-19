import json
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import cast

from flask import Flask, abort, redirect, render_template, request, url_for

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"
ARTICLE_PATH.mkdir(parents=True, exist_ok=True)

ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin"


# TODO Add anotations to this wraper
def admin_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
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
    for article in ARTICLE_PATH.glob("*.json"):
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


def _renumber_articles() -> None:
    # TODO
    # later fix whatever this is into something normal and actually working
    articles = sorted(ARTICLE_PATH.glob("*.json"), key=lambda path: int(path.stem))
    temporary_paths: list[Path] = []

    for _, article_path in enumerate(articles, start=1):
        temporary_path = article_path.with_suffix(".tmp")
        _ = article_path.rename(temporary_path)
        temporary_paths.append(temporary_path)

    for index, temporary_path in enumerate(temporary_paths, start=1):
        _ = temporary_path.rename(ARTICLE_PATH / f"{index}.json")


def article_creator(
    title: str, content: str, timestamp: str, edit_by_id: int | None = None
) -> None:
    _ = _renumber_articles()
    filename = edit_by_id
    payload = {"title": title, "content": content, "timestamp": timestamp}
    if filename is None:
        articles_ids = (int(path.stem) for path in ARTICLE_PATH.glob("*.json"))
        filename = max(articles_ids, default=0) + 1
    # TODO Add validation that "filename" exist withing files when edit_by_id flag used
    # or not i honestly don’t know
    new_path = ARTICLE_PATH / f"{filename}.json"
    with new_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


app = Flask(__name__)


@app.get("/")
def mainpage_get_handler():
    return redirect(url_for("homepage_get_handler"))


@app.get("/home")
def homepage_get_handler() -> str:
    articles_data = cast(list[dict[str, str]], json_data_parser())
    return render_template("webpage_head.html", articles_data=articles_data)


@app.get("/article/<int:article_id>")
def articlepage_get_handler(article_id: int):
    try:
        article_data = cast(dict[str, str], json_data_parser(article_id))
    except FileNotFoundError:
        abort(404)
    return render_template("webpage_article.html", article=article_data)


@app.get("/admin")
@admin_auth
def adminpage_get_handler():
    articles_data = cast(list[dict[str, str]], json_data_parser())
    return render_template("webpage_admin.html", articles_data=articles_data)


@app.post("/delete/<int:delete_id>")
@admin_auth
def deletepage_post_handler(delete_id: int):
    path = ARTICLE_PATH / f"{delete_id}.json"
    if path.exists():
        path.unlink()
    _ = _renumber_articles()
    return redirect(url_for("adminpage_get_handler"))


@app.get("/new")
@admin_auth
def newpage_get_handler():
    return render_template("webpage_new.html")


@app.post("/new")
@admin_auth
def newpage_post_handler():
    article_title = request.form["title"]
    article_publishing_date = request.form["publishing_date"]
    article_content = request.form["content"]

    create_timestamp = datetime.fromisoformat(article_publishing_date)
    create_timestamp_iso = create_timestamp.isoformat()

    _ = article_creator(article_title, article_content, create_timestamp_iso)

    return redirect(url_for("adminpage_get_handler"))


@app.get("/edit/<int:edit_article_id>")
@admin_auth
def editpage_get_handler(edit_article_id: int):
    return render_template("webpage_edit.html")


@app.post("/edit/<int:edit_article_id>")
@admin_auth
def editpage_post_handler(edit_article_id: int):
    article_edition_dict = {
        "title": request.form.get("title"),
        "content": request.form.get("content"),
        "timestamp": request.form.get("publishing_date"),
    }
    article_dict = cast(
        dict[str, str], json_data_parser(edit_article_id, raw_date=True)
    )
    article_dict.update(
        {k: v for k, v in article_edition_dict.items() if v is not None and v != ""}
    )
    _ = article_creator(
        title=article_dict["title"],
        content=article_dict["content"],
        timestamp=article_dict["timestamp"],
        edit_by_id=edit_article_id,
    )
    return redirect(url_for("adminpage_get_handler"))
