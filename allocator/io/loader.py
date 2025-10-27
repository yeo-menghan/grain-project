# allocator/io/loader.py
"""Data loading functionality"""
import json
from typing import List, Tuple
from allocator.models import Driver, Order


class DataLoader:
    """Handles loading of driver and order data"""
    
    @staticmethod
    def load_json(filepath: str) -> List[dict]:
        """Load JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def load_drivers_and_orders(drivers_file: str, orders_file: str) -> Tuple[List[Driver], List[Order]]:
        """Load drivers and orders from JSON files"""
        drivers_data = DataLoader.load_json(drivers_file)
        orders_data = DataLoader.load_json(orders_file)
        
        drivers = [Driver(d) for d in drivers_data]
        orders = [Order(o) for o in orders_data]
        
        print(f"Loaded {len(drivers)} drivers and {len(orders)} orders")
        
        return drivers, orders