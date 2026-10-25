from psycopg.rows import dict_row
from database import get_connection


def add_warehouse(name, location=None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                INSERT INTO warehouses (name, location)
                VALUES (%s, %s)
                RETURNING *;
            """, (name, location))
            return cur.fetchone()


def get_warehouse_by_id(warehouse_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM warehouses WHERE id = %s;",
                (warehouse_id,),
            )
            return cur.fetchone()


def get_all_warehouses():
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM warehouses ORDER BY id;")
            return cur.fetchall()


def update_warehouse(warehouse_id, name, location=None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                UPDATE warehouses
                SET name = %s, location = %s
                WHERE id = %s
                RETURNING *;
            """, (name, location, warehouse_id))
            return cur.fetchone()


def delete_warehouse(warehouse_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouses WHERE id = %s;",
                (warehouse_id,),
            )
            return cur.rowcount > 0


def transfer_stock(
    source_warehouse_id,
    destination_warehouse_id,
    product_id,
    quantity,
):
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    if source_warehouse_id == destination_warehouse_id:
        raise ValueError("Source and destination must differ.")

    # Lock inventory rows in a consistent order to reduce deadlocks.
    warehouse_ids = sorted([
        source_warehouse_id,
        destination_warehouse_id,
    ])

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT warehouse_id, quantity
                FROM inventory
                WHERE product_id = %s
                  AND warehouse_id = ANY(%s)
                ORDER BY warehouse_id
                FOR UPDATE;
            """, (product_id, warehouse_ids))

            records = {
                row["warehouse_id"]: row
                for row in cur.fetchall()
            }

            source = records.get(source_warehouse_id)
            if source is None:
                raise ValueError("Source inventory record not found.")

            if source["quantity"] < quantity:
                raise ValueError("Insufficient source stock.")

            # Deduct from source.
            cur.execute("""
                UPDATE inventory
                SET quantity = quantity - %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE warehouse_id = %s AND product_id = %s;
            """, (quantity, source_warehouse_id, product_id))

            # Add to destination or create its inventory row.
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
            """, (
                destination_warehouse_id,
                product_id,
                quantity,
            ))

            return cur.fetchone()