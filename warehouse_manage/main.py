from uuid import uuid4

from product_repository import (
    add_product,
    get_all_products,
)
from user_repository import add_user
from warehouse_repository import add_warehouse
from inventory_repository import add_stock, get_stock
from order_repository import place_order, cancel_order


def main():
    print("StockFlow")

    # Example workflow. Use fresh records or existing valid IDs.
    user = add_user("Demo User", f"demo-{uuid4().hex[:8]}@example.com")
    product = add_product("Keyboard", 49.99, "Example Brand")
    warehouse = add_warehouse("Main Warehouse", "Berlin")

    add_stock(warehouse["id"], product["id"], 10)

    order = place_order(
        user_id=user["id"],
        warehouse_id=warehouse["id"],
        product_id=product["id"],
        quantity=2,
        idempotency_key=uuid4(),
    )

    print("Order created:", order)
    print("Products:", get_all_products())

    # Uncomment to demonstrate cancellation:
    # print(cancel_order(order["id"]))


if __name__ == "__main__":
    main()