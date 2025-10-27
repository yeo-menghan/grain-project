# allocator/allocation/validator.py
"""Allocation validation"""
from typing import List, Dict, Any
from datetime import datetime
from allocator.models import Driver, Order


class AllocationValidator:
    """Validates allocations against constraints"""
    
    def __init__(self, drivers: List[Driver], orders: List[Order]):
        self.driver_map = {d.driver_id: d for d in drivers}
        self.order_map = {o.order_id: o for o in orders}
        self.wedding_order_ids = {o.order_id for o in orders if o.is_wedding_order}
    
    def validate(self, allocation: Dict[str, Any]) -> List[str]:
        """Validate allocation against hard constraints"""
        issues = []
        allocations = allocation.get('allocations', {})
        allocated_wedding_orders = set()
        
        for driver_id, order_ids in allocations.items():
            if driver_id not in self.driver_map:
                issues.append(f"Unknown driver: {driver_id}")
                continue
            
            driver = self.driver_map[driver_id]
            
            # Check capacity
            if len(order_ids) > driver.max_orders_per_day:
                issues.append(
                    f"❌ CAPACITY: {driver_id} ({driver.name}) assigned {len(order_ids)} "
                    f"orders, max is {driver.max_orders_per_day}"
                )
            
            # Validate each order
            driver_orders = []
            region_mismatches = 0
            driver_has_wedding_orders = False
            driver_has_regular_orders = False
            
            for order_id in order_ids:
                if order_id not in self.order_map:
                    issues.append(f"Unknown order: {order_id}")
                    continue
                
                order = self.order_map[order_id]
                driver_orders.append(order)
                
                # Check wedding capability
                if order.is_wedding_order:
                    allocated_wedding_orders.add(order_id)
                    driver_has_wedding_orders = True
                    if not driver.is_wedding_capable:
                        issues.append(
                            f"❌ CAPABILITY: {driver_id} lacks wedding capability "
                            f"for order {order_id} (tags: {order.tags})"
                        )
                else:
                    driver_has_regular_orders = True
                
                # Check region match
                if order.region != driver.preferred_region:
                    region_mismatches += 1
            
            # Check for resource waste
            unallocated_wedding_orders = self.wedding_order_ids - allocated_wedding_orders
            if (driver.is_wedding_capable and driver_has_regular_orders and 
                len(unallocated_wedding_orders) > 0):
                issues.append(
                    f"❌ RESOURCE WASTE: {driver_id} is wedding-capable but assigned "
                    f"regular orders while {len(unallocated_wedding_orders)} wedding "
                    f"orders remain unallocated"
                )
            
            # Report region mismatches
            if region_mismatches > 0 and len(order_ids) > 0:
                match_rate = (len(order_ids) - region_mismatches) / len(order_ids)
                if match_rate < 0.5:
                    issues.append(
                        f"⚠️ REGION: {driver_id} has poor region matching: "
                        f"{region_mismatches}/{len(order_ids)} orders not in "
                        f"preferred region '{driver.preferred_region}'"
                    )
            
            # Check time conflicts
            for i, order1 in enumerate(driver_orders):
                for order2 in driver_orders[i+1:]:
                    if order1.conflicts_with(order2):
                        issues.append(
                            f"❌ TIME CONFLICT: {driver_id} has overlapping orders "
                            f"{order1.order_id} ({order1.pickup_time.strftime('%H:%M')}-"
                            f"{order1.teardown_time.strftime('%H:%M')}) and "
                            f"{order2.order_id} ({order2.pickup_time.strftime('%H:%M')}-"
                            f"{order2.teardown_time.strftime('%H:%M')})"
                        )
        
        return issues