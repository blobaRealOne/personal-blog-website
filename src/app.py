from flask import Flask, render_template, redirect, url_for, abort
from pathlib import Path
import json
from typing import cast

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

def json_data_parser(file_id = None):
    if file_id is not None:
        article_path = ARTICLE_PATH / f"{file_id}.json"
        if not article_path.exists():
            raise FileNotFoundError
        with article_path.open("r", encoding="utf-8") as f:
            return cast(dict[str, str], json.load(f))
    result = []
    for article in ARTICLE_PATH.glob("*.json"):
        with article.open("r", encoding="utf-8") as f:
            data = cast(dict[str, str], json.load(f))
        result.append({"article_name": data.get("title", ""), "article_timestamp": data.get("ctime", "")})
    return result



app = Flask(__name__)


@app.get("/")
def mainpage_get_handler():
    return redirect(url_for("homepage_get_handler"))

@app.get("/home")
def homepage_get_handler() -> str:
    articles_data = json_data_parser()
    return render_template("webpage_main.html", articles_data = articles_data)

@app.get("/article/<int:article_id>")
def articlepage_get_handler(article_id: int):
    chosen_file = ARTICLE_PATH / f"{article_id}.json"
    try:
        article_payload = json.loads(chosen_file.read_text(encoding="UTF-8"))
    except FileNotFoundError:
        abort(404)
    return "<p>hello</p>"
