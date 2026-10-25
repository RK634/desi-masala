class Warehouse:

    def __init__(self, warehouse_id, name, location, inventory):
        self.id = warehouse_id
        self.name = name
        self.location = location
        self.inventory = inventory

    def show_warehouse(self):

        print("""WAREHOUSE INFO""")
        print(f"ID       : {self.id}")
        print(f"Name     : {self.name}")
        print(f"Location : {self.location}")

        print("\nINVENTORY")

        self.inventory.show_inventory()

    def get_product(self, product_id):
        return self.inventory.find_product(product_id)


    def get_inventory_summary(self):
        products = self.inventory.inventory
    
        return {
            "product_count": len(products),
            "total_units": sum(
                product.quantity for product in products
            ),
            "inventory_value": self.inventory.get_total_inventory_value()
        }