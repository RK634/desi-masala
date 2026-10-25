from order_status import OrderStatus


class User:

    def __init__(self, user_id, name, role):
        self.id = user_id
        self.name = name
        self.role = role
        self.orders = []

    # Add completed order to user's history
    def add_order(self, order):
        self.orders.append(order)

    # Show user's order history
    def show_orders(self):
        print(f"""ORDER HISTORY
Customer: {self.name}
User ID : {self.id}""")

        if not self.orders:
            print("No orders found.")
            return

        for order in self.orders:
            order.order_info()

    def get_order_by_id(self, order_id):
        for order in self.orders:
            if order.id == order_id:
                return order

        return None

    def get_order_history(self):
        return sorted( self.orders, key=lambda order: order.created_at, reverse=True )

    def get_total_spending(self):
        return sum( order.amount for order in self.orders
                    if order.status == OrderStatus.SUCCESS )

