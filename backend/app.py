import os

import psycopg
from flask import Flask, jsonify, request
from flask_cors import CORS
from psycopg.rows import dict_row


VALID_STATUSES = {"running", "stopped", "terminated"}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        DB_HOST=os.environ.get("DB_HOST", "127.0.0.1"),
        DB_PORT=os.environ.get("DB_PORT", "15432"),
        POSTGRES_DB=os.environ.get("POSTGRES_DB", "virtual_labs"),
        POSTGRES_USER=os.environ.get("POSTGRES_USER", "virtual_labs"),
        POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD", "change-me"),
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    def connect_database():
        if app.config["DATABASE_URL"]:
            return psycopg.connect(app.config["DATABASE_URL"], row_factory=dict_row)

        return psycopg.connect(
            host=app.config["DB_HOST"],
            port=app.config["DB_PORT"],
            dbname=app.config["POSTGRES_DB"],
            user=app.config["POSTGRES_USER"],
            password=app.config["POSTGRES_PASSWORD"],
            row_factory=dict_row,
        )

    @app.get("/api/vlabs")
    def list_vlabs():
        with connect_database() as connection:
            vlabs = connection.execute(
                """
                SELECT vlabs.id, vlabs.name, vlab_types.name AS type, vlabs.status
                FROM vlabs
                JOIN vlab_types ON vlab_types.id = vlabs.type_id
                ORDER BY vlabs.created_at DESC, vlabs.id DESC
                """
            ).fetchall()
        return jsonify(vlabs)

    @app.get("/api/vlabtype")
    def list_vlab_types():
        with connect_database() as connection:
            vlab_types = connection.execute(
                "SELECT name FROM vlab_types ORDER BY id"
            ).fetchall()
        return jsonify([vlab_type["name"] for vlab_type in vlab_types])

    @app.post("/api/vlabs")
    def create_vlab():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name", "").strip()
        vlab_type = payload.get("type")

        if not name:
            return jsonify({"error": "A laboratory name is required."}), 400

        with connect_database() as connection:
            type_row = connection.execute(
                "SELECT id FROM vlab_types WHERE name = %s",
                (vlab_type,),
            ).fetchone()
            if type_row is None:
                return jsonify({"error": "The laboratory type is invalid."}), 400

            vlab = connection.execute(
                """
                INSERT INTO vlabs (name, type_id, status)
                VALUES (%s, %s, 'stopped')
                RETURNING id, name, %s AS type, status
                """,
                (name, type_row["id"], vlab_type),
            ).fetchone()
        return jsonify(vlab), 201

    @app.put("/api/vlabs/<int:vlab_id>")
    def update_vlab_status(vlab_id):
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")

        if status not in VALID_STATUSES:
            return jsonify({"error": "The laboratory status is invalid."}), 400

        with connect_database() as connection:
            vlab = connection.execute(
                """
                UPDATE vlabs
                SET status = %s
                WHERE id = %s
                RETURNING id, name,
                    (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                    status
                """,
                (status, vlab_id),
            ).fetchone()
        if vlab is None:
            return jsonify({"error": "Laboratory not found."}), 404

        return jsonify(vlab)

    @app.delete("/api/vlabs/<int:vlab_id>")
    def delete_vlab(vlab_id):
        with connect_database() as connection:
            vlab = connection.execute(
                """
                DELETE FROM vlabs
                WHERE id = %s
                RETURNING id, name,
                    (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                    status
                """,
                (vlab_id,),
            ).fetchone()
        if vlab is None:
            return jsonify({"error": "Laboratory not found."}), 404

        return jsonify(vlab)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5050")))
