#!/usr/bin/env python3

from datetime import datetime
import os
import tarfile
import hashlib
import humanize
import sqlite3
import json
from flask import Flask, jsonify, abort, send_from_directory, g, render_template, request, url_for, redirect
from slugify import slugify
from werkzeug.utils import secure_filename
from pygments import highlight
from pygments.lexers import guess_lexer_for_filename
from pygments.formatters import HtmlFormatter

# TODO: Move these to a config file
APP_BASE_PATH = ""
STATIC_PATH = os.path.join(APP_BASE_PATH, "static")
SSL_CERT_PATH = os.path.join(APP_BASE_PATH, "server.pem")
DATABASE = os.path.join(APP_BASE_PATH, "data.db")
BASE_URL = "https://example.com"
ALLOWED_RELEASE_FILE_EXTS = ["py", "png", "txt", "json", "yml", "yaml", "html", "htm", "js"]
RELEASE_FILE_PATH = os.path.join(STATIC_PATH, "releases")
EGG_PATH = os.path.join(STATIC_PATH, "eggs")

LISTEN_ADDR = "0.0.0.0"
LISTEN_PORT = 443

app = Flask(__name__)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def get_categories():
    cur = get_db().cursor()
    cur.execute("SELECT id, name FROM category")
    categories = []
    for cat in cur.fetchall():
        categories.append({
            "id": cat[0],
            "name": cat[1]
        })
    return categories


def get_statuses():
    cur = get_db().cursor()
    cur.execute("SELECT id, name FROM status")
    statuses = []
    for status in cur.fetchall():
        statuses.append({
            "id": status[0],
            "name": status[1]
        })
    return statuses


def get_apps(slug=None):
    cur = get_db().cursor()

    query = """
        SELECT
            a.id,
            a.name,
            a.slug,
            u.name,
            a.description,
            c.name,
            s.name,
            a.download_count,
            e.version,
            e.created_at,
            a.created_at,
            a.newest_egg_id,
            c.slug
        FROM app a
            JOIN user u ON u.id = a.user_id
            JOIN category c ON c.id = a.category_id
            JOIN status s ON s.id = a.status_id
            LEFT JOIN egg e ON e.id = a.newest_egg_id
    """

    params = []

    if slug is not None:
        query += " WHERE a.slug = ?"
        params.append(slug)

    query += " ORDER BY e.created_at DESC, a.id DESC"

    cur.execute(query, params)

    apps = []

    for app in cur.fetchall():
        apps.append({
            "id": app[0],
            "name": app[1],
            "slug": app[2],
            "user": app[3],
            "desc": app[4],
            "category": app[5],
            "status": app[6],
            "dl_count": app[7],
            "version": app[8],
            "last_release": app[9],
            "created_at": app[10],
            "newest_egg_id": app[11],
            "category_slug": app[12]
        })
    return apps


def get_eggs(app, include_not_released=False):
    cur = get_db().cursor()

    query = """
        SELECT
            id,
            version,
            released,
            size,
            size_unpacked,
            created_at,
            hash
        FROM egg
        WHERE app_id = ?
    """
    if not include_not_released:
        query += " AND released = 1"
    cur.execute(query, (app["id"],))

    eggs = []

    for egg in cur.fetchall():
        eggs.append({
            "id": egg[0],
            "version": egg[1],
            "released": egg[2],
            "size": egg[3],
            "size_unpacked": egg[4],
            "created_at": egg[5],
            "hash": egg[6]
        })
    return eggs


def get_newest_egg_files(app):
    cur = get_db().cursor()

    query = """
        SELECT
            id,
            upload_name,
            local_name,
            size,
            created_at,
            hash
        FROM egg_file
        WHERE egg_id = ?
    """
    cur.execute(query, (app["newest_egg_id"],))

    files = []
    for file in cur.fetchall():
        files.append({
            "id": file[0],
            "name": file[1],
            "size": file[3],
            "created_at": file[4],
            "hash": file[5]
        })
    return files


@app.template_filter("humanizets")
def humanize_timestamp(ts):
    # Convert timestamp to datetime
    if ts is None:
        return "-"
    return humanize.naturaltime(datetime.fromtimestamp(int(ts)))


