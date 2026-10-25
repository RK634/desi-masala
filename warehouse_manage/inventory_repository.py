from psycopg.rows import dict_row
from database import get_connection


def get_stock(warehouse_id, product_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM inventory
                WHERE warehouse_id = %s AND product_id = %s;
            """, (warehouse_id, product_id))
            return cur.fetchone()


def add_stock(warehouse_id, product_id, quantity):
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                INSERT INTO inventory (
                    warehouse_id, product_id, quantity
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (warehouse_id, product_id)
                DO UPDATE SET
                    quantity = inventory.quantity + EXCLUDED.quantity,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *;
            """, (warehouse_id, product_id, quantity))
            return cur.fetchone()


def remove_stock(warehouse_id, product_id, quantity):
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                UPDATE inventory
                SET quantity = quantity - %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE warehouse_id = %s
                  AND product_id = %s
                  AND quantity >= %s
                RETURNING *;
            """, (
                quantity,
                warehouse_id,
                product_id,
                quantity,
            ))

            result = cur.fetchone()
            if result is None:
                raise ValueError(
                    "Inventory record missing or insufficient stock."
                )
            return result


def get_warehouse_inventory(warehouse_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT p.id AS product_id, p.name, p.brand, p.price,
                       i.quantity, i.updated_at
                FROM inventory i
                JOIN products p ON p.id = i.product_id
                WHERE i.warehouse_id = %s
                ORDER BY p.name;
            """, (warehouse_id,))
            return cur.fetchall()


def get_low_stock_products(threshold, warehouse_id=None):
    if threshold < 0:
        raise ValueError("Threshold cannot be negative.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if warehouse_id is None:
                cur.execute("""
                    SELECT w.id AS warehouse_id, w.name AS warehouse_name,
                           p.id AS product_id, p.name AS product_name,
                           i.quantity
                    FROM inventory i
                    JOIN warehouses w ON w.id = i.warehouse_id
                    JOIN products p ON p.id = i.product_id
                    WHERE i.quantity <= %s
                    ORDER BY i.quantity, w.id, p.id;
                """, (threshold,))
            else:
                cur.execute("""
                    SELECT w.id AS warehouse_id, w.name AS warehouse_name,
                           p.id AS product_id, p.name AS product_name,
                           i.quantity
                    FROM inventory i
                    JOIN warehouses w ON w.id = i.warehouse_id
                    JOIN products p ON p.id = i.product_id
                    WHERE i.quantity <= %s AND i.warehouse_id = %s
                    ORDER BY i.quantity, p.id;
                """, (threshold, warehouse_id))

            return cur.fetchall()


def get_inventory_summary(warehouse_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS distinct_products,
                    COALESCE(SUM(i.quantity), 0) AS total_units,
                    COALESCE(SUM(i.quantity * p.price), 0)
                        AS inventory_value
                FROM inventory i
                JOIN products p ON p.id = i.product_id
                WHERE i.warehouse_id = %s;
            """, (warehouse_id,))
            return cur.fetchone()