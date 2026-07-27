from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response
)

import csv
import io
import sqlite3

from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = "change-this-to-a-long-private-secret-key"

DATABASE = "office_day.db"


BRANDS = [
    "WALL STREET",
    "SAHARA",
    "CRITERION",
    "ULTIMO",
    "ARROW",
    "VAN HEUSEN",
    "IZOD"
]


PURPOSES = [
    "Submit Report",
    "Regular Office Day",
    "Office Day Requested by Sales Department",
    "Other"
]


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('SALES', 'HR')),
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS office_day_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            store_assignment TEXT NOT NULL,
            brand TEXT NOT NULL,
            requested_date TEXT NOT NULL,
            purpose TEXT NOT NULL,
            other_purpose TEXT,
            remarks TEXT,
            requested_by INTEGER NOT NULL,
            requested_by_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending HR Approval',
            approved_date TEXT,
            adjustment_reason TEXT,
            hr_action_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requested_by) REFERENCES users(id)
        )
        """
    )

    hr_account = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
        """,
        ("hradmin",)
    ).fetchone()

    if hr_account is None:
        connection.execute(
            """
            INSERT INTO users (
                full_name,
                username,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "HR Administrator",
                "hradmin",
                generate_password_hash("hr12345"),
                "HR"
            )
        )

    sales_account = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
        """,
        ("salesuser",)
    ).fetchone()

    if sales_account is None:
        connection.execute(
            """
            INSERT INTO users (
                full_name,
                username,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "Sales Department",
                "salesuser",
                generate_password_hash("sales12345"),
                "SALES"
            )
        )

    sample_employees = [
        "Juan Dela Cruz",
        "Maria Santos",
        "Ana Reyes"
    ]

    for employee in sample_employees:
        connection.execute(
            """
            INSERT OR IGNORE INTO employees (
                employee_name
            )
            VALUES (?)
            """,
            (employee,)
        )

    sample_stores = [
        "SM MEGAMALL",
        "SM MALL OF ASIA",
        "SM NORTH EDSA",
        "ROBINSONS ERMITA",
        "LANDMARK MAKATI"
    ]

    for store in sample_stores:
        connection.execute(
            """
            INSERT OR IGNORE INTO stores (
                store_name
            )
            VALUES (?)
            """,
            (store,)
        )

    connection.commit()
    connection.close()


def login_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return decorated_function


def role_required(required_role):
    def decorator(view_function):

        @wraps(view_function)
        def decorated_function(*args, **kwargs):

            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))

            if session.get("role") != required_role:
                flash(
                    "You are not authorized to access that page.",
                    "error"
                )

                if session.get("role") == "HR":
                    return redirect(url_for("hr_dashboard"))

                return redirect(url_for("sales_dashboard"))

            return view_function(*args, **kwargs)

        return decorated_function

    return decorator


@app.route("/")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "HR":
        return redirect(url_for("hr_dashboard"))

    return redirect(url_for("sales_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            AND is_active = 1
            """,
            (username,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password"],
            password
        ):
            session.clear()

            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "HR":
                return redirect(url_for("hr_dashboard"))

            return redirect(url_for("sales_dashboard"))

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


@app.route("/sales")
@role_required("SALES")
def sales_dashboard():

    connection = get_db_connection()

    employees = connection.execute(
        """
        SELECT *
        FROM employees
        WHERE is_active = 1
        ORDER BY employee_name
        """
    ).fetchall()

    stores = connection.execute(
        """
        SELECT *
        FROM stores
        WHERE is_active = 1
        ORDER BY store_name
        """
    ).fetchall()

    office_requests = connection.execute(
        """
        SELECT *
        FROM office_day_requests
        WHERE requested_by = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "sales_dashboard.html",
        employees=employees,
        stores=stores,
        brands=BRANDS,
        purposes=PURPOSES,
        office_requests=office_requests
    )


@app.route(
    "/sales/submit-request",
    methods=["POST"]
)
@role_required("SALES")
def submit_request():

    employee_name = request.form.get(
        "employee_name",
        ""
    ).strip()

    store_assignment = request.form.get(
        "store_assignment",
        ""
    ).strip()

    brand = request.form.get(
        "brand",
        ""
    ).strip()

    requested_date = request.form.get(
        "requested_date",
        ""
    ).strip()

    purpose = request.form.get(
        "purpose",
        ""
    ).strip()

    other_purpose = request.form.get(
        "other_purpose",
        ""
    ).strip()

    remarks = request.form.get(
        "remarks",
        ""
    ).strip()

    if not employee_name:
        flash(
            "Please select an employee or demo.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    if not store_assignment:
        flash(
            "Please select a store assignment.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    if brand not in BRANDS:
        flash(
            "Please select a valid brand.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    if not requested_date:
        flash(
            "Please select an Office Day date.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    if purpose not in PURPOSES:
        flash(
            "Please select a valid purpose.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    if purpose == "Other" and not other_purpose:
        flash(
            "Please specify the other purpose.",
            "error"
        )
        return redirect(url_for("sales_dashboard"))

    connection = get_db_connection()

    employee_exists = connection.execute(
        """
        SELECT id
        FROM employees
        WHERE employee_name = ?
        AND is_active = 1
        """,
        (employee_name,)
    ).fetchone()

    store_exists = connection.execute(
        """
        SELECT id
        FROM stores
        WHERE store_name = ?
        AND is_active = 1
        """,
        (store_assignment,)
    ).fetchone()

    if employee_exists is None:
        connection.close()

        flash(
            "The selected employee is not registered.",
            "error"
        )

        return redirect(url_for("sales_dashboard"))

    if store_exists is None:
        connection.close()

        flash(
            "The selected store is not registered.",
            "error"
        )

        return redirect(url_for("sales_dashboard"))

    connection.execute(
        """
        INSERT INTO office_day_requests (
            employee_name,
            store_assignment,
            brand,
            requested_date,
            purpose,
            other_purpose,
            remarks,
            requested_by,
            requested_by_name,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employee_name,
            store_assignment,
            brand,
            requested_date,
            purpose,
            other_purpose,
            remarks,
            session["user_id"],
            session["full_name"],
            "Pending HR Approval"
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Office Day request submitted successfully.",
        "success"
    )

    return redirect(url_for("sales_dashboard"))


@app.route("/hr")
@role_required("HR")
def hr_dashboard():

    connection = get_db_connection()

    office_requests = connection.execute(
        """
        SELECT *
        FROM office_day_requests
        ORDER BY
            CASE
                WHEN status = 'Pending HR Approval'
                THEN 1

                WHEN status = 'Adjusted Schedule'
                THEN 2

                ELSE 3
            END,
            created_at DESC
        """
    ).fetchall()

    employees = connection.execute(
        """
        SELECT *
        FROM employees
        ORDER BY employee_name
        """
    ).fetchall()

    stores = connection.execute(
        """
        SELECT *
        FROM stores
        ORDER BY store_name
        """
    ).fetchall()

    sales_accounts = connection.execute(
        """
        SELECT
            id,
            full_name,
            username,
            is_active
        FROM users
        WHERE role = 'SALES'
        ORDER BY full_name
        """
    ).fetchall()

    connection.close()

    return render_template(
        "hr_dashboard.html",
        office_requests=office_requests,
        employees=employees,
        stores=stores,
        sales_accounts=sales_accounts
    )


@app.route(
    "/hr/request/<int:request_id>/approve",
    methods=["POST"]
)
@role_required("HR")
def approve_request(request_id):

    connection = get_db_connection()

    office_request = connection.execute(
        """
        SELECT *
        FROM office_day_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if office_request is None:
        connection.close()

        flash(
            "Office Day request not found.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection.execute(
        """
        UPDATE office_day_requests
        SET
            status = ?,
            approved_date = requested_date,
            adjustment_reason = NULL,
            hr_action_by = ?
        WHERE id = ?
        """,
        (
            "Approved",
            session["full_name"],
            request_id
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Office Day request approved.",
        "success"
    )

    return redirect(url_for("hr_dashboard"))


@app.route(
    "/hr/request/<int:request_id>/adjust",
    methods=["POST"]
)
@role_required("HR")
def adjust_request(request_id):

    adjusted_date = request.form.get(
        "adjusted_date",
        ""
    ).strip()

    adjustment_reason = request.form.get(
        "adjustment_reason",
        ""
    ).strip()

    if not adjusted_date:
        flash(
            "Please provide the adjusted schedule.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    if not adjustment_reason:
        flash(
            "Please provide the reason for adjustment.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection = get_db_connection()

    office_request = connection.execute(
        """
        SELECT id
        FROM office_day_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if office_request is None:
        connection.close()

        flash(
            "Office Day request not found.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection.execute(
        """
        UPDATE office_day_requests
        SET
            status = ?,
            approved_date = ?,
            adjustment_reason = ?,
            hr_action_by = ?
        WHERE id = ?
        """,
        (
            "Adjusted Schedule",
            adjusted_date,
            adjustment_reason,
            session["full_name"],
            request_id
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Adjusted Office Day schedule saved.",
        "success"
    )

    return redirect(url_for("hr_dashboard"))


@app.route(
    "/hr/request/<int:request_id>/reject",
    methods=["POST"]
)
@role_required("HR")
def reject_request(request_id):

    rejection_reason = request.form.get(
        "rejection_reason",
        ""
    ).strip()

    if not rejection_reason:
        flash(
            "Please provide the reason for rejection.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection = get_db_connection()

    office_request = connection.execute(
        """
        SELECT id
        FROM office_day_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if office_request is None:
        connection.close()

        flash(
            "Office Day request not found.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection.execute(
        """
        UPDATE office_day_requests
        SET
            status = ?,
            approved_date = NULL,
            adjustment_reason = ?,
            hr_action_by = ?
        WHERE id = ?
        """,
        (
            "Rejected",
            rejection_reason,
            session["full_name"],
            request_id
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Office Day request rejected.",
        "success"
    )

    return redirect(url_for("hr_dashboard"))


@app.route(
    "/hr/add-employee",
    methods=["POST"]
)
@role_required("HR")
def add_employee():

    employee_name = request.form.get(
        "employee_name",
        ""
    ).strip()

    if not employee_name:
        flash(
            "Employee or demo name is required.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection = get_db_connection()

    try:
        connection.execute(
            """
            INSERT INTO employees (
                employee_name
            )
            VALUES (?)
            """,
            (employee_name,)
        )

        connection.commit()

        flash(
            "Employee or demo added successfully.",
            "success"
        )

    except sqlite3.IntegrityError:
        flash(
            "Employee or demo name already exists.",
            "error"
        )

    finally:
        connection.close()

    return redirect(url_for("hr_dashboard"))


@app.route(
    "/hr/add-store",
    methods=["POST"]
)
@role_required("HR")
def add_store():

    store_name = request.form.get(
        "store_name",
        ""
    ).strip().upper()

    if not store_name:
        flash(
            "Store name is required.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection = get_db_connection()

    try:
        connection.execute(
            """
            INSERT INTO stores (
                store_name
            )
            VALUES (?)
            """,
            (store_name,)
        )

        connection.commit()

        flash(
            "Store added successfully.",
            "success"
        )

    except sqlite3.IntegrityError:
        flash(
            "Store already exists.",
            "error"
        )

    finally:
        connection.close()

    return redirect(url_for("hr_dashboard"))


@app.route(
    "/hr/create-sales-account",
    methods=["POST"]
)
@role_required("HR")
def create_sales_account():

    full_name = request.form.get(
        "full_name",
        ""
    ).strip()

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not full_name or not username or not password:
        flash(
            "Complete all Sales account fields.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    if len(password) < 8:
        flash(
            "Password must have at least 8 characters.",
            "error"
        )

        return redirect(url_for("hr_dashboard"))

    connection = get_db_connection()

    try:
        connection.execute(
            """
            INSERT INTO users (
                full_name,
                username,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                full_name,
                username,
                generate_password_hash(password),
                "SALES"
            )
        )

        connection.commit()

        flash(
            "Sales account created successfully.",
            "success"
        )

    except sqlite3.IntegrityError:
        flash(
            "Username already exists.",
            "error"
        )

    finally:
        connection.close()



    return redirect(url_for("hr_dashboard"))


@app.route("/hr/export-employees")
@role_required("HR")
def export_employees():
    connection = get_db_connection()

    employees = connection.execute(
        """
        SELECT employee_name
        FROM employees
        WHERE is_active = 1
        ORDER BY employee_name
        """
    ).fetchall()

    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Employee Name"])

    for employee in employees:
        writer.writerow([employee["employee_name"]])

    csv_content = "\ufeff" + output.getvalue()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=employee_names.csv"
        }
    )


@app.route("/hr/export-stores")
@role_required("HR")
def export_stores():
    connection = get_db_connection()

    stores = connection.execute(
        """
        SELECT store_name
        FROM stores
        WHERE is_active = 1
        ORDER BY store_name
        """
    ).fetchall()

    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Store Name"])

    for store in stores:
        writer.writerow([store["store_name"]])

    csv_content = "\ufeff" + output.getvalue()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=store_names.csv"
        }
    )

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)