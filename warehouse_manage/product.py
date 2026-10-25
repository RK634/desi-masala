class Product:

    def __init__(self, product_id, name, price, quantity, brand):
        if price < 0:
            raise ValueError("Price cannot be negative.")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")
        
        self.id = product_id
        self.name = name
        self.price = price
        self.quantity = quantity
        self.brand = brand

    def increase_product(self, value):
        self.quantity += value

    def decrease_product(self, value):
        if value > 0 and value <= self.quantity:
            self.quantity -= value
            return True

        print("Not enough quantity available.")
        return False

    def product_info(self):
        print(f"""ID: {self.id}
Name: {self.name}
Brand: {self.brand}
Price: {self.price}
Available Quantity: {self.quantity}""")