@app.template_filter("tstodatestr")
def ts_to_datestr(ts):
    if ts is None:
        return "-"
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S GMT")


@app.route("/")
def main():
    return "Nothing here yet"


@app.route("/apps")
def apps():
    # List apps
    # TODO: Filter out non-released apps
    apps = get_apps()
    return render_template("apps.html", apps=apps)


@app.route("/apps/<slug>")
def app_page(slug):
    # Get app by slug
    matched_apps = get_apps(slug=slug)
    if len(matched_apps) == 0:
        # No such app
        # TODO: Better error page
        return abort(404)
    cur_app = matched_apps[0]
    # Get releases for this app
    eggs = get_eggs(cur_app, include_not_released=False)
    # Get newest release files
    egg_files = get_newest_egg_files(cur_app)
    return render_template("app.html", app=cur_app, eggs=eggs, files=egg_files)


# TODO: Ensure that no user can create app named "create" etc.
@app.route("/apps/create", methods=["GET"])
def app_create_page():
    categories = get_categories()
    statuses = get_statuses()
    return render_template("create_app.html", categories=categories, statuses=statuses)


@app.route("/apps/create", methods=["POST"])
def app_create():
    conn = get_db()
    cur = conn.cursor()

    name = request.form["name"]
    description = request.form["description"]
    category_id = request.form["category"]
    status_id = request.form["status"]

    try:
        category_id = int(category_id)
    except:
        # TODO: Better error handling
        return "Invalid category"

    try:
        status_id = int(status_id)
    except:
        # TODO: Better error handling
        return "Invalid status"

    name_len = len(name)
    if name_len < 1 or name_len > 20:
        # Invalid length
        # TODO: Better error handling
        return "Name length must be between 1 and 20 characters"

    if len(description) > 5000:
        # Too long description
        # TODO: Better error handling
        return "Too long description. Maximum description length is 5000 characters"

    # Check if the app name is already in use
    cur.execute("SELECT COUNT(*) FROM app WHERE LOWER(name) = ?", (name.lower(),))
    name_count = cur.fetchone()[0]
    if name_count > 0:
        # App name already in use, don't allow
        # TODO: Better error handling
        return "Name already in use, choose another"

    # Create slug
    slug = slugify(name, max_length=20, word_boundary=True)
    while True:
        # Check if the slug is already in use
        cur.execute("SELECT COUNT(*) FROM app WHERE slug = ?", (slug,))
        slug_count = cur.fetchone()[0]
        if slug_count == 0:
            # Free slug, use it
            break
        # Slug in use
        if len(slug) >= 30:
            # Abort, too long slug for us
            # The user must choose another name
            # TODO: Better error handling
            return "Failed to create app, please choose another name"
        # Add dash
        slug += "-"

    # Insert into database
    # TODO: Get user id from session
    try:
        cur.execute("""
            INSERT INTO app (
                name, slug, user_id, description, category_id, status_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?
            )
        """,
        (name, slug, 1, description, category_id, status_id))
        conn.commit()
    except:
        # TODO: Better error handling
        return "Database error"

    return redirect(url_for("app_page", slug=slug))


@app.route("/apps/<slug>/release", methods=["GET"])
def app_create_release_page(slug):
    apps = get_apps(slug=slug)
    if len(apps) == 0:
        # TODO: Better error handling
        abort(404)
    return render_template("create_release.html", app=apps[0])


