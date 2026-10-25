from psycopg.rows import dict_row
from database import get_connection


def add_user(name, email):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                INSERT INTO users (name, email)
                VALUES (%s, %s)
                RETURNING *;
            """, (name, email))
            return cur.fetchone()


def get_user_by_id(user_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM users WHERE id = %s;",
                (user_id,),
            )
            return cur.fetchone()


def get_all_users(limit=50, offset=0):
    if not 1 <= limit <= 200 or offset < 0:
        raise ValueError("Invalid pagination parameters.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM users
                ORDER BY id
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            return cur.fetchall()


def update_user(user_id, name, email):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                UPDATE users
                SET name = %s, email = %s
                WHERE id = %s
                RETURNING *;
            """, (name, email, user_id))
            return cur.fetchone()


def delete_user(user_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM users WHERE id = %s;",
                (user_id,),
            )
            return cur.rowcount > 0