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
            'wedding_orders': [],
            'corporate_orders': [],
            'regular_orders': [],
            'orders_by_region': {},
            'orders_by_time_slot': {}
        }
        
        for order in self.orders:
            # Categorize by tags
            tags = order.get('tags', [])
            
            # Simplified: Any order with 'vip', 'wedding', or 'large_events' tag is a wedding order
            if any(tag in ['vip', 'wedding', 'large_events'] for tag in tags):
                analysis['wedding_orders'].append(order['order_id'])
            elif 'corporate' in tags or 'seminars' in tags:
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
            'wedding_capable_drivers': [],
            'corporate_capable_drivers': [],
            'standard_drivers': [],
            'drivers_by_region': {},
            'total_capacity': 0
        }
        
        for driver in self.drivers:
            capabilities = driver.get('capabilities', [])
            
            # Simplified: Track wedding capable drivers (vip, wedding, or large_events)
            is_wedding_capable = any(cap in ['vip', 'wedding', 'large_events'] for cap in capabilities)
            
            if is_wedding_capable:
                analysis['wedding_capable_drivers'].append(driver['driver_id'])
            elif any(cap in ['corporate', 'seminars'] for cap in capabilities):
                analysis['corporate_capable_drivers'].append(driver['driver_id'])
            else:
                analysis['standard_drivers'].append(driver['driver_id'])
            
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
- Wedding Orders (VIP/weddings/large events - need special capabilities): {len(order_analysis['wedding_orders'])}
- Corporate Orders: {len(order_analysis['corporate_orders'])}
- Regular Orders: {len(order_analysis['regular_orders'])}

- Total Drivers: {driver_analysis['total_drivers']}
- Wedding-Capable Drivers: {len(driver_analysis['wedding_capable_drivers'])} (SCARCE RESOURCE!)
- Corporate-Capable Drivers: {len(driver_analysis['corporate_capable_drivers'])}
- Standard Drivers: {len(driver_analysis['standard_drivers'])}
- Total Driver Capacity: {driver_analysis['total_capacity']} orders/day

CRITICAL CONSTRAINTS - THESE MUST BE SATISFIED 100%:

1. TIME CONFLICTS (HIGHEST PRIORITY):
   - Each order has a pickup_time and teardown_time
   - A driver CANNOT be assigned two orders if their time windows overlap AT ALL
   - Example: Order A (18:00-22:00) and Order B (20:00-00:00) CONFLICT - they overlap from 20:00-22:00
   - Example: Order C (18:00-22:00) and Order D (22:00-02:00) DO NOT conflict - D starts when C ends
   - BEFORE assigning any order to a driver, check ALL previously assigned orders for that driver
   - If ANY time overlap exists, DO NOT assign the order to that driver
   
2. WEDDING CAPABILITY REQUIREMENTS (CRITICAL):
   - Orders with tags "vip", "wedding", OR "large_events" REQUIRE wedding-capable drivers
   - Wedding-capable drivers have at least one of these capabilities: "vip", "wedding", "large_events"
   - There are only {len(driver_analysis['wedding_capable_drivers'])} wedding-capable drivers
   - These drivers are: {', '.join(driver_analysis['wedding_capable_drivers'])}
   - NEVER assign wedding/VIP/large event orders to drivers without wedding capabilities
   
3. EFFICIENT RESOURCE UTILIZATION (IMPORTANT):
   - Wedding-capable drivers are a SCARCE RESOURCE
   - PRIORITY ORDER for wedding-capable drivers:
     a. FIRST: Assign ALL wedding orders to wedding-capable drivers
     b. ONLY AFTER all wedding orders are assigned: Use remaining capacity for corporate/regular orders
   - DO NOT waste wedding-capable driver capacity on regular orders if wedding orders are unallocated
   - Standard drivers should handle regular orders whenever possible
   
4. CAPACITY LIMITS:
   - Each driver has max_orders_per_day - NEVER exceed this limit
   - Count carefully: if a driver is at capacity, they cannot take more orders

