"""HTTP routes and request handlers for the blog application.

Defines the main Flask blueprint and its request handlers for
public article browsing, commenting, and administrator operations.

Also provides administrator authentication and request validation
for article and comment management.
"""
from datetime import datetime
from functools import wraps
from typing import Callable

from flask import (
    Blueprint,
    # ResponseReturnValue,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from . import config
from .json_parsers import (
    ArticleNotFoundError,
    ArticleReadError,
    InvalidArticleError,
    _exceeds_max_length,
    _format_date,
    _get_article_ids,
    json_data_parser,
)
from .services import save_article

main = Blueprint("main", __name__)

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
            or auth.username != config.ADMIN_USER
            or auth.password != config.ADMIN_PASSWORD
        ):
            config.logger.warning(
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

@main.get("/")
def mainpage_get_handler():
    """Redirects visitors to the homepage."""
    return redirect(url_for("main.homepage_get_handler"))


@main.get("/home")
def homepage_get_handler() -> str:
    """Renders the homepage with a list of available article previews."""
    articles_data = json_data_parser()
    return render_template("webpage_head.html", articles_data=articles_data)


@main.get("/article/<int:article_id>")
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


@main.get("/article/<int:article_id>/comment")
def commentpage_get_handler(article_id: int):
    """Displays the comment submission form for an existing article.

    Args:
        article_id: Identifier of the article receiving the comment.
    """
    if article_id not in _get_article_ids():
        abort(404)
    return render_template("webpage_comment.html", article_id=article_id)


@main.post("/article/<int:article_id>/comment")
def commentpage_post_handler(article_id: int):
    """Validates and saves a new comment submitted by a visitor.

    Assigns a new comment identifier, preserves existing article data,
    and redirects the visitor to the updated article.

    The operation is protected by the article lock to prevent concurrent
    modifications within the current process.

    Args:
        article_id: Identifier of the article receiving the comment.
    """
    with config.ARTICLE_LOCK:
        comment_username = request.form.get("comment_username", "").strip()
        comment_content = request.form.get("comment_content", "").strip()

        if not comment_username or not comment_content:
            abort(400)

        if _exceeds_max_length(
            comment_username, config.MAX_USERNAME_LENGTH
        ) or _exceeds_max_length(comment_content, config.MAX_COMMENT_LENGTH):
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

        config.logger.info(
            "Added comment: article_id=%s, comment_id=%s",
            article_id,
            comment_id,
        )

        return redirect(url_for("main.articlepage_get_handler", article_id=article_id))


@main.get("/admin")
@admin_auth
def adminpage_get_handler():
    """Displays the administrator dashboard.

    Requires successful HTTP Basic Authentication.
    """
    articles_data = json_data_parser()
    return render_template("webpage_admin.html", articles_data=articles_data)


@main.post("/delete/<int:delete_id>")
@admin_auth
def deletepage_post_handler(delete_id: int):
    """Deletes an article.

    Requires administrator authentication and executes the deletion
    while holding the article lock.

    Args:
        delete_id: Identifier of the article to delete.
    """
    with config.ARTICLE_LOCK:
        path = config.ARTICLE_PATH / f"{delete_id}.json"
        try:
            path.unlink()
        except FileNotFoundError:
            config.logger.warning(
                "Attempted to delete non-existent article: id=%s",
                delete_id,
            )
        else:
            config.logger.info("Deleted article: id=%s", delete_id)
    return redirect(url_for("main.adminpage_get_handler"))


@main.get("/new")
@admin_auth
def newpage_get_handler():
    """Displays the form for creating a new article.

    Requires administrator authentication.
    """
    return render_template("webpage_new.html")


@main.post("/new")
@admin_auth
def newpage_post_handler():
    """Validates and creates a new article.

    Validates the submitted title, publication date, and content before
    saving the article and redirecting to the administrator dashboard.

    Requires administrator authentication.
    """
    with config.ARTICLE_LOCK:
        article_title = request.form.get("title", "").strip()
        article_publishing_date = request.form.get("publishing_date", "").strip()
        article_content = request.form.get("content", "").strip()

        if not article_title or not article_publishing_date or not article_content:
            abort(400)

        if (_exceeds_max_length(article_title, config.MAX_TITLE_LENGTH)) or (
            _exceeds_max_length(article_content, config.MAX_CONTENT_LENGTH)
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

        return redirect(url_for("main.adminpage_get_handler"))


@main.get("/edit/<int:edit_article_id>")
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


@main.post("/edit/<int:edit_article_id>")
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
    with config.ARTICLE_LOCK:
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
                article_edition_dict["title"], config.MAX_TITLE_LENGTH
            ) or _exceeds_max_length(
                article_edition_dict["content"], config.MAX_CONTENT_LENGTH
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
            config.logger.info(
                "Deleted comment: article_id=%s, comment_id=%s",
                edit_article_id,
                comment_to_delete,
            )

        return redirect(url_for("main.adminpage_get_handler"))
