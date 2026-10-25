from decimal import Decimal
from database import get_connection
from psycopg.rows import dict_row
from uuid import UUID
from psycopg.errors import UniqueViolation
from psycopg import errors

def place_order(
    user_id,
    warehouse_id,
    product_id,
    quantity,
    idempotency_key,
):
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    try:
        key = UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("A valid idempotency UUID is required.") from exc

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Lock stock first so concurrent orders cannot oversell it.
            cur.execute("""
                SELECT quantity
                FROM inventory
                WHERE warehouse_id = %s AND product_id = %s
                FOR UPDATE;
            """, (warehouse_id, product_id))

            stock = cur.fetchone()
            if stock is None:
                raise ValueError("Inventory record not found.")

            # Check idempotency after acquiring the stock lock.
            cur.execute("""
                SELECT *
                FROM orders
                WHERE idempotency_key = %s;
            """, (key,))

            existing = cur.fetchone()

            if existing:
                expected = (
                    user_id,
                    warehouse_id,
                    product_id,
                    quantity,
                )
                actual = (
                    existing["user_id"],
                    existing["warehouse_id"],
                    existing["product_id"],
                    existing["quantity"],
                )

                if actual != expected:
                    raise ValueError(
                        "Idempotency key reused with different details."
                    )
                return existing

            if stock["quantity"] < quantity:
                raise ValueError("Insufficient stock.")

            cur.execute(
                "SELECT price FROM products WHERE id = %s;",
                (product_id,),
            )
            product = cur.fetchone()

            if product is None:
                raise ValueError("Product not found.")

            unit_price = product["price"]
            amount = unit_price * quantity

            cur.execute("""
                INSERT INTO orders (
                    user_id, warehouse_id, product_id, quantity,
                    unit_price, amount, status, idempotency_key
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'SUCCESS', %s)
                RETURNING *;
            """, (
                user_id,
                warehouse_id,
                product_id,
                quantity,
                unit_price,
                amount,
                key,
            ))

            order = cur.fetchone()

            cur.execute("""
                UPDATE inventory
                SET quantity = quantity - %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE warehouse_id = %s
                  AND product_id = %s
                RETURNING quantity;
            """, (quantity, warehouse_id, product_id))

            updated_stock = cur.fetchone()
            if updated_stock is None:
                raise ValueError("Stock deduction failed.")

            order["remaining_stock"] = updated_stock["quantity"]
            return order


def get_order_by_id(order_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT o.*, u.name AS user_name, p.name AS product_name,
                       w.name AS warehouse_name
                FROM orders o
                JOIN users u ON u.id = o.user_id
                JOIN products p ON p.id = o.product_id
                LEFT JOIN warehouses w ON w.id = o.warehouse_id
                WHERE o.id = %s;
            """, (order_id,))
            return cur.fetchone()


def get_user_orders(user_id, limit=50, offset=0):
    if not 1 <= limit <= 200 or offset < 0:
        raise ValueError("Invalid pagination parameters.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM orders
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s;
            """, (user_id, limit, offset))
            return cur.fetchall()


def get_orders_by_warehouse(warehouse_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM orders
                WHERE warehouse_id = %s
                ORDER BY created_at DESC, id DESC;
            """, (warehouse_id,))
            return cur.fetchall()


def get_orders_by_product(product_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM orders
                WHERE product_id = %s
                ORDER BY created_at DESC, id DESC;
            """, (product_id,))
            return cur.fetchall()


def get_orders_by_date_range(start_date, end_date):
    if start_date >= end_date:
        raise ValueError("End date must be later than start date.")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT *
                FROM orders
                WHERE created_at >= %s AND created_at < %s
                ORDER BY created_at DESC, id DESC;
            """, (start_date, end_date))
            return cur.fetchall()


def get_user_orders_by_status(user_id, status):
    query = """
        SELECT
            o.id AS order_id,
            o.user_id,
            u.name AS user_name,
            o.product_id,
            p.name AS product_name,
            o.quantity,
            o.unit_price,
            o.amount,
            o.status,
            o.created_at
        FROM orders AS o
        JOIN users AS u ON u.id = o.user_id
        JOIN products AS p ON p.id = o.product_id
        WHERE o.user_id = %s
          AND UPPER(o.status) = UPPER(%s)
        ORDER BY o.created_at DESC;
    """

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (user_id, status))
            orders = cursor.fetchall()

    return orders

def get_user_order_summary(user_id):
    query = """
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (
                WHERE UPPER(status) = 'SUCCESS'
            ) AS successful_orders,
            COUNT(*) FILTER (
                WHERE UPPER(status) = 'FAILED'
            ) AS failed_orders,
            COUNT(*) FILTER (
                WHERE UPPER(status) = 'CANCELLED'
            ) AS cancelled_orders,
            COALESCE(
                SUM(amount) FILTER (
                    WHERE UPPER(status) = 'SUCCESS'
                ),
                0
            ) AS total_spending
        FROM orders
        WHERE user_id = %s;
    """

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (user_id,))
            summary = cursor.fetchone()

    return summary

def cancel_order(order_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT id, warehouse_id, product_id, quantity, status
                FROM orders
                WHERE id = %s
                FOR UPDATE;
            """, (order_id,))

            order = cur.fetchone()

            if order is None:
                raise ValueError("Order not found.")

            if order["status"] != "SUCCESS":
                raise ValueError("Only successful orders can be cancelled.")

            if order["warehouse_id"] is None:
                raise ValueError("Order has no recorded warehouse.")

            cur.execute("""
                UPDATE inventory
                SET quantity = quantity + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE warehouse_id = %s AND product_id = %s
                RETURNING quantity;
            """, (
                order["quantity"],
                order["warehouse_id"],
                order["product_id"],
            ))

            stock = cur.fetchone()
            if stock is None:
                raise ValueError("Inventory record not found.")

            cur.execute("""
                UPDATE orders
                SET status = 'CANCELLED'
                WHERE id = %s AND status = 'SUCCESS'
                RETURNING id, status;
            """, (order_id,))

            result = cur.fetchone()
            if result is None:
                raise ValueError("Order status update failed.")

            result["remaining_stock"] = stock["quantity"]
            return result

def update_order_status(order_id, new_status):
    allowed_statuses = {"SUCCESS", "CANCELLED"}

    if new_status not in allowed_statuses:
        raise ValueError("Invalid order status.")

    if new_status != "CANCELLED":
        raise ValueError(
            "Orders cannot be changed back to SUCCESS. "
            "Use place_order() to create a new order."
        )

    raise ValueError(
        "Use cancel_order(order_id) to cancel an order safely "
        "and restore inventory."
    )

def update_order_status(order_id, new_status):
    if new_status == "CANCELLED":
        return cancel_order(order_id)

    raise ValueError(
        "Only cancellation is supported. "
        "Use place_order() to create a new order."
    )
