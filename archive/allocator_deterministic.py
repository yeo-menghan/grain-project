# allocator_deterministic.py
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dotenv import load_dotenv
from openai import OpenAI
from collections import defaultdict

load_dotenv()

class DeterministicAllocator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.drivers = []
        self.orders = []
        self.allocations = defaultdict(list)  # driver_id -> [order_ids]
        self.driver_schedules = defaultdict(list)  # driver_id -> [(pickup, teardown, order_id)]
        
    def load_data(self, drivers_file: str, orders_file: str):
        """Load driver and order data from JSON files"""
        with open(drivers_file, 'r') as f:
            self.drivers = json.load(f)
        with open(orders_file, 'r') as f:
            self.orders = json.load(f)
        
        print(f"Loaded {len(self.drivers)} drivers and {len(self.orders)} orders")
    
    def check_time_conflict(self, driver_id: str, pickup_time: datetime, teardown_time: datetime) -> bool:
        """Check if a time slot conflicts with driver's existing schedule"""
        for existing_pickup, existing_teardown, _ in self.driver_schedules[driver_id]:
            # Two time windows conflict if they overlap at all
            # They DON'T conflict only if one ends before the other starts
            if not (teardown_time <= existing_pickup or existing_teardown <= pickup_time):
                return True  # Conflict found
        return False  # No conflict
    
    def assign_order_to_driver(self, driver_id: str, order: Dict) -> bool:
        """Try to assign an order to a driver, return True if successful"""
        pickup = datetime.fromisoformat(order['pickup_time'])
        teardown = datetime.fromisoformat(order['teardown_time'])
        
        # Find driver
        driver = next((d for d in self.drivers if d['driver_id'] == driver_id), None)
        if not driver:
            return False
        
        # Check capacity
        if len(self.allocations[driver_id]) >= driver['max_orders_per_day']:
            return False
        
        # Check time conflict - CRITICAL CHECK
        if self.check_time_conflict(driver_id, pickup, teardown):
            return False
        
        # Check capabilities for VIP/wedding orders
        tags = order.get('tags', [])
        if 'vip' in tags or 'wedding' in tags:
            capabilities = driver.get('capabilities', [])
            has_vip_capability = any(cap in ['vip', 'wedding', 'large_events'] for cap in capabilities)
            if not has_vip_capability:
                return False
        
        # All checks passed - assign the order
        self.allocations[driver_id].append(order['order_id'])
        self.driver_schedules[driver_id].append((pickup, teardown, order['order_id']))
        return True
    
    def find_best_driver_for_order(self, order: Dict) -> Optional[str]:
        """Find the best available driver for an order"""
        tags = order.get('tags', [])
        region = order['region']
        requires_vip = 'vip' in tags or 'wedding' in tags
        
        # Create candidate list
        candidates = []
        
        for driver in self.drivers:
            driver_id = driver['driver_id']
            capabilities = driver.get('capabilities', [])
            preferred_region = driver.get('preferred_region')
            
            # Skip if VIP required but driver not capable
            if requires_vip:
                has_vip = any(cap in ['vip', 'wedding', 'large_events'] for cap in capabilities)
                if not has_vip:
                    continue
            
            # Skip if at capacity
            if len(self.allocations[driver_id]) >= driver['max_orders_per_day']:
                continue
            
            # Skip if time conflict
            pickup = datetime.fromisoformat(order['pickup_time'])
            teardown = datetime.fromisoformat(order['teardown_time'])
            if self.check_time_conflict(driver_id, pickup, teardown):
                continue
            
            # Calculate priority score
            region_match = 100 if preferred_region == region else 0
            capacity_remaining = driver['max_orders_per_day'] - len(self.allocations[driver_id])
            
            # Prioritize: region match > capacity remaining
            priority = (region_match, capacity_remaining)
            
            candidates.append((priority, driver_id))
        
        if not candidates:
            return None
        
        # Sort by priority (highest first) and return best driver
        candidates.sort(reverse=True)
        return candidates[0][1]
    
    def allocate_deterministically(self) -> Dict[str, Any]:
        """Deterministic allocation with guaranteed constraint satisfaction"""
        print("\n🔧 Starting deterministic allocation...")
        
        # Create order map
        order_map = {o['order_id']: o for o in self.orders}
        
        # Categorize orders
        vip_wedding_orders = []
        corporate_orders = []
        regular_orders = []
        
        for order in self.orders:
            tags = order.get('tags', [])
            if 'vip' in tags or 'wedding' in tags:
                vip_wedding_orders.append(order)
            elif 'corporate' in tags:
                corporate_orders.append(order)
            else:
                regular_orders.append(order)
        
        # Sort each category by pickup time for better allocation
        vip_wedding_orders.sort(key=lambda o: o['pickup_time'])
        corporate_orders.sort(key=lambda o: o['pickup_time'])
        regular_orders.sort(key=lambda o: o['pickup_time'])
        
        unallocated = []
        allocation_stats = {
            'vip_wedding_allocated': 0,
            'corporate_allocated': 0,
            'regular_allocated': 0,
            'region_matches': 0,
            'region_mismatches': 0
        }
        
        print(f"\n📦 Allocating {len(vip_wedding_orders)} VIP/wedding orders...")
        for order in vip_wedding_orders:
            driver_id = self.find_best_driver_for_order(order)
            if driver_id:
                self.assign_order_to_driver(driver_id, order)
                allocation_stats['vip_wedding_allocated'] += 1
                
                # Track region matching
                driver = next(d for d in self.drivers if d['driver_id'] == driver_id)
                if driver['preferred_region'] == order['region']:
                    allocation_stats['region_matches'] += 1
                else:
                    allocation_stats['region_mismatches'] += 1
                    print(f"   ⚠️  {order['order_id']} assigned to {driver_id} (region mismatch: {order['region']} → {driver['preferred_region']})")
            else:
                unallocated.append((order['order_id'], 'VIP/wedding - no available capable driver without time conflicts'))
                print(f"   ❌ {order['order_id']} - no available driver")
        
        print(f"\n📦 Allocating {len(corporate_orders)} corporate orders...")
        for order in corporate_orders:
            driver_id = self.find_best_driver_for_order(order)
            if driver_id:
                self.assign_order_to_driver(driver_id, order)
                allocation_stats['corporate_allocated'] += 1
                
                driver = next(d for d in self.drivers if d['driver_id'] == driver_id)
                if driver['preferred_region'] == order['region']:
                    allocation_stats['region_matches'] += 1
                else:
                    allocation_stats['region_mismatches'] += 1
            else:
                unallocated.append((order['order_id'], 'Corporate - no available driver without time conflicts'))
        
        print(f"\n📦 Allocating {len(regular_orders)} regular orders...")
        for order in regular_orders:
            driver_id = self.find_best_driver_for_order(order)
            if driver_id:
                self.assign_order_to_driver(driver_id, order)
                allocation_stats['regular_allocated'] += 1
                
                driver = next(d for d in self.drivers if d['driver_id'] == driver_id)
                if driver['preferred_region'] == order['region']:
                    allocation_stats['region_matches'] += 1
                else:
                    allocation_stats['region_mismatches'] += 1
            else:
                unallocated.append((order['order_id'], 'Regular - no available driver without time conflicts'))
        
        # Build result
        total_allocated = sum([
            allocation_stats['vip_wedding_allocated'],
            allocation_stats['corporate_allocated'],
            allocation_stats['regular_allocated']
        ])
        
        total_region_ops = allocation_stats['region_matches'] + allocation_stats['region_mismatches']
        region_match_rate = allocation_stats['region_matches'] / total_region_ops if total_region_ops > 0 else 0
        
        # Generate reasoning for each driver
        reasoning = {}
        driver_map = {d['driver_id']: d for d in self.drivers}
        
        for driver_id, order_ids in self.allocations.items():
            driver = driver_map[driver_id]
            schedule = sorted(self.driver_schedules[driver_id], key=lambda x: x[0])
            
            time_info = []
            for pickup, teardown, oid in schedule:
                time_info.append(f"{oid} ({pickup.strftime('%H:%M')}-{teardown.strftime('%H:%M')})")
            
            region_match_count = sum(1 for oid in order_ids if order_map[oid]['region'] == driver['preferred_region'])
            
            reasoning[driver_id] = (
                f"{driver['preferred_region']} region, capacity {len(order_ids)}/{driver['max_orders_per_day']}. "
                f"Region match: {region_match_count}/{len(order_ids)}. "
                f"Schedule: {'; '.join(time_info)}"
            )
        
        result = {
            'allocations': dict(self.allocations),
            'reasoning': reasoning,
            'warnings': [f"{oid}: {reason}" for oid, reason in unallocated],
            'metrics': {
                'total_allocated': total_allocated,
                'total_unallocated': len(unallocated),
                'vip_wedding_allocated': allocation_stats['vip_wedding_allocated'],
                'corporate_allocated': allocation_stats['corporate_allocated'],
                'regular_allocated': allocation_stats['regular_allocated'],
                'drivers_used': len(self.allocations),
                'average_orders_per_driver': total_allocated / len(self.allocations) if self.allocations else 0,
                'region_match_rate': region_match_rate,
                'time_conflicts_detected': 0  # Guaranteed 0 by design
            }
        }
        
        return result
    
    def validate_allocation(self, allocation: Dict[str, Any]) -> List[str]:
        """Validate allocation - should find ZERO issues if done deterministically"""
        issues = []
        
        allocations = allocation.get('allocations', {})
        driver_map = {d['driver_id']: d for d in self.drivers}
        order_map = {o['order_id']: o for o in self.orders}
        
        for driver_id, order_ids in allocations.items():
            if driver_id not in driver_map:
                issues.append(f"Unknown driver: {driver_id}")
                continue
            
            driver = driver_map[driver_id]
            driver_capabilities = driver.get('capabilities', [])
            driver_region = driver.get('preferred_region')
            
            # Check capacity
            if len(order_ids) > driver['max_orders_per_day']:
                issues.append(f"{driver_id} exceeds capacity: {len(order_ids)}/{driver['max_orders_per_day']}")
            
            driver_orders = []
            
            for order_id in order_ids:
                if order_id not in order_map:
                    issues.append(f"Unknown/hallucinated order: {order_id}")
                    continue
                
                order = order_map[order_id]
                driver_orders.append(order)
                
                # Check VIP/wedding capability
                tags = order.get('tags', [])
                if 'vip' in tags or 'wedding' in tags:
                    has_vip = any(cap in ['vip', 'wedding', 'large_events'] for cap in driver_capabilities)
                    if not has_vip:
                        issues.append(f"{driver_id} lacks VIP capability for {order_id}")
            
            # Check time conflicts
            for i, order1 in enumerate(driver_orders):
                pickup1 = datetime.fromisoformat(order1['pickup_time'])
                teardown1 = datetime.fromisoformat(order1['teardown_time'])
                
                for order2 in driver_orders[i+1:]:
                    pickup2 = datetime.fromisoformat(order2['pickup_time'])
                    teardown2 = datetime.fromisoformat(order2['teardown_time'])
                    
                    # Check overlap
                    if not (teardown1 <= pickup2 or teardown2 <= pickup1):
                        issues.append(
                            f"TIME CONFLICT: {driver_id} - {order1['order_id']} "
                            f"({pickup1.strftime('%H:%M')}-{teardown1.strftime('%H:%M')}) overlaps "
                            f"{order2['order_id']} ({pickup2.strftime('%H:%M')}-{teardown2.strftime('%H:%M')})"
                        )
        
        return issues
    
    def optimize_with_llm(self, initial_allocation: Dict[str, Any], validation_issues: List[str]) -> Optional[Dict[str, Any]]:
        """Use LLM to suggest improvements AFTER deterministic allocation"""
        if not validation_issues or len(validation_issues) == 0:
            print("\n✨ Initial allocation is perfect! No LLM optimization needed.")
            return initial_allocation
        
        print(f"\n🤖 Asking LLM to resolve {len(validation_issues)} issues...")
        
        prompt = f"""You are helping optimize a delivery driver allocation.

CURRENT ALLOCATION ISSUES:
{chr(10).join('- ' + issue for issue in validation_issues[:20])}  

CURRENT ALLOCATION:
{json.dumps(initial_allocation['allocations'], indent=2)}

DRIVERS DATA (for reference):
{json.dumps(self.drivers[:10], indent=2)}
... ({len(self.drivers)} drivers total)

ORDERS DATA (for reference):
{json.dumps(self.orders[:10], indent=2)}
... ({len(self.orders)} orders total)

YOUR TASK:
Suggest specific reassignments to fix the issues above. Focus on:
1. Resolving time conflicts by moving orders to different drivers
2. Ensuring VIP/wedding orders go to capable drivers
3. Maintaining region matches when possible

RESPONSE FORMAT (JSON only):
{{
  "suggested_moves": [
    {{
      "order_id": "Q1234",
      "from_driver": "DRV-001",
      "to_driver": "DRV-002",
      "reason": "Resolves time conflict with Q5678"
    }}
  ],
  "explanation": "Brief summary of the optimization strategy"
}}

Only suggest moves that will fix actual problems. Be conservative."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a logistics optimization expert. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            suggestions = json.loads(response.choices[0].message.content)
            print(f"\n💡 LLM Suggestions: {suggestions.get('explanation', 'No explanation')}")
            
            return suggestions
            
        except Exception as e:
            print(f"⚠️  LLM optimization failed: {e}")
            return None
    
    def format_output(self, allocation: Dict[str, Any], validation_issues: List[str]):
        """Pretty print results"""
        print("\n" + "="*80)
        print("📋 ALLOCATION RESULTS")
        print("="*80)
        
        metrics = allocation.get('metrics', {})
        print(f"\n📊 METRICS:")
        print(f"   Total Allocated: {metrics.get('total_allocated', 0)}/{len(self.orders)} orders")
        print(f"   Unallocated: {metrics.get('total_unallocated', 0)} orders")
        print(f"   VIP/Wedding: {metrics.get('vip_wedding_allocated', 0)}")
        print(f"   Corporate: {metrics.get('corporate_allocated', 0)}")
        print(f"   Regular: {metrics.get('regular_allocated', 0)}")
        print(f"   Drivers Used: {metrics.get('drivers_used', 0)}/{len(self.drivers)}")
        print(f"   Avg Orders/Driver: {metrics.get('average_orders_per_driver', 0):.1f}")
        print(f"   Region Match Rate: {metrics.get('region_match_rate', 0):.1%}")
        print(f"   Time Conflicts: {metrics.get('time_conflicts_detected', 0)} ✅")
        
        if validation_issues:
            print(f"\n❌ VALIDATION ISSUES ({len(validation_issues)}):")
            print("-"*80)
            for issue in validation_issues[:20]:
                print(f"   • {issue}")
            if len(validation_issues) > 20:
                print(f"   ... and {len(validation_issues) - 20} more issues")
        else:
            print(f"\n✅ PERFECT ALLOCATION - Zero conflicts!")
        
        warnings = allocation.get('warnings', [])
        if warnings:
            print(f"\n⚠️  UNALLOCATED ORDERS ({len(warnings)}):")
            print("-"*80)
            for warning in warnings[:10]:
                print(f"   • {warning}")
        
        print("\n" + "="*80)
    
    def save_results(self, allocation: Dict[str, Any], output_file: str = './data/deterministic-allocation_results.json'):
        """Save allocation results"""
        with open(output_file, 'w') as f:
            json.dump(allocation, f, indent=2)
        print(f"\n💾 Results saved to {output_file}")


def main():
    allocator = DeterministicAllocator()
    allocator.load_data('./data/drivers.json', './data/orders.json')
    
    # Do deterministic allocation
    allocation = allocator.allocate_deterministically()
    
    # Validate
    validation_issues = allocator.validate_allocation(allocation)
    
    # Display results
    allocator.format_output(allocation, validation_issues)
    
    # Optionally try LLM optimization if there are issues
    if validation_issues:
        suggestions = allocator.optimize_with_llm(allocation, validation_issues)
        # You could apply suggestions here if needed
    
    # Save
    allocator.save_results(allocation)


if __name__ == "__main__":
    main()