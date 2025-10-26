# allocator.py
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

class DeliveryAllocator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.drivers = []
        self.orders = []
        
    def load_data(self, drivers_file: str, orders_file: str):
        """Load driver and order data from JSON files"""
        with open(drivers_file, 'r') as f:
            self.drivers = json.load(f)
        with open(orders_file, 'r') as f:
            self.orders = json.load(f)
        
        print(f"Loaded {len(self.drivers)} drivers and {len(self.orders)} orders")
    
    def preprocess_orders(self) -> Dict[str, Any]:
        """Analyze orders and identify constraints"""
        analysis = {
            'total_orders': len(self.orders),
            'vip_wedding_orders': [],
            'corporate_orders': [],
            'regular_orders': [],
            'orders_by_region': {},
            'orders_by_time_slot': {}
        }
        
        for order in self.orders:
            # Categorize by tags
            tags = order.get('tags', [])
            if 'vip' in tags or 'wedding' in tags:
                analysis['vip_wedding_orders'].append(order['order_id'])
            elif 'corporate' in tags:
                analysis['corporate_orders'].append(order['order_id'])
            else:
                analysis['regular_orders'].append(order['order_id'])
            
            # Group by region
            region = order['region']
            if region not in analysis['orders_by_region']:
                analysis['orders_by_region'][region] = []
            analysis['orders_by_region'][region].append(order['order_id'])
            
            # Group by pickup time slot (hour)
            pickup_time = datetime.fromisoformat(order['pickup_time'])
            time_slot = f"{pickup_time.date()}_{pickup_time.hour:02d}:00"
            if time_slot not in analysis['orders_by_time_slot']:
                analysis['orders_by_time_slot'][time_slot] = []
            analysis['orders_by_time_slot'][time_slot].append(order['order_id'])
        
        return analysis
    
    def preprocess_drivers(self) -> Dict[str, Any]:
        """Analyze driver capabilities"""
        analysis = {
            'total_drivers': len(self.drivers),
            'vip_wedding_drivers': [],
            'corporate_drivers': [],
            'drivers_by_region': {},
            'total_capacity': 0
        }
        
        for driver in self.drivers:
            capabilities = driver.get('capabilities', [])
            
            # Track VIP/wedding capable drivers
            if any(cap in ['vip', 'wedding', 'large_events'] for cap in capabilities):
                analysis['vip_wedding_drivers'].append(driver['driver_id'])
            
            # Track corporate capable drivers
            if any(cap in ['corporate', 'seminars'] for cap in capabilities):
                analysis['corporate_drivers'].append(driver['driver_id'])
            
            # Group by region
            region = driver['preferred_region']
            if region not in analysis['drivers_by_region']:
                analysis['drivers_by_region'][region] = []
            analysis['drivers_by_region'][region].append(driver['driver_id'])
            
            # Calculate total capacity
            analysis['total_capacity'] += driver['max_orders_per_day']
        
        return analysis
    
    def create_allocation_prompt(self, order_analysis: Dict, driver_analysis: Dict) -> str:
        """Create structured prompt for LLM"""
        
        prompt = f"""You are an expert operations optimizer for a catering delivery company. Your task is to intelligently assign orders to delivery drivers.

SITUATION OVERVIEW:
- Total Orders: {order_analysis['total_orders']}
- VIP/Wedding Orders (need special capabilities): {len(order_analysis['vip_wedding_orders'])}
- Corporate Orders: {len(order_analysis['corporate_orders'])}
- Regular Orders: {len(order_analysis['regular_orders'])}

- Total Drivers: {driver_analysis['total_drivers']}
- VIP/Wedding Capable Drivers: {len(driver_analysis['vip_wedding_drivers'])}
- Corporate Capable Drivers: {len(driver_analysis['corporate_drivers'])}
- Total Driver Capacity: {driver_analysis['total_capacity']} orders/day

CRITICAL CONSTRAINTS - THESE MUST BE SATISFIED 100%:

1. TIME CONFLICTS (HIGHEST PRIORITY):
   - Each order has a pickup_time and teardown_time
   - A driver CANNOT be assigned two orders if their time windows overlap AT ALL
   - Example: Order A (18:00-22:00) and Order B (20:00-00:00) CONFLICT - they overlap from 20:00-22:00
   - Example: Order C (18:00-22:00) and Order D (22:00-02:00) DO NOT conflict - D starts when C ends
   - BEFORE assigning any order to a driver, check ALL previously assigned orders for that driver
   - If ANY time overlap exists, DO NOT assign the order to that driver
   
2. VIP/WEDDING CAPABILITY REQUIREMENTS:
   - Orders with tags "vip" OR "wedding" MUST go to drivers with capabilities: "vip", "wedding", OR "large_events"
   - There are only {len(driver_analysis['vip_wedding_drivers'])} VIP-capable drivers
   - These drivers are: {', '.join(driver_analysis['vip_wedding_drivers'])}
   - NEVER assign VIP/wedding orders to drivers without these capabilities
   
3. CAPACITY LIMITS:
   - Each driver has max_orders_per_day - NEVER exceed this limit
   - Count carefully: if a driver is at capacity, they cannot take more orders

4. REGION MATCHING (STRONGLY PREFERRED):
   - Each driver has a "preferred_region" field
   - Each order has a "region" field
   - STRONGLY prefer matching order.region to driver.preferred_region
   - Only assign orders to different regions if absolutely necessary (e.g., no capacity in preferred region)
   - When choosing between two drivers with equal capabilities, ALWAYS choose the one with matching region

ALLOCATION ALGORITHM - FOLLOW THIS STEP BY STEP:

Step 1: Sort all VIP/wedding orders by pickup time
Step 2: For each VIP/wedding order (in time order):
   a. Find all drivers with VIP/wedding capabilities AND matching region
   b. For each candidate driver, check if order time conflicts with their existing assignments
   c. Choose the first driver with no conflicts and available capacity
   d. If no matching region drivers available, try other region VIP drivers
   e. If still no driver available, mark order as UNALLOCATED

Step 3: Process corporate orders (same logic, but with corporate-capable drivers)

Step 4: Process regular orders (same logic, all drivers eligible)

Step 5: Verify ZERO time conflicts exist in final allocation

EXAMPLE TIME CONFLICT CHECK:

Driver DRV-001 current assignments:

- Order Q1: pickup 2024-11-02T18:00:00, teardown 2024-11-02T22:00:00
- Order Q2: pickup 2024-11-02T22:00:00, teardown 2024-11-03T02:00:00

Checking new Order Q3: pickup 2024-11-02T20:00:00, teardown 2024-11-03T00:00:00

- Q3 vs Q1: Q3 starts (20:00) BEFORE Q1 ends (22:00) → CONFLICT! ❌
Cannot assign Q3 to DRV-001

Checking new Order Q4: pickup 2024-11-03T02:00:00, teardown 2024-11-03T06:00:00
- Q4 vs Q1: Q4 starts (02:00) AFTER Q1 ends (22:00) → OK ✓
- Q4 vs Q2: Q4 starts (02:00) when Q2 ends (02:00) → OK ✓
Can assign Q4 to DRV-001

DRIVERS DATA:
{json.dumps(self.drivers, indent=2)}

ORDERS DATA:
{json.dumps(self.orders, indent=2)}

RESPONSE FORMAT:
Return your allocation as a valid JSON object with this exact structure:
{{
  "allocations": {{
    "DRV-001": ["Q3370", "Q3371"],
    "DRV-002": ["P9764"]
  }},
  "reasoning": {{
    "DRV-001": "North region specialist. Assigned Q3370 (north, pickup 02:00) and Q3371 (north, pickup 19:30) - no time overlap. Both are regular orders matching preferred region.",
    "DRV-002": "West region, has corporate/seminar capabilities. Assigned P9764 (east region, pickup 00:15) - only corporate-capable driver available in time slot."
  }},
  "warnings": [
    "DRV-008 assigned 6 orders (at max capacity of 6)",
    "Order Q9999 UNALLOCATED - no available VIP-capable drivers in time window"
  ],
  "metrics": {{
    "total_allocated": 58,
    "total_unallocated": 2,
    "vip_wedding_allocated": 15,
    "drivers_used": 25,
    "average_orders_per_driver": 2.3,
    "region_match_rate": 0.85
  }}
}}

DOUBLE-CHECK BEFORE RESPONDING:
1. ✓ Every VIP/wedding order is assigned to a VIP-capable driver
2. ✓ NO driver has overlapping time windows for their orders
3. ✓ NO driver exceeds their max_orders_per_day
4. ✓ Region matches are maximized (aim for >90% match rate)
5. ✓ All driver IDs and order IDs in your response exactly match the input data

IMPORTANT: 
- TIME CONFLICTS are the #1 issue to avoid - check carefully
- Prefer region matching - only assign to different regions if necessary
- Only return the JSON, no additional text
- If an order cannot be allocated due to constraints, include it in warnings with specific reason
"""
        return prompt
    
    def allocate_with_ai(self) -> Dict[str, Any]:
        """Use GPT-4 to create allocation plan"""
        print("\n🤖 Analyzing orders and drivers...")
        
        order_analysis = self.preprocess_orders()
        driver_analysis = self.preprocess_drivers()
        
        print(f"\n📊 Analysis Summary:")
        print(f"   VIP/Wedding Orders: {len(order_analysis['vip_wedding_orders'])}")
        print(f"   VIP/Wedding Capable Drivers: {len(driver_analysis['vip_wedding_drivers'])}")
        print(f"   Total Capacity: {driver_analysis['total_capacity']} orders/day")
        print(f"   Orders by Region: {dict(sorted({k: len(v) for k, v in order_analysis['orders_by_region'].items()}.items()))}")
        
        prompt = self.create_allocation_prompt(order_analysis, driver_analysis)
        
        print(f"\n🚀 Sending allocation request to GPT-4...")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are an expert logistics optimizer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            allocation_result = json.loads(response.choices[0].message.content)
            return allocation_result
            
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {e}")
            raise
    
    def validate_allocation(self, allocation: Dict[str, Any]) -> List[str]:
        """Validate allocation against hard constraints"""
        issues = []
        
        allocations = allocation.get('allocations', {})
        
        # Create lookup maps
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
                issues.append(f"{driver_id} ({driver['name']}) assigned {len(order_ids)} orders, max is {driver['max_orders_per_day']}")
            
            # Check capabilities and time conflicts
            driver_orders = []
            region_mismatches = 0
            
            for order_id in order_ids:
                if order_id not in order_map:
                    issues.append(f"Unknown order: {order_id}")
                    continue
                
                order = order_map[order_id]
                driver_orders.append(order)
                
                # Check VIP/wedding capability
                tags = order.get('tags', [])
                if ('vip' in tags or 'wedding' in tags):
                    has_vip_capability = any(cap in ['vip', 'wedding', 'large_events'] for cap in driver_capabilities)
                    if not has_vip_capability:
                        issues.append(f"{driver_id} lacks VIP/wedding capability for order {order_id} (tags: {tags})")
                
                # Check region match
                if order.get('region') != driver_region:
                    region_mismatches += 1
            
            # Report region mismatches as warnings (not critical errors)
            if region_mismatches > 0 and len(order_ids) > 0:
                match_rate = (len(order_ids) - region_mismatches) / len(order_ids)
                if match_rate < 0.5:  # Flag if less than 50% match
                    issues.append(f"{driver_id} has poor region matching: {region_mismatches}/{len(order_ids)} orders not in preferred region '{driver_region}'")
            
            # Check time conflicts
            for i, order1 in enumerate(driver_orders):
                pickup1 = datetime.fromisoformat(order1['pickup_time'])
                teardown1 = datetime.fromisoformat(order1['teardown_time'])
                
                for order2 in driver_orders[i+1:]:
                    pickup2 = datetime.fromisoformat(order2['pickup_time'])
                    teardown2 = datetime.fromisoformat(order2['teardown_time'])
                    
                    # Check if time windows overlap
                    if not (teardown1 <= pickup2 or teardown2 <= pickup1):
                        issues.append(f"❌ TIME CONFLICT: {driver_id} has overlapping orders {order1['order_id']} ({pickup1.strftime('%H:%M')}-{teardown1.strftime('%H:%M')}) and {order2['order_id']} ({pickup2.strftime('%H:%M')}-{teardown2.strftime('%H:%M')})")
        
        return issues
    
    def format_output(self, allocation: Dict[str, Any], validation_issues: List[str]):
        """Pretty print allocation results"""
        print("\n" + "="*80)
        print("📋 ALLOCATION RESULTS")
        print("="*80)
        
        # Metrics
        metrics = allocation.get('metrics', {})
        print(f"\n📊 METRICS:")
        print(f"   Total Allocated: {metrics.get('total_allocated', 0)}/{len(self.orders)} orders")
        print(f"   Unallocated: {metrics.get('total_unallocated', 0)} orders")
        print(f"   VIP/Wedding Allocated: {metrics.get('vip_wedding_allocated', 0)}")
        print(f"   Drivers Used: {metrics.get('drivers_used', 0)}/{len(self.drivers)}")
        print(f"   Avg Orders/Driver: {metrics.get('average_orders_per_driver', 0):.1f}")
        print(f"   Region Match Rate: {metrics.get('region_match_rate', 0):.1%}")
        print(f"   Time Conflicts: {metrics.get('time_conflicts_detected', 'N/A')}")
        
        # Count time conflicts from validation
        time_conflicts = len([i for i in validation_issues if 'TIME CONFLICT' in i])
        if time_conflicts > 0:
            print(f"   ⚠️  ACTUAL Time Conflicts Found: {time_conflicts}")
        
        # Allocations
        allocations = allocation.get('allocations', {})
        reasoning = allocation.get('reasoning', {})
        
        print(f"\n👥 DRIVER ASSIGNMENTS ({len(allocations)} drivers):")
        print("-"*80)
        
        # Create driver lookup
        driver_map = {d['driver_id']: d for d in self.drivers}
        order_map = {o['order_id']: o for o in self.orders}
        
        for driver_id in sorted(allocations.keys()):
            driver = driver_map.get(driver_id, {})
            order_ids = allocations[driver_id]
            
            print(f"\n{driver_id} - {driver.get('name', 'Unknown')} (Preferred Region: {driver.get('preferred_region', 'N/A')})")
            print(f"   Capacity: {len(order_ids)}/{driver.get('max_orders_per_day', 'N/A')} orders")
            print(f"   Capabilities: {', '.join(driver.get('capabilities', [])) or 'None'}")
            print(f"   Reasoning: {reasoning.get(driver_id, 'No reasoning provided')}")
            print(f"   Orders:")
            
            for order_id in sorted(order_ids, key=lambda oid: order_map.get(oid, {}).get('pickup_time', '')):
                order = order_map.get(order_id, {})
                pickup = order.get('pickup_time', 'N/A')
                teardown = order.get('teardown_time', 'N/A')
                region = order.get('region', 'N/A')
                tags = ', '.join(order.get('tags', [])) or 'none'
                pax = order.get('pax_count', 'N/A')
                
                # Highlight region mismatch
                region_match = "✓" if region == driver.get('preferred_region') else "⚠️"
                
                print(f"      • {order_id}: {region} {region_match} | {pax} pax | {pickup} → {teardown} | tags: {tags}")
        
        # Warnings
        warnings = allocation.get('warnings', [])
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            print("-"*80)
            for warning in warnings:
                print(f"   • {warning}")
        
        # Validation issues
        if validation_issues:
            print(f"\n❌ VALIDATION ISSUES ({len(validation_issues)}):")
            print("-"*80)
            for issue in validation_issues:
                print(f"   • {issue}")
        else:
            print(f"\n✅ No validation issues found!")
        
        print("\n" + "="*80)
    
    def save_results(self, allocation: Dict[str, Any], output_file: str = './data/allocation_results.json'):
        """Save allocation results to file"""
        with open(output_file, 'w') as f:
            json.dump(allocation, f, indent=2)
        print(f"\n💾 Results saved to {output_file}")


def main():
    # Initialize allocator
    allocator = DeliveryAllocator()
    
    # Load data
    allocator.load_data('./data/drivers.json', './data/orders.json')
    
    # Run AI allocation
    allocation = allocator.allocate_with_ai()
    
    # Validate results
    validation_issues = allocator.validate_allocation(allocation)
    
    # Display results
    allocator.format_output(allocation, validation_issues)
    
    # Save results
    allocator.save_results(allocation)


if __name__ == "__main__":
    main()