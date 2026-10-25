class Inventory:

    def __init__(self):
        self.inventory = []

    # Find product by ID
    def find_product(self, product_id):

        for product in self.inventory:
            if product.id == product_id:
                return product

        return None

    # Add completely new product
    def add_product(self, product):
        existing_product = self.find_product(product.id)

        if existing_product:
            print(f"Product ID {product.id} already exists.")
            return False

        self.inventory.append(product)
        print(f"Product {product.name} added successfully.")
        return True


    # Update existing product
   
    def update_product(self, new_product):

        if new_product.price < 0:
            print("Price cannot be negative.")
            return False

        if new_product.quantity < 0:
            print("Quantity cannot be negative.")
            return False

        existing_product = self.find_product(new_product.id)

        if existing_product:
        # New price replaces old price
            existing_product.price = new_product.price

        # Add incoming stock to existing stock
            existing_product.quantity += new_product.quantity

            print(f"Product '{existing_product.name}' updated successfully.")
            return True

        print("Product not found.")
        return False
    

    # Add if new, otherwise update
   
    def add_or_update_product(self, product):
        existing_product = self.find_product(product.id)

        if existing_product:
            return self.update_product(product)

        return self.add_product(product)


    # Remove stock after successful order
    def remove_stock(self, product_id, quantity):

        if quantity <= 0:
            print("Quantity must be greater than zero.")
            return False

        product = self.find_product(product_id)
        if product is None:
            print("Product not found.")
            return False

        if product.quantity < quantity:

            print(
                f"Not enough stock for '{product.name}'.")
            return False

        success = product.decrease_product(quantity)

        if not success:
            return False

        print(
            f"{quantity} unit(s) of {product.name}' removed from inventory.")
        return True

    # Remove complete product
    def remove_product(self, product_id):

        product = self.find_product(product_id)
        if product:
            self.inventory.remove(product)
            print(
                f"Product '{product.name}' removed successfully.")
            return True

        print("Product not found.")
        return False

    # Show all inventory
    def show_inventory(self):

        if not self.inventory:

            print("Inventory is empty.")
            return

        for product in self.inventory:
            product.product_info()

    def get_low_stock_products(self, threshold=5):
        return [ product for product in self.inventory if product.quantity <= threshold ]

    def get_total_inventory_value(self):
        return sum( product.price * product.quantity for product in self.inventory )


    def search_products(self, search_term):
        search_term = search_term.strip().lower()

        if not search_term:
            return []

        return [ product for product in self.inventory 
                if search_term in product.name.lower() 
                or search_term in product.brand.lower() ]