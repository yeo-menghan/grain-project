# allocator/analysis/analyzer.py
"""Data analysis functionality"""
from typing import Dict, Any, List
from datetime import datetime
from allocator.models import Driver, Order


class OrderAnalyzer:
    """Analyzes order data"""
    
    @staticmethod
    def analyze(orders: List[Order]) -> Dict[str, Any]:
        """Analyze orders and identify constraints"""
        analysis = {
            'total_orders': len(orders),
            'wedding_orders': [],
            'corporate_orders': [],
            'regular_orders': [],
            'orders_by_region': {},
            'orders_by_time_slot': {}
        }
        
        for order in orders:
            # Categorize by type
            if order.is_wedding_order:
                analysis['wedding_orders'].append(order.order_id)
            elif order.is_corporate_order:
                analysis['corporate_orders'].append(order.order_id)
            else:
                analysis['regular_orders'].append(order.order_id)
            
            # Group by region
            region = order.region
            if region not in analysis['orders_by_region']:
                analysis['orders_by_region'][region] = []
            analysis['orders_by_region'][region].append(order.order_id)
            
            # Group by pickup time slot (hour)
            time_slot = f"{order.pickup_time.date()}_{order.pickup_time.hour:02d}:00"
            if time_slot not in analysis['orders_by_time_slot']:
                analysis['orders_by_time_slot'][time_slot] = []
            analysis['orders_by_time_slot'][time_slot].append(order.order_id)
        
        return analysis


class DriverAnalyzer:
    """Analyzes driver data"""
    
    @staticmethod
    def analyze(drivers: List[Driver]) -> Dict[str, Any]:
        """Analyze driver capabilities"""
        analysis = {
            'total_drivers': len(drivers),
            'wedding_capable_drivers': [],
            'corporate_capable_drivers': [],
            'standard_drivers': [],
            'drivers_by_region': {},
            'total_capacity': 0
        }
        
        for driver in drivers:
            # Categorize by capability
            if driver.is_wedding_capable:
                analysis['wedding_capable_drivers'].append(driver.driver_id)
            elif driver.is_corporate_capable:
                analysis['corporate_capable_drivers'].append(driver.driver_id)
            else:
                analysis['standard_drivers'].append(driver.driver_id)
            
            # Group by region
            region = driver.preferred_region
            if region not in analysis['drivers_by_region']:
                analysis['drivers_by_region'][region] = []
            analysis['drivers_by_region'][region].append(driver.driver_id)
            
            # Calculate total capacity
            analysis['total_capacity'] += driver.max_orders_per_day
        
        return analysis


class MetricsCalculator:
    """Calculates metrics from allocations"""
    
    @staticmethod
    def calculate(allocation: Dict[str, Any], drivers: List[Driver], 
                 orders: List[Order]) -> Dict[str, Any]:
        """Calculate actual metrics from the allocation"""
        allocations = allocation.get('allocations', {})
        
        # Create lookup maps
        driver_map = {d.driver_id: d for d in drivers}
        order_map = {o.order_id: o for o in orders}
        
        # Track statistics
        total_allocated = 0
        wedding_orders_allocated = 0
        corporate_orders_allocated = 0
        regular_orders_allocated = 0
        drivers_used = 0
        region_matches = 0
        total_order_assignments = 0
        wedding_drivers_on_wedding = 0
        wedding_drivers_on_regular = 0
        
        for driver_id, order_ids in allocations.items():
            if not order_ids:
                continue
            
            drivers_used += 1
            driver = driver_map.get(driver_id)
            if not driver:
                continue
            
            for order_id in order_ids:
                total_allocated += 1
                order = order_map.get(order_id)
                if not order:
                    continue
                
                # Count order types
                if order.is_wedding_order:
                    wedding_orders_allocated += 1
                    if driver.is_wedding_capable:
                        wedding_drivers_on_wedding += 1
                elif order.is_corporate_order:
                    corporate_orders_allocated += 1
                else:
                    regular_orders_allocated += 1
                    if driver.is_wedding_capable:
                        wedding_drivers_on_regular += 1
                
                # Count region matches
                if order.region == driver.preferred_region:
                    region_matches += 1
                total_order_assignments += 1
        
        return {
            'total_allocated': total_allocated,
            'total_unallocated': len(orders) - total_allocated,
            'wedding_orders_allocated': wedding_orders_allocated,
            'corporate_orders_allocated': corporate_orders_allocated,
            'regular_orders_allocated': regular_orders_allocated,
            'drivers_used': drivers_used,
            'average_orders_per_driver': total_allocated / drivers_used if drivers_used > 0 else 0,
            'region_match_rate': region_matches / total_order_assignments if total_order_assignments > 0 else 0,
            'wedding_drivers_on_wedding_orders': wedding_drivers_on_wedding,
            'wedding_drivers_on_regular_orders': wedding_drivers_on_regular
        }