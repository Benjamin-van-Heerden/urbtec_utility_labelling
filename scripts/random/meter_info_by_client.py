"""
Script to analyze meter type distribution across all client databases.

This queries the API database to get all client databases, then checks each one
for the distribution of meter types (cold_water, hot_water, electricity).
"""

import mysql.connector
from mysql.connector.cursor_cext import CMySQLCursorDict

from env_settings import ENV_SETTINGS

API_DATABASE = "mobixhep_urbtec_api"


def get_client_databases() -> list[tuple[str, str]]:
    """
    Query the API database to get all client databases.

    Returns:
        List of (client_name, dbname) tuples
    """
    conn = mysql.connector.connect(
        host=ENV_SETTINGS.source_db_host,
        port=ENV_SETTINGS.source_db_port,
        user=ENV_SETTINGS.source_db_user,
        password=ENV_SETTINGS.source_db_password,
        database=API_DATABASE,
        ssl_disabled=True,
    )
    cursor: CMySQLCursorDict = conn.cursor(cursor_class=CMySQLCursorDict)  # type: ignore

    cursor.execute("SELECT client_name, dbname FROM `databases`")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [(row["client_name"], row["dbname"]) for row in rows]  # type: ignore


def validate_client_database(dbname: str) -> bool:
    """
    Check if a client database has the required tables for meter readings.

    Returns:
        True if meter_readings and meter_history tables exist
    """
    try:
        conn = mysql.connector.connect(
            host=ENV_SETTINGS.source_db_host,
            port=ENV_SETTINGS.source_db_port,
            user=ENV_SETTINGS.source_db_user,
            password=ENV_SETTINGS.source_db_password,
            database=dbname,
            ssl_disabled=True,
        )
        cursor = conn.cursor()

        required_tables = ["meter_readings", "meter_history"]
        for table in required_tables:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return False

        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


def get_meter_distribution(dbname: str) -> dict[str, int]:
    """
    Get the distribution of meter types for a client database.

    Returns:
        Dict mapping utility_type -> count
    """
    conn = mysql.connector.connect(
        host=ENV_SETTINGS.source_db_host,
        port=ENV_SETTINGS.source_db_port,
        user=ENV_SETTINGS.source_db_user,
        password=ENV_SETTINGS.source_db_password,
        database=dbname,
        ssl_disabled=True,
    )
    cursor: CMySQLCursorDict = conn.cursor(cursor_class=CMySQLCursorDict)  # type: ignore

    cursor.execute("""
        SELECT mh.utility_type, COUNT(*) as count
        FROM meter_readings mr
        LEFT JOIN meter_history mh ON mr.meter_no = mh.meter_no
        WHERE mr.site IS NOT NULL
          AND mr.reading_date IS NOT NULL
          AND mr.file_name IS NOT NULL
          AND mr.file_name != ''
          AND mr.file_name NOT LIKE '%NOFILE%'
        GROUP BY mh.utility_type
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return {row["utility_type"]: row["count"] for row in rows}  # type: ignore


def main():
    print("Fetching client databases from API...")
    client_databases = get_client_databases()
    print(f"Found {len(client_databases)} client databases\n")

    results: list[dict] = []

    for client_name, dbname in client_databases:
        print(f"Checking {client_name} ({dbname})...", end=" ")

        if not validate_client_database(dbname):
            print("SKIPPED (missing required tables)")
            continue

        distribution = get_meter_distribution(dbname)
        cold_water = distribution.get("cold_water", 0)
        hot_water = distribution.get("hot_water", 0)
        electricity = distribution.get("electricity", 0)
        total = cold_water + hot_water + electricity

        results.append(
            {
                "client_name": client_name,
                "dbname": dbname,
                "cold_water": cold_water,
                "hot_water": hot_water,
                "electricity": electricity,
                "total": total,
            }
        )

        print(f"CW={cold_water}, HW={hot_water}, E={electricity}, Total={total}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Sort by total count descending
    results.sort(key=lambda x: x["total"], reverse=True)

    # Calculate totals
    total_cold_water = sum(r["cold_water"] for r in results)
    total_hot_water = sum(r["hot_water"] for r in results)
    total_electricity = sum(r["electricity"] for r in results)
    grand_total = total_cold_water + total_hot_water + total_electricity

    print(
        f"\n{'Client':<25} {'Cold Water':>12} {'Hot Water':>12} {'Electricity':>12} {'Total':>12}"
    )
    print("-" * 80)

    for r in results:
        print(
            f"{r['client_name']:<25} {r['cold_water']:>12,} {r['hot_water']:>12,} {r['electricity']:>12,} {r['total']:>12,}"
        )

    print("-" * 80)
    print(
        f"{'TOTAL':<25} {total_cold_water:>12,} {total_hot_water:>12,} {total_electricity:>12,} {grand_total:>12,}"
    )

    print("\nProportions:")
    if grand_total > 0:
        print(f"  Cold Water:  {total_cold_water / grand_total * 100:.1f}%")
        print(f"  Hot Water:   {total_hot_water / grand_total * 100:.1f}%")
        print(f"  Electricity: {total_electricity / grand_total * 100:.1f}%")

    # Show which clients have each meter type
    print("\nClients with Hot Water meters:")
    for r in results:
        if r["hot_water"] > 0:
            print(f"  - {r['client_name']}: {r['hot_water']:,}")

    print("\nClients with Electricity meters:")
    for r in results:
        if r["electricity"] > 0:
            print(f"  - {r['client_name']}: {r['electricity']:,}")


if __name__ == "__main__":
    main()