@app.route("/apps/<slug>/release", methods=["POST"])
def app_create_release(slug):
    # TODO: Cleanup on error

    apps = get_apps(slug=slug)
    if len(apps) == 0:
        # TODO: Better error handling
        abort(404)
    cur_app = apps[0]

    released = request.form.get("released") is not None
    uploaded_files = request.files.getlist("files")

    if len(uploaded_files) == 0:
        # No uploaded files
        # TODO: Better error handling
        return "Upload some files! At least '__init__.py' is needed to create a release"

    uploaded_filenames = [file.filename for file in uploaded_files]

    if "__init__.py" not in uploaded_filenames:
        # No __init__.py
        # TODO: Better error handling
        return "At least '__init__.py' is needed to create a release"

    if "metadata.json" in uploaded_filenames:
        # TODO: Better error handling
        return "'metadata.json' is an illegal file name"

    # Get the next version number for this release
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT version FROM egg WHERE app_id = ? ORDER BY version DESC LIMIT 1", (cur_app["id"],))
    resp = cur.fetchone()
    if resp is None:
        # No previous version, this release is 1
        new_version_num = 1
    else:
        # Previous release exists, bump version by one
        new_version_num = resp[0] + 1

    # Create folder for this upload
    release_folder_path = os.path.join(RELEASE_FILE_PATH, "%s-%d" % (slug, new_version_num))
    os.mkdir(release_folder_path)

    stored_files = []
    uncompressed_total_size = 0

    for file in uploaded_files:
        fname = file.filename
        if "." in fname and fname.rsplit(".", 1)[1].lower() in ALLOWED_RELEASE_FILE_EXTS:
            # Allowed, save to the release folder
            secure_name = secure_filename(fname)
            local_path = os.path.join(release_folder_path, secure_name)
            file.save(local_path)
            fsize = os.path.getsize(local_path)
            uncompressed_total_size += fsize
            stored_files.append((fname, secure_name, fsize))
        else:
            # Not allowed filename
            # TODO: Better error handling
            return "Invalid filename(s)"

    # Create hash for this release
    md5 = hashlib.md5()
    md5.update(b"%s-%d" % (cur_app["name"].encode("utf-8"), new_version_num))
    egg_hash = md5.hexdigest()

    # Create metadata file
    metadata = {
        "name": cur_app["name"],
        "description": cur_app["desc"],
        "category": cur_app["category_slug"],
        "author": "-",  # TODO: Get the user name
        "revision": new_version_num
    }
    metadata_path = os.path.join(release_folder_path, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

    stored_files.append(("metadata.json", "metadata.json", os.path.getsize(metadata_path)))

    # Create tarball
    tarball_path = os.path.join(EGG_PATH, "%s.tar.gz" % (egg_hash,))
    with tarfile.open(tarball_path, "w:gz") as tgz:
        # Add uploaded files
        for fname, secure_name, _ in stored_files:
            file_path = os.path.join(release_folder_path, secure_name)
            arc_path = os.path.join(cur_app["slug"], fname)
            tgz.add(file_path, arcname=arc_path)

    # Tarball created, get compressed size
    compressed_total_size = os.path.getsize(tarball_path)

    # Create egg entry
    cur.execute("""
        INSERT INTO egg (
            app_id, version, released, size, size_unpacked, hash)
        VALUES (
            ?, ?, ?, ?, ?, ?
        )
    """, (cur_app["id"], new_version_num, released, compressed_total_size, uncompressed_total_size, egg_hash))
    new_egg_id = cur.lastrowid

    # Set latest released egg ID if needed
    if released:
        cur.execute("UPDATE app SET newest_egg_id = ? WHERE id = ?", (new_egg_id, cur_app["id"]))

    # Create egg_file entries
    for fname, secure_name, fsize in stored_files:
        # TODO: Mimetype?
        if fname == "metadata.json":
            # Skip metadata
            continue
        fpath = os.path.join(release_folder_path, secure_name)
        # Hash file
        md5 = hashlib.md5()
        with open(fpath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        fhash = md5.hexdigest()
        cur.execute("""
            INSERT INTO egg_file (
                egg_id, upload_name, local_name, size, hash)
            VALUES (?, ?, ?, ?, ?)""", (new_egg_id, fname, secure_name, fsize, fhash))

    # All done, commit
    conn.commit()

    return redirect(url_for("app_page", slug=slug))


@app.route("/apps/<slug>/files/<fhash>")
def show_release_file(slug, fhash):
    cur = get_db().cursor()

    # Get app
    apps = get_apps(slug=slug)
    if len(apps) == 0:
        # TODO: Better error handling
        abort(404)
    cur_app = apps[0]

    # Get file info
    cur.execute("""
        SELECT
            ef.upload_name,
            ef.local_name,
            ef.size,
            ef.created_at,
            ef.hash,
            e.version
        FROM egg_file ef
            JOIN egg e ON e.id = ef.egg_id
            JOIN app a ON a.id = e.app_id
        WHERE e.id = a.newest_egg_id AND a.id = ? AND ef.hash = ?
    """, (cur_app["id"], fhash))

    info = cur.fetchone()
    if info is None:
        # TODO: Better error handling
        abort(404)

    # Get file content
    rel_folder = "%s-%d" % (slug, info[5])
    with open(os.path.join(RELEASE_FILE_PATH, rel_folder, info[1]), "rb") as f:
        content = f.read()

    # Highlight content (if needed)
    lexer = guess_lexer_for_filename(info[0], content)
    formatter = HtmlFormatter(style="monokai", linenos="inline", nobackground=True)
    highlight_styles = formatter.get_style_defs(".highlight")
    highlight_content = highlight(content, lexer, formatter)

    fileinfo = {
        "name": info[0],
        "size": info[2],
        "created_at": info[3],
        "content": content,
        "highlight_styles": highlight_styles,
        "highlight_content": highlight_content
    }

    return render_template("app_file.html", app=cur_app, file=fileinfo)


@app.route("/eggs/categories/json")
def categories():
    cur = get_db().cursor()
    cur.execute("""
        SELECT
            name,
            slug,
            (
                SELECT
                    COUNT(id)
                FROM app
                WHERE category_id = category.id
                    AND (
                        SELECT
                            COUNT(id)
                        FROM egg
                        WHERE app_id = app.id
                            AND released = 1
                    ) > 0
            ) AS egg_count
        FROM category""")
    res = cur.fetchall()
    categories = []
    for row in res:
        categories.append({"name": row[0], "slug": row[1], "eggs": row[2]})

    return jsonify(categories)


@app.route("/eggs/category/<category_name>/json")
def category_apps(category_name):
    # Get apps in the category
    cur = get_db().cursor()
    cur.execute("""
        SELECT
            app.name,
            app.slug,
            app.description,
            app.download_count,
            status.slug,
            egg.version,
            egg.size,
            egg.size_unpacked,
            category.slug
        FROM app
        JOIN
            status ON status.id = app.status_id,
            egg ON egg.id = app.newest_egg_id,
            category ON category.slug = ?""",
        (category_name,))

    apps = cur.fetchall()
    apps_list = []
    for app in apps:
        apps_list.append({
            "name": app[0],
            "slug": app[1],
            "description": app[2],
            "download_counter": app[3],
            "status": app[4],
            "revision": app[5],
            "size_of_zip": app[6],
            "size_of_content": app[7],
            "category": app[8]
        })

    return jsonify(apps_list)


@app.route("/eggs/get/<name>/json")
def get(name):
    # Get release data from the database
    cur = get_db().cursor()
    cur.execute("""
        SELECT
            egg.version,
            app.description,
            app.name,
            app.slug,
            category.slug,
            egg.hash
        FROM app
        JOIN
            category ON category.id = app.category_id,
            egg ON egg.app_id = app.id AND released = 1
        WHERE app.slug = ?
        ORDER BY app.id ASC, egg.version DESC""",
        (name,))

    releases = {}
    data = cur.fetchall()

    # There is no app with the given slug
    if len(data) == 0:
        abort(404)

    newest_version = str(data[0][0])
    for release in data:
        releases[str(release[0])] = [{
            "url": "%s/eggs/%s.tar.gz" % (BASE_URL, release[5],)
        }]

    return jsonify({
        "info": {
            "version": newest_version
        },
        "description": data[0][1],
        "name": data[0][2],
        "category": data[0][4],
        "releases": releases
    })


@app.route("/eggs/<egg_hash>.tar.gz")
def get_egg(egg_hash):
    # TODO: Check that egg_hash really seems to be MD5 hash
    return send_from_directory(EGG_PATH, "%s.tar.gz" % (egg_hash,))


# @app.get("/eggs/")

if __name__ == "__main__":
    app.run(host=LISTEN_ADDR, port=LISTEN_PORT, ssl_context=(SSL_CERT_PATH,), use_reloader=True, debug=True)