5. REGION MATCHING (STRONGLY PREFERRED):
   - Each driver has a "preferred_region" field
   - Each order has a "region" field
   - STRONGLY prefer matching order.region to driver.preferred_region
   - Only assign orders to different regions if absolutely necessary (e.g., no capacity in preferred region)
   - When choosing between two drivers with equal capabilities, ALWAYS choose the one with matching region

ALLOCATION ALGORITHM - FOLLOW THIS STEP BY STEP:

Step 1: Sort all wedding orders (VIP/wedding/large_events) by pickup time
Step 2: For each wedding order (in time order):
   a. Find all wedding-capable drivers with matching region
   b. For each candidate driver, check if order time conflicts with their existing assignments
   c. Choose the first driver with no conflicts and available capacity
   d. If no matching region drivers available, try other region wedding-capable drivers
   e. If still no driver available, mark order as UNALLOCATED

Step 3: Sort all corporate orders by pickup time
Step 4: For each corporate order (in time order):
   a. FIRST try corporate-capable (non-wedding) drivers with matching region
   b. If none available, try wedding-capable drivers with spare capacity
   c. Check for time conflicts with existing assignments
   d. Assign to first available driver
   e. If no driver available, mark as UNALLOCATED

Step 5: Sort all regular orders by pickup time
Step 6: For each regular order (in time order):
   a. FIRST try standard/corporate drivers with matching region
   b. ONLY IF NO standard/corporate drivers available, use wedding-capable drivers
   c. Check for time conflicts
   d. Assign to first available driver
   e. If no driver available, mark as UNALLOCATED

Step 7: Verify ZERO time conflicts exist in final allocation
Step 8: Verify NO wedding orders assigned to non-wedding-capable drivers
Step 9: Verify wedding-capable drivers prioritized for wedding orders

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

In essence, two orders conflict IF: 
NOT (order1.teardown_time <= order2.pickup_time OR order2.teardown_time <= order1.pickup_time)

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
    "Order Q9999 UNALLOCATED - no available wedding-capable drivers in time window"
  ],
  "metrics": {{
    "total_allocated": 58,
    "total_unallocated": 2,
    "wedding_orders_allocated": 15,
    "corporate_orders_allocated": 10,
    "regular_orders_allocated": 33,
    "drivers_used": 25,
    "average_orders_per_driver": 2.3,
    "region_match_rate": 0.85,
    "wedding_drivers_on_wedding_orders": 12,
    "wedding_drivers_on_regular_orders": 3
  }}
}}

DOUBLE-CHECK BEFORE RESPONDING:
1. ✓ Every wedding/VIP/large event order is assigned to a wedding-capable driver
2. ✓ Every corporate order is assigned to a corporate-capable driver (or wedding-capable if needed)
3. ✓ NO driver has overlapping time windows for their orders
4. ✓ NO driver exceeds their max_orders_per_day
5. ✓ Wedding-capable drivers are primarily used for wedding orders
6. ✓ Regular orders are handled by standard/corporate drivers when possible
7. ✓ Region matches are maximized (aim for >90% match rate)
8. ✓ All driver IDs and order IDs in your response exactly match the input data

IMPORTANT: 
- TIME CONFLICTS are the #1 issue to avoid - check carefully
- DO NOT waste wedding-capable drivers on regular orders if wedding orders need them
- Prefer region matching - only assign to different regions if necessary
- Only return the JSON, no additional text
- If an order cannot be allocated due to constraints, include it in warnings with specific reason
"""
        return prompt
    
    def create_correction_prompt(self, previous_allocation: Dict[str, Any], 
                                 validation_issues: List[str], 
                                 order_analysis: Dict, 
                                 driver_analysis: Dict) -> str:
        """Create prompt to fix validation issues"""
        
        # Categorize issues
        time_conflicts = [i for i in validation_issues if 'TIME CONFLICT' in i]
        capability_issues = [i for i in validation_issues if 'lacks' in i and 'capability' in i]
        capacity_issues = [i for i in validation_issues if 'assigned' in i and 'max is' in i]
        region_issues = [i for i in validation_issues if 'region matching' in i]
        resource_waste = [i for i in validation_issues if 'wedding-capable driver wasted' in i]
        
        prompt = f"""Your previous allocation attempt had {len(validation_issues)} validation issue(s). Please fix them and provide a corrected allocation.

