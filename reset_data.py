"""
Reset operational/test data while retaining all login accounts.

This script clears:
- Employees
- Stores
- Office Day requests/schedules
- Brands that are currently unassigned to any employee

It retains:
- All records in the users table
- Brands currently assigned to at least one employee before the reset

IMPORTANT:
1. Stop Flask first using Ctrl+C.
2. Place this file in the same folder as app.py and office_day.db.
3. Run: python reset_data.py
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DATABASE_NAME = "office_day.db"
CONFIRMATION_TEXT = "RESET DATA"


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    result = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return result is not None


def count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])


def main() -> None:
    project_folder = Path(__file__).resolve().parent
    database_path = project_folder / DATABASE_NAME

    if not database_path.exists():
        print(f"\nERROR: Cannot find {DATABASE_NAME}")
        print(f"Expected location: {database_path}")
        print("Place reset_data.py in the same folder as app.py and office_day.db.")
        return

    print("\nOFFICE DAY SYSTEM — RESET OPERATIONAL DATA")
    print("=" * 48)
    print(f"Database: {database_path}")
    print("\nThis will permanently delete:")
    print("  • All employees")
    print("  • All stores")
    print("  • All Office Day requests/schedules")
    print("  • Brands not assigned to any employee before the reset")
    print("\nThis will retain:")
    print("  • All login accounts in the users table")
    print("  • Brands currently assigned to at least one employee")

    confirmation = input(
        f'\nType exactly "{CONFIRMATION_TEXT}" to continue: '
    ).strip()

    if confirmation != CONFIRMATION_TEXT:
        print("\nReset cancelled. No data was changed.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = project_folder / f"office_day_backup_before_reset_{timestamp}.db"

    try:
        shutil.copy2(database_path, backup_path)
    except OSError as error:
        print(f"\nERROR: Could not create backup: {error}")
        print("Reset cancelled. No data was changed.")
        return

    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(database_path, timeout=30)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        required_tables = {"users", "employees", "stores", "brands", "office_day_requests"}
        missing_tables = [
            table for table in required_tables if not table_exists(connection, table)
        ]
        if missing_tables:
            raise RuntimeError(
                "Missing expected table(s): " + ", ".join(sorted(missing_tables))
            )

        users_before = count_rows(connection, "users")
        employees_before = count_rows(connection, "employees")
        stores_before = count_rows(connection, "stores")
        requests_before = count_rows(connection, "office_day_requests")
        brands_before = count_rows(connection, "brands")

        assigned_brand_rows = connection.execute(
            """
            SELECT DISTINCT TRIM(brand)
            FROM employees
            WHERE brand IS NOT NULL
              AND TRIM(brand) <> ''
            """
        ).fetchall()
        assigned_brands = {
            str(row[0]).strip().casefold()
            for row in assigned_brand_rows
            if row[0] is not None
        }

        connection.execute("DELETE FROM office_day_requests")
        connection.execute("DELETE FROM employees")
        connection.execute("DELETE FROM stores")

        brand_rows = connection.execute(
            "SELECT id, brand_name FROM brands"
        ).fetchall()

        unassigned_brand_ids = [
            int(row[0])
            for row in brand_rows
            if str(row[1]).strip().casefold() not in assigned_brands
        ]

        if unassigned_brand_ids:
            placeholders = ",".join("?" for _ in unassigned_brand_ids)
            connection.execute(
                f"DELETE FROM brands WHERE id IN ({placeholders})",
                unassigned_brand_ids,
            )

        for table_name in ("employees", "stores", "office_day_requests"):
            connection.execute(
                "DELETE FROM sqlite_sequence WHERE name = ?",
                (table_name,),
            )

        if count_rows(connection, "brands") == 0:
            connection.execute(
                "DELETE FROM sqlite_sequence WHERE name = 'brands'"
            )

        connection.commit()

        users_after = count_rows(connection, "users")
        employees_after = count_rows(connection, "employees")
        stores_after = count_rows(connection, "stores")
        requests_after = count_rows(connection, "office_day_requests")
        brands_after = count_rows(connection, "brands")

        print("\nRESET COMPLETED SUCCESSFULLY")
        print("=" * 48)
        print(f"Users retained:               {users_after}")
        print(f"Employees deleted:            {employees_before - employees_after}")
        print(f"Stores deleted:               {stores_before - stores_after}")
        print(f"Office Day records deleted:   {requests_before - requests_after}")
        print(f"Unassigned brands deleted:    {brands_before - brands_after}")
        print(f"Assigned brands retained:     {brands_after}")
        print(f"\nBackup created:\n{backup_path}")

        if users_after != users_before:
            print(
                "\nWARNING: The number of users changed unexpectedly. "
                "Restore the backup before using the system."
            )

    except sqlite3.OperationalError as error:
        if connection is not None:
            connection.rollback()

        print(f"\nDATABASE ERROR: {error}")
        if "locked" in str(error).lower():
            print("\nThe database is locked.")
            print("Stop Flask using Ctrl+C and close DB Browser/SQLite extensions,")
            print("then run this script again.")
        else:
            print("\nNo reset was completed. Use the backup if necessary.")

    except Exception as error:
        if connection is not None:
            connection.rollback()
        print(f"\nERROR: {error}")
        print("No reset was completed. Your backup is available.")

    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
