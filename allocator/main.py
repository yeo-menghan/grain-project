# allocator/main.py
"""Main entry point for the allocator"""
from typing import Dict, Any, List
from allocator.config import DRIVERS_FILE, ORDERS_FILE, OUTPUT_FILE, MAX_RETRIES
from allocator.io import DataLoader, ResultSaver
from allocator.allocation import AllocationEngine
from allocator.analysis import MetricsCalculator
from allocator.utils import categorize_validation_issues


class OutputFormatter:
    """Formats and displays allocation results"""
    
    @staticmethod
    def print_results(allocation: Dict[str, Any], validation_issues: List[str],
                     drivers_count: int, orders_count: int, metrics: Dict[str, Any]):
        """Pretty print allocation results"""
        print("\n" + "="*80)
        print("📋 ALLOCATION RESULTS")
        print("="*80)
        
        OutputFormatter._print_metrics(metrics, orders_count, drivers_count)
        OutputFormatter._print_validation_breakdown(validation_issues)
        OutputFormatter._print_allocations(allocation, drivers_count, orders_count)
        OutputFormatter._print_warnings(allocation)
        OutputFormatter._print_validation_issues(validation_issues)
        
        print("\n" + "="*80)
    
    @staticmethod
    def _print_metrics(metrics: Dict, orders_count: int, drivers_count: int):
        """Print metrics section"""
        print(f"\n📊 METRICS:")
        print(f"   Total Allocated: {metrics.get('total_allocated', 0)}/{orders_count} orders")
        print(f"   Unallocated: {metrics.get('total_unallocated', 0)} orders")
        print(f"   Wedding Orders Allocated: {metrics.get('wedding_orders_allocated', 0)}")
        print(f"   Corporate Orders Allocated: {metrics.get('corporate_orders_allocated', 0)}")
        print(f"   Regular Orders Allocated: {metrics.get('regular_orders_allocated', 0)}")
        print(f"   Drivers Used: {metrics.get('drivers_used', 0)}/{drivers_count}")
        print(f"   Avg Orders/Driver: {metrics.get('average_orders_per_driver', 0):.1f}")
        print(f"   Region Match Rate: {metrics.get('region_match_rate', 0):.1%}")
        
        wedding_on_wedding = metrics.get('wedding_drivers_on_wedding_orders', 0)
        wedding_on_regular = metrics.get('wedding_drivers_on_regular_orders', 0)
        if wedding_on_wedding or wedding_on_regular:
            print(f"   Wedding Drivers on Wedding Orders: {wedding_on_wedding}")
            print(f"   Wedding Drivers on Regular Orders: {wedding_on_regular}")
    
    @staticmethod
    def _print_validation_breakdown(issues: List[str]):
        """Print validation issue breakdown"""
        issue_breakdown = categorize_validation_issues(issues)
        if any(issue_breakdown.values()):
            print(f"\n⚠️  VALIDATION ISSUE BREAKDOWN:")
            if issue_breakdown['time_conflicts'] > 0:
                print(f"   ⛔ Time Conflicts: {issue_breakdown['time_conflicts']}")
            if issue_breakdown['capability_mismatches'] > 0:
                print(f"   ⛔ Capability Mismatches: {issue_breakdown['capability_mismatches']}")
            if issue_breakdown['capacity_violations'] > 0:
                print(f"   ⚠️  Capacity Violations: {issue_breakdown['capacity_violations']}")
            if issue_breakdown['resource_waste'] > 0:
                print(f"   ⚠️  Resource Waste: {issue_breakdown['resource_waste']}")
            if issue_breakdown['region_mismatches'] > 0:
                print(f"   ℹ️  Region Mismatches: {issue_breakdown['region_mismatches']}")
    
    @staticmethod
    def _print_allocations(allocation: Dict[str, Any], drivers_count: int, 
                          orders_count: int):
        """Print driver allocations"""
        from allocator.io import DataLoader
        from allocator.config import DRIVERS_FILE, ORDERS_FILE
        
        # Reload data for display
        drivers, orders = DataLoader.load_drivers_and_orders(DRIVERS_FILE, ORDERS_FILE)
        driver_map = {d.driver_id: d for d in drivers}
        order_map = {o.order_id: o for o in orders}
        
        allocations = allocation.get('allocations', {})
        reasoning = allocation.get('reasoning', {})
        
        active_drivers = {k: v for k, v in allocations.items() if len(v) > 0}
        print(f"\n👥 DRIVER ASSIGNMENTS ({len(active_drivers)} drivers with orders):")
        print("-"*80)
        
        for driver_id in sorted(active_drivers.keys()):
            driver = driver_map.get(driver_id)
            if not driver:
                continue
            
            order_ids = allocations[driver_id]
            
            capability_type = "Wedding-capable" if driver.is_wedding_capable else "Standard"
            
            print(f"\n{driver_id} - {driver.name} ({capability_type})")
            print(f"   Preferred Region: {driver.preferred_region}")
            print(f"   Capacity: {len(order_ids)}/{driver.max_orders_per_day} orders")
            print(f"   Capabilities: {', '.join(driver.capabilities) or 'None'}")
            print(f"   Orders:")
            
            sorted_order_ids = sorted(
                order_ids, 
                key=lambda oid: order_map.get(oid).pickup_time if order_map.get(oid) else ''
            )
            
            for order_id in sorted_order_ids:
                order = order_map.get(order_id)
                if not order:
                    continue
                
                order_type = "🎉 WEDDING" if order.is_wedding_order else "📦"
                region_match = "✓" if order.region == driver.preferred_region else "⚠️"
                tags_str = ', '.join(order.tags) or 'none'
                
                print(f"      {order_type} {order_id}: {order.region} {region_match} | "
                      f"{order.pax_count} pax | "
                      f"{order.pickup_time.isoformat()} → {order.teardown_time.isoformat()} | "
                      f"tags: {tags_str}")
                
                order_reasoning = reasoning.get(order_id, "No reasoning provided")
                print(f"         └─ Reasoning: {order_reasoning}")
    
    @staticmethod
    def _print_warnings(allocation: Dict[str, Any]):
        """Print warnings"""
        warnings = allocation.get('warnings', [])
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            print("-"*80)
            for warning in warnings:
                print(f"   • {warning}")
    
    @staticmethod
    def _print_validation_issues(issues: List[str]):
        """Print validation issues"""
        if issues:
            print(f"\n❌ VALIDATION ISSUES ({len(issues)}):")
            print("-"*80)
            for issue in issues:
                print(f"   • {issue}")
        else:
            print(f"\n✅ No validation issues found!")


def main():
    """Main entry point"""
    # Load data
    print("📂 Loading data...")
    drivers, orders = DataLoader.load_drivers_and_orders(DRIVERS_FILE, ORDERS_FILE)
    
    # Initialize allocation engine
    engine = AllocationEngine(drivers, orders)
    
    # Run allocation with retry logic
    best_allocation, best_attempt_filepath = engine.allocate(max_retries=MAX_RETRIES)
    
    # Final validation
    from allocator.allocation import AllocationValidator
    validator = AllocationValidator(drivers, orders)
    validation_issues = validator.validate(best_allocation)
    
    # Calculate metrics
    metrics = MetricsCalculator.calculate(best_allocation, drivers, orders)
    
    # Display results
    OutputFormatter.print_results(
        best_allocation, validation_issues, 
        len(drivers), len(orders), metrics
    )
    
    # Build and save complete output
    complete_output = engine.build_complete_output(best_allocation)
    saver = ResultSaver()
    saver.save_final_results(complete_output, OUTPUT_FILE)
    
    print(f"\n📁 All attempts saved in: {saver.attempts_dir}/")
    print(f"🏆 Best attempt was saved as final result")


if __name__ == "__main__":
    main()