ISSUE BREAKDOWN:
- Time Conflicts: {len(time_conflicts)}
- Capability Mismatches: {len(capability_issues)}
- Capacity Violations: {len(capacity_issues)}
- Region Mismatches: {len(region_issues)}
- Resource Waste (wedding drivers on regular orders): {len(resource_waste)}

ALL VALIDATION ISSUES:
{chr(10).join(f"- {issue}" for issue in validation_issues)}

YOUR PREVIOUS ALLOCATION:
{json.dumps(previous_allocation.get('allocations', {}), indent=2)}

SITUATION OVERVIEW:
- Total Orders: {order_analysis['total_orders']}
- Wedding Orders: {len(order_analysis['wedding_orders'])}
- Corporate Orders: {len(order_analysis['corporate_orders'])}
- Regular Orders: {len(order_analysis['regular_orders'])}
- Wedding-Capable Drivers: {len(driver_analysis['wedding_capable_drivers'])} (SCARCE!)
- Corporate-Capable Drivers: {len(driver_analysis['corporate_capable_drivers'])}
- Standard Drivers: {len(driver_analysis['standard_drivers'])}

DRIVERS DATA:
{json.dumps(self.drivers, indent=2)}

ORDERS DATA:
{json.dumps(self.orders, indent=2)}

INSTRUCTIONS TO FIX ISSUES:

1. TIME CONFLICTS ({len(time_conflicts)} issues):
   - For any driver with time conflicts, reassign conflicting orders to other available drivers
   - Double-check: two orders conflict IF NOT (order1.teardown <= order2.pickup OR order2.teardown <= order1.pickup)

2. CAPABILITY MISMATCHES ({len(capability_issues)} issues):
   - Move wedding/VIP orders to wedding-capable drivers ONLY
   - Wedding-capable drivers: {', '.join(driver_analysis['wedding_capable_drivers'])}

3. RESOURCE WASTE ({len(resource_waste)} issues):
   - DO NOT assign regular orders to wedding-capable drivers if wedding orders exist
   - Move regular orders from wedding-capable drivers to standard/corporate drivers
   - Keep wedding-capable drivers available for wedding orders

4. CAPACITY EXCEEDED ({len(capacity_issues)} issues):
   - Redistribute orders from overloaded drivers to those with available capacity

5. REGION MISMATCHES ({len(region_issues)} issues):
   - Try to improve region matching where possible without violating hard constraints
   - Only assign different region if truly no capacity in matching region

ALLOCATION PRIORITY:
1. Wedding orders → Wedding-capable drivers (matching region first)
2. Corporate orders → Corporate-capable drivers (matching region first)
3. Regular orders → Standard/Corporate drivers (matching region first)
4. Only use wedding-capable drivers for regular orders if all wedding orders are allocated

CRITICAL RULES (MUST FOLLOW):
- Orders with 'vip', 'wedding', or 'large_events' tags MUST go to wedding-capable drivers
- NO time conflicts allowed
- Never exceed driver max_orders_per_day
- Minimize waste of wedding-capable driver capacity
- Maintain or improve region match rate

RESPONSE FORMAT:
Return a corrected allocation in the same JSON format:
{{
  "allocations": {{ ... }},
  "reasoning": {{ ... }},
  "warnings": [ ... ],
  "metrics": {{
    ...,
    "wedding_drivers_on_wedding_orders": X,
    "wedding_drivers_on_regular_orders": Y
  }}
}}

