import psycopg
from psycopg.rows import dict_row
from database import get_connection

from psycopg.rows import dict_row
from database import get_connection


def add_product(name, price, brand=None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                INSERT INTO products (name, price, brand)
                VALUES (%s, %s, %s)
                RETURNING *;
            """, (name, price, brand))
            return cur.fetchone()


def get_product_by_id(product_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM products WHERE id = %s;",
                (product_id,),
            )
            return cur.fetchone()


def get_all_products(limit=50, offset=0):
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("Invalid pagination parameters.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM products
                ORDER BY id
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            return cur.fetchall()


def update_product(product_id, name, price, brand=None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                UPDATE products
                SET name = %s, price = %s, brand = %s
                WHERE id = %s
                RETURNING *;
            """, (name, price, brand, product_id))
            return cur.fetchone()


def delete_product(product_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM products WHERE id = %s;",
                (product_id,),
            )
            return cur.rowcount > 0


def search_products(search_term):
    pattern = f"%{search_term}%"

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM products
                WHERE name ILIKE %s OR brand ILIKE %s
                ORDER BY name;
            """, (pattern, pattern))
            return cur.fetchall()


def get_products_by_price_range(min_price, max_price):
    if min_price < 0 or max_price < min_price:
        raise ValueError("Invalid price range.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM products
                WHERE price BETWEEN %s AND %s
                ORDER BY price, id;
            """, (min_price, max_price))
            return cur.fetchall()

    