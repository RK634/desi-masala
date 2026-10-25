from datetime import datetime, timedelta
from order_status import OrderStatus


class Order:
    def __init__(self, order_id, user, product, quantity, inventory):
        if quantity <= 0:
            raise ValueError("Order quantity must be greater than zero.")

        self.id = order_id
        self.user = user
        self.product = product
        self.quantity = quantity
        self.amount = product.price * quantity
        self.status = OrderStatus.PENDING
        self.inventory = inventory
        self.created_at = datetime.now()

    def place_order(self):
        # Prevent placing the same Order object twice
        if self.status == OrderStatus.SUCCESS:
            print("This order has already been placed.")
            return False

        # Reject duplicate successful orders within 30 minutes
        current_time = datetime.now()
        duplicate_window = timedelta(minutes=30)

        for existing_order in self.user.orders:
            if (
                existing_order.id != self.id
                and existing_order.product.id == self.product.id
                and existing_order.quantity == self.quantity
                and existing_order.status == OrderStatus.SUCCESS
                and current_time - existing_order.created_at < duplicate_window
            ):
                print(
                    "Duplicate order rejected: the same product "
                    "and quantity were ordered within the last 30 minutes."
                )
                return False

        # Check stock availability
        if self.product.quantity < self.quantity:
            print("Order failed: Not enough stock.")
            self.status = OrderStatus.FAILED
            return False

        # Deduct stock
        stock_removed = self.inventory.remove_stock(
            self.product.id,
            self.quantity
        )

        if not stock_removed:
            self.status = OrderStatus.FAILED
            return False

        # Record successful order
        self.status = OrderStatus.SUCCESS
        self.user.add_order(self)

        print("Order placed successfully.")
        return True

    def order_info(self):
        print(f"""Order ID  : {self.id}
Customer  : {self.user.name}
Product   : {self.product.name}
Quantity  : {self.quantity}
Amount    : {self.amount}
Status    : {self.status.value}
Created At: {self.created_at}""")


    def cancel_order(self):
        # Only successful orders can be cancelled
        if self.status != OrderStatus.SUCCESS:
            print("Only successful orders can be cancelled.")
            return False
    
        # Restore the product stock
        product = self.inventory.find_product(self.product.id)
    
        if product is None:
            print("Order cancellation failed: Product not found.")
            return False
    
        product.increase_product(self.quantity)
    
        # Update order status
        self.status = OrderStatus.CANCELLED
    
        print(f"Order {self.id} cancelled successfully.")
        print(f"Restored stock: {self.quantity} units")
    
        return True

    def mark_failed(self, reason):
        if self.status == OrderStatus.SUCCESS:
            raise ValueError("A successful order cannot be marked as failed.")
    
        if self.status == OrderStatus.CANCELLED:
            raise ValueError("A cancelled order cannot be marked as failed.")
    
        self.status = OrderStatus.FAILED
        print(f"Order {self.id} failed: {reason}")