Focus on fixing the validation issues above. Only return the JSON, no additional text.
"""
        return prompt
    
    def allocate_with_ai(self, max_retries: int = 5) -> Dict[str, Any]:
        """Use GPT-4 to create allocation plan with retry logic"""
        print("\n🤖 Analyzing orders and drivers...")
        
        order_analysis = self.preprocess_orders()
        driver_analysis = self.preprocess_drivers()
        
        print(f"\n📊 Analysis Summary:")
        print(f"   Wedding Orders (VIP/Wedding/Large Events): {len(order_analysis['wedding_orders'])}")
        print(f"   Wedding-Capable Drivers: {len(driver_analysis['wedding_capable_drivers'])}")
        print(f"   Corporate Orders: {len(order_analysis['corporate_orders'])}")
        print(f"   Corporate-Capable Drivers: {len(driver_analysis['corporate_capable_drivers'])}")
        print(f"   Standard Drivers: {len(driver_analysis['standard_drivers'])}")
        print(f"   Regular Orders: {len(order_analysis['regular_orders'])}")
        print(f"   Total Capacity: {driver_analysis['total_capacity']} orders/day")
        print(f"   Orders by Region: {dict(sorted({k: len(v) for k, v in order_analysis['orders_by_region'].items()}.items()))}")
        
        # First attempt
        prompt = self.create_allocation_prompt(order_analysis, driver_analysis)
        
        print(f"\n🚀 Sending allocation request to GPT-4 (Attempt 1/{max_retries + 1})...")
        
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
            
            # Validate and retry if needed
            for retry_count in range(max_retries):
                validation_issues = self.validate_allocation(allocation_result)
                
                if not validation_issues:
                    print(f"✅ Allocation successful on attempt {retry_count + 1}")
                    break
                
                print(f"\n⚠️  Found {len(validation_issues)} validation issue(s) on attempt {retry_count + 1}")
                
                # Show issue breakdown
                time_conflicts = len([i for i in validation_issues if 'TIME CONFLICT' in i])
                capability_issues = len([i for i in validation_issues if 'lacks' in i and 'capability' in i])
                resource_waste = len([i for i in validation_issues if 'wedding-capable driver wasted' in i])
                
                print(f"   - Time conflicts: {time_conflicts}")
                print(f"   - Capability mismatches: {capability_issues}")
                print(f"   - Resource waste: {resource_waste}")
                
                print(f"🔄 Requesting corrections (Attempt {retry_count + 2}/{max_retries + 1})...")
                
                # Create correction prompt
                correction_prompt = self.create_correction_prompt(
                    allocation_result, 
                    validation_issues, 
                    order_analysis, 
                    driver_analysis
                )
                
                # Request correction
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert logistics optimizer. Always respond with valid JSON only."},
                        {"role": "user", "content": correction_prompt}
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
        
        # Track which wedding orders are allocated
        wedding_orders = set()
        for order in self.orders:
            tags = order.get('tags', [])
            if any(tag in ['vip', 'wedding', 'large_events'] for tag in tags):
                wedding_orders.add(order['order_id'])
        
        allocated_wedding_orders = set()
        
        for driver_id, order_ids in allocations.items():
            if driver_id not in driver_map:
                issues.append(f"Unknown driver: {driver_id}")
                continue
            
            driver = driver_map[driver_id]
            driver_capabilities = driver.get('capabilities', [])
            driver_region = driver.get('preferred_region')
            
            # Check if driver is wedding-capable
            is_wedding_capable = any(cap in ['vip', 'wedding', 'large_events'] for cap in driver_capabilities)
            
            # Check capacity
            if len(order_ids) > driver['max_orders_per_day']:
                issues.append(f"❌ CAPACITY: {driver_id} ({driver['name']}) assigned {len(order_ids)} orders, max is {driver['max_orders_per_day']}")
            
            # Check capabilities and time conflicts
            driver_orders = []
            region_mismatches = 0
            driver_has_wedding_orders = False
            driver_has_regular_orders = False
            
            for order_id in order_ids:
                if order_id not in order_map:
                    issues.append(f"Unknown order: {order_id}")
                    continue
                
                order = order_map[order_id]
                driver_orders.append(order)
                
                # Check wedding capability
                tags = order.get('tags', [])
                requires_wedding_capability = any(tag in ['vip', 'wedding', 'large_events'] for tag in tags)
                
                if requires_wedding_capability:
                    allocated_wedding_orders.add(order_id)
                    driver_has_wedding_orders = True
                    if not is_wedding_capable:
                        issues.append(f"❌ CAPABILITY: {driver_id} lacks wedding capability for order {order_id} (tags: {tags})")
                else:
                    driver_has_regular_orders = True
                
                # Check region match
                if order.get('region') != driver_region:
                    region_mismatches += 1
            
            # Check for resource waste: wedding-capable driver on regular orders when wedding orders unallocated
            unallocated_wedding_orders = wedding_orders - allocated_wedding_orders
            if is_wedding_capable and driver_has_regular_orders and len(unallocated_wedding_orders) > 0:
                issues.append(f"❌ RESOURCE WASTE: {driver_id} is wedding-capable but assigned regular orders while {len(unallocated_wedding_orders)} wedding orders remain unallocated")
            
            # Report region mismatches
            if region_mismatches > 0 and len(order_ids) > 0:
                match_rate = (len(order_ids) - region_mismatches) / len(order_ids)
                if match_rate < 0.5:
                    issues.append(f"⚠️ REGION: {driver_id} has poor region matching: {region_mismatches}/{len(order_ids)} orders not in preferred region '{driver_region}'")
            
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
        print(f"   Wedding Orders Allocated: {metrics.get('wedding_orders_allocated', 0)}")
        print(f"   Corporate Orders Allocated: {metrics.get('corporate_orders_allocated', 0)}")
        print(f"   Regular Orders Allocated: {metrics.get('regular_orders_allocated', 0)}")
        print(f"   Drivers Used: {metrics.get('drivers_used', 0)}/{len(self.drivers)}")
        print(f"   Avg Orders/Driver: {metrics.get('average_orders_per_driver', 0):.1f}")
        print(f"   Region Match Rate: {metrics.get('region_match_rate', 0):.1%}")
        
        # Resource utilization
        wedding_on_wedding = metrics.get('wedding_drivers_on_wedding_orders', 0)
        wedding_on_regular = metrics.get('wedding_drivers_on_regular_orders', 0)
        if wedding_on_wedding or wedding_on_regular:
            print(f"   Wedding Drivers on Wedding Orders: {wedding_on_wedding}")
            print(f"   Wedding Drivers on Regular Orders: {wedding_on_regular}")
        
        # Count time conflicts from validation
        time_conflicts = len([i for i in validation_issues if 'TIME CONFLICT' in i])
        if time_conflicts > 0:
            print(f"   ⚠️  Time Conflicts Found: {time_conflicts}")
        
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
            
            # Determine capability type
            capabilities = driver.get('capabilities', [])
            is_wedding_capable = any(cap in ['vip', 'wedding', 'large_events'] for cap in capabilities)
            capability_type = "Wedding-capable" if is_wedding_capable else "Standard"
            
            print(f"\n{driver_id} - {driver.get('name', 'Unknown')} ({capability_type})")
            print(f"   Preferred Region: {driver.get('preferred_region', 'N/A')}")
            print(f"   Capacity: {len(order_ids)}/{driver.get('max_orders_per_day', 'N/A')} orders")
            print(f"   Capabilities: {', '.join(capabilities) or 'None'}")
            print(f"   Reasoning: {reasoning.get(driver_id, 'No reasoning provided')}")
            print(f"   Orders:")
            
            for order_id in sorted(order_ids, key=lambda oid: order_map.get(oid, {}).get('pickup_time', '')):
                order = order_map.get(order_id, {})
                pickup = order.get('pickup_time', 'N/A')
                teardown = order.get('teardown_time', 'N/A')
                region = order.get('region', 'N/A')
                tags = order.get('tags', [])
                pax = order.get('pax_count', 'N/A')
                
                # Determine order type
                is_wedding_order = any(tag in ['vip', 'wedding', 'large_events'] for tag in tags)
                order_type = "🎉 WEDDING" if is_wedding_order else "📦"
                
                # Highlight region mismatch
                region_match = "✓" if region == driver.get('preferred_region') else "⚠️"
                
                tags_str = ', '.join(tags) or 'none'
                
                print(f"      {order_type} {order_id}: {region} {region_match} | {pax} pax | {pickup} → {teardown} | tags: {tags_str}")
        
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
    
    # Run AI allocation with retry logic (max 5 retries = 6 total attempts)
    allocation = allocator.allocate_with_ai(max_retries=5)
    
    # Final validation
    validation_issues = allocator.validate_allocation(allocation)
    
    # Display results
    allocator.format_output(allocation, validation_issues)
    
    # Save results
    allocator.save_results(allocation)


if __name__ == "__main__":
    main()