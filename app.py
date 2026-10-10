"""
app.py - Flask server for AccessLens AI.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

from flask import Flask, jsonify, render_template, request

import models
import text_processor

app = Flask(__name__)

MAX_CHARS = 20000
MIN_WORDS = 3

# Create the SQLite database and tables automatically on startup.
models.init_db()


def error(message, status=400):
    """Consistent JSON error response used by every API route."""
    return jsonify({"error": message}), status


def serialize_record(row):
    """Turn a history row into the JSON the frontend needs (including safe highlighted HTML)."""
    highlighted, counts = text_processor.highlight_html(row["simplified_text"])
    return {
        "id": row["id"],
        "original": row["original_text"],
        "simplified": row["simplified_text"],
        "html": highlighted,
        "counts": counts,
        "highlight_count": row["highlight_count"],
        "created_at": row["created_at"],
        "before": {"words": row["words_before"], "avg_sentence": row["avg_sentence_before"],
                   "ease": row["ease_before"]},
        "after": {"words": row["words_after"], "avg_sentence": row["avg_sentence_after"],
                  "ease": row["ease_after"]},
    }


# ------------------------------------------------------------------- pages
@app.route("/")
def index():
    # Saved preferences are passed to the template so they are applied before the page paints.
    return render_template("index.html", prefs=models.get_preferences())


# ------------------------------------------------------------- preferences
@app.route("/api/preferences", methods=["GET"])
def get_preferences():
    return jsonify(models.get_preferences())


@app.route("/api/preferences", methods=["PUT"])
def save_preferences():
    data = request.get_json(silent=True)
    try:
        return jsonify(models.update_preferences(data))
    except ValueError as exc:
        return error(str(exc))


@app.route("/api/preferences/reset", methods=["POST"])
def reset_preferences():
    return jsonify(models.reset_preferences())


# ----------------------------------------------------------------- process
@app.route("/api/process", methods=["POST"])
def process_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return error("Please enter some text to simplify.")
    text = text.strip()
    if len(text) > MAX_CHARS:
        return error(f"Text is too long. The limit is {MAX_CHARS:,} characters.")
    if len(text.split()) < MIN_WORDS:
        return error(f"Please enter at least {MIN_WORDS} words.")

    result = text_processor.process(text)
    record_id = models.add_history(text, result)
    return jsonify(serialize_record(models.get_history_item(record_id))), 201


# ----------------------------------------------------------------- history
@app.route("/api/history", methods=["GET"])
def list_history():
    return jsonify(models.get_history_list())


@app.route("/api/history/<int:item_id>", methods=["GET"])
def get_history_item(item_id):
    row = models.get_history_item(item_id)
    if row is None:
        return error("That history item no longer exists.", 404)
    return jsonify(serialize_record(row))


@app.route("/api/history/<int:item_id>", methods=["DELETE"])
def delete_history_item(item_id):
    if not models.delete_history_item(item_id):
        return error("That history item no longer exists.", 404)
    return jsonify({"deleted": item_id})


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    return jsonify({"deleted": models.clear_history()})


# ------------------------------------------------------------------- stats
@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify(models.get_stats())


# ---------------------------------------------------------- error handlers
@app.errorhandler(404)
def not_found(exc):
    if request.path.startswith("/api/"):
        return error("API route not found.", 404)
    return exc


@app.errorhandler(405)
def bad_method(exc):
    if request.path.startswith("/api/"):
        return error("Method not allowed.", 405)
    return exc


@app.errorhandler(500)
def server_error(exc):
    if request.path.startswith("/api/"):
        return error("Something went wrong on the server.", 500)
    return exc


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
