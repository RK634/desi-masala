from database import get_connection

try:
    with get_connection() as conn:
        row = conn.execute("SELECT current_database() AS database_name, current_user AS database_user").fetchone()
        print("Connected successfully!")
        print("Database:", row["database_name"])
        print("User:", row["database_user"])
except Exception as exc:
    print("Connection failed:", exc)
