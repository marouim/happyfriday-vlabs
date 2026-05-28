import os

import psycopg
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from psycopg.rows import dict_row


VALID_STATUS_UPDATES = {"running", "stopped", "terminated"}
ACTION_JOB_TEMPLATE_FIELDS = {
    "running": ("start", "aap_start_job_template_id", "starting"),
    "stopped": ("stop", "aap_stop_job_template_id", "stopping"),
}
FAILED_AAP_STATUSES = {"canceled", "error", "failed"}
PENDING_VLAB_STATUSES = {"deleting", "starting", "stopping"}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        DB_HOST=os.environ.get("DB_HOST", "127.0.0.1"),
        DB_PORT=os.environ.get("DB_PORT", "15432"),
        POSTGRES_DB=os.environ.get("POSTGRES_DB", "virtual_labs"),
        POSTGRES_USER=os.environ.get("POSTGRES_USER", "virtual_labs"),
        POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD", "change-me"),
        AAP_BASE_URL=os.environ.get("AAP_BASE_URL", "").rstrip("/"),
        AAP_TOKEN=os.environ.get("AAP_TOKEN") or os.environ.get("AAP_OAUTH_TOKEN", ""),
        AAP_REQUEST_TIMEOUT=float(os.environ.get("AAP_REQUEST_TIMEOUT", "30")),
        AAP_VERIFY_SSL=os.environ.get("AAP_VERIFY_SSL", "true").lower()
        not in {"0", "false", "no"},
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

    def serialize_vlab(row):
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "status": row["status"],
        }

    def launch_aap_job_template(vlab, action, job_template_id):
        if not app.config["AAP_BASE_URL"]:
            return None, "AAP_BASE_URL is not configured."
        if not app.config["AAP_TOKEN"]:
            return None, "AAP_TOKEN is not configured."
        if job_template_id is None:
            return None, f"No AAP {action} job template is configured for {vlab['type']}."

        url = (
            f"{app.config['AAP_BASE_URL']}/api/controller/v2/job_templates/"
            f"{job_template_id}/launch/"
        )
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {app.config['AAP_TOKEN']}",
                    "Content-Type": "application/json",
                },
                json={
                    "extra_vars": {
                        "vlab_id": vlab["id"],
                        "vlab_name": vlab["name"],
                        "vlab_type": vlab["type"],
                        "vlab_action": action,
                    }
                },
                timeout=app.config["AAP_REQUEST_TIMEOUT"],
                verify=app.config["AAP_VERIFY_SSL"],
            )
        except requests.RequestException as error:
            return None, f"AAP job template launch failed: {error}"

        if not response.ok:
            return (
                None,
                "AAP job template launch failed "
                f"with HTTP {response.status_code}: {response.text}",
            )

        try:
            payload = response.json()
        except ValueError:
            return None, "AAP job template launch response was not valid JSON."

        job_id = payload.get("job") or payload.get("id")
        if job_id is None:
            return None, "AAP job template launch response did not include a job ID."

        return job_id, None

    def get_aap_job_status(job_id):
        url = f"{app.config['AAP_BASE_URL']}/api/controller/v2/jobs/{job_id}/"
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {app.config['AAP_TOKEN']}"},
                timeout=app.config["AAP_REQUEST_TIMEOUT"],
                verify=app.config["AAP_VERIFY_SSL"],
            )
        except requests.RequestException:
            return None

        if not response.ok:
            return None

        try:
            return response.json().get("status")
        except ValueError:
            return None

    def refresh_pending_vlabs(connection, vlabs):
        for vlab in vlabs:
            if vlab["status"] not in PENDING_VLAB_STATUSES or not vlab.get("aap_job_id"):
                continue

            job_status = get_aap_job_status(vlab["aap_job_id"])
            if job_status == "successful":
                if vlab["status"] == "deleting":
                    connection.execute(
                        "DELETE FROM vlabs WHERE id = %s",
                        (vlab["id"],),
                    )
                    vlab["_deleted"] = True
                    continue

                updated_vlab = connection.execute(
                    """
                    UPDATE vlabs
                    SET status = aap_target_status,
                        aap_target_status = NULL,
                        aap_last_job_status = %s
                    WHERE id = %s
                    RETURNING id, name,
                        (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                        status,
                        aap_job_id,
                        aap_target_status,
                        aap_last_job_status
                    """,
                    (job_status, vlab["id"]),
                ).fetchone()
                vlab.update(updated_vlab)
            elif job_status in FAILED_AAP_STATUSES:
                updated_vlab = connection.execute(
                    """
                    UPDATE vlabs
                    SET status = 'failed',
                        aap_target_status = NULL,
                        aap_last_job_status = %s
                    WHERE id = %s
                    RETURNING id, name,
                        (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                        status,
                        aap_job_id,
                        aap_target_status,
                        aap_last_job_status
                    """,
                    (job_status, vlab["id"]),
                ).fetchone()
                vlab.update(updated_vlab)

        vlabs[:] = [vlab for vlab in vlabs if not vlab.get("_deleted")]

    @app.get("/api/vlabs")
    def list_vlabs():
        with connect_database() as connection:
            vlabs = connection.execute(
                """
                SELECT vlabs.id, vlabs.name, vlab_types.name AS type, vlabs.status,
                    vlabs.aap_job_id, vlabs.aap_target_status, vlabs.aap_last_job_status
                FROM vlabs
                JOIN vlab_types ON vlab_types.id = vlabs.type_id
                ORDER BY vlabs.created_at DESC, vlabs.id DESC
                """
            ).fetchall()
            refresh_pending_vlabs(connection, vlabs)
        return jsonify([serialize_vlab(vlab) for vlab in vlabs])

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

        if status not in VALID_STATUS_UPDATES:
            return jsonify({"error": "The laboratory status is invalid."}), 400

        job_template = ACTION_JOB_TEMPLATE_FIELDS.get(status)
        if job_template:
            action, job_template_field, pending_status = job_template
            with connect_database() as connection:
                vlab = connection.execute(
                    """
                    SELECT vlabs.id, vlabs.name, vlab_types.name AS type,
                        vlab_types.aap_start_job_template_id,
                        vlab_types.aap_stop_job_template_id,
                        vlabs.status
                    FROM vlabs
                    JOIN vlab_types ON vlab_types.id = vlabs.type_id
                    WHERE vlabs.id = %s
                    """,
                    (vlab_id,),
                ).fetchone()
            if vlab is None:
                return jsonify({"error": "Laboratory not found."}), 404

            job_id, launch_error = launch_aap_job_template(vlab, action, vlab[job_template_field])
            if launch_error:
                with connect_database() as connection:
                    failed_vlab = connection.execute(
                        """
                        UPDATE vlabs
                        SET status = 'failed',
                            aap_target_status = NULL,
                            aap_last_job_status = 'launch_failed'
                        WHERE id = %s
                        RETURNING id, name,
                            (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                            status
                        """,
                        (vlab_id,),
                    ).fetchone()
                if failed_vlab is not None:
                    vlab = failed_vlab
                return jsonify({"error": launch_error, "vlab": serialize_vlab(vlab)}), 502

            with connect_database() as connection:
                vlab = connection.execute(
                    """
                    UPDATE vlabs
                    SET status = %s,
                        aap_job_id = %s,
                        aap_target_status = %s,
                        aap_last_job_status = 'launched'
                    WHERE id = %s
                    RETURNING id, name,
                        (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                        status
                    """,
                    (pending_status, job_id, status, vlab_id),
                ).fetchone()
            return jsonify(serialize_vlab(vlab))

        with connect_database() as connection:
            vlab = connection.execute(
                """
                UPDATE vlabs
                SET status = %s,
                    aap_target_status = NULL
                WHERE id = %s
                RETURNING id, name,
                    (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                    status
                """,
                (status, vlab_id),
            ).fetchone()
        if vlab is None:
            return jsonify({"error": "Laboratory not found."}), 404

        return jsonify(serialize_vlab(vlab))

    @app.delete("/api/vlabs/<int:vlab_id>")
    def delete_vlab(vlab_id):
        with connect_database() as connection:
            vlab = connection.execute(
                """
                SELECT vlabs.id, vlabs.name, vlab_types.name AS type,
                    vlab_types.aap_delete_job_template_id,
                    vlabs.status
                FROM vlabs
                JOIN vlab_types ON vlab_types.id = vlabs.type_id
                WHERE vlabs.id = %s
                """,
                (vlab_id,),
            ).fetchone()
        if vlab is None:
            return jsonify({"error": "Laboratory not found."}), 404

        job_id, launch_error = launch_aap_job_template(
            vlab,
            "delete",
            vlab["aap_delete_job_template_id"],
        )
        if launch_error:
            with connect_database() as connection:
                failed_vlab = connection.execute(
                    """
                    UPDATE vlabs
                    SET status = 'failed',
                        aap_target_status = NULL,
                        aap_last_job_status = 'launch_failed'
                    WHERE id = %s
                    RETURNING id, name,
                        (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                        status
                    """,
                    (vlab_id,),
                ).fetchone()
            if failed_vlab is not None:
                vlab = failed_vlab
            return jsonify({"error": launch_error, "vlab": serialize_vlab(vlab)}), 502

        with connect_database() as connection:
            vlab = connection.execute(
                """
                UPDATE vlabs
                SET status = 'deleting',
                    aap_job_id = %s,
                    aap_target_status = 'deleted',
                    aap_last_job_status = 'launched'
                WHERE id = %s
                RETURNING id, name,
                    (SELECT name FROM vlab_types WHERE id = type_id) AS type,
                    status
                """,
                (job_id, vlab_id),
            ).fetchone()

        return jsonify(serialize_vlab(vlab))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5050")))
