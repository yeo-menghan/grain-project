# allocator/ai/prompt_builder.py
"""Prompt building for AI allocation"""
import json
from typing import Dict, Any, List
from allocator.models import Driver, Order


class PromptBuilder:
    """Builds prompts for AI allocation"""
    
    @staticmethod
    def build_initial_prompt(order_analysis: Dict, driver_analysis: Dict,
                           drivers: List[Driver], orders: List[Order]) -> str:
        """Create structured prompt for LLM"""
        
        # Convert model objects to dicts
        drivers_data = [d.to_dict() for d in drivers]
        orders_data = [o.to_dict() for o in orders]
        
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
{json.dumps(drivers_data, indent=2)}

ORDERS DATA:
{json.dumps(orders_data, indent=2)}

RESPONSE FORMAT:
Return your allocation as a valid JSON object with this exact structure:
{{
  "allocations": {{
    "DRV-001": ["Q3370", "Q3371"],
    "DRV-002": ["P9764"]
  }},
  "reasoning": {{
    "Q3370": "Assigned to DRV-001 (north region specialist). Order is in north region (matching preferred region). No time conflicts with other orders. Driver has wedding capability for this wedding order.",
    "Q3371": "Assigned to DRV-001 (north region specialist). Order is in north region (matching preferred region). Pickup at 19:30 does not conflict with Q3370 which ends at 06:00. Regular order, driver has capacity.",
    "P9764": "Assigned to DRV-002 (west region, corporate capable). Only corporate-capable driver available in this time slot. Order is in east region (not matching) but no west region corporate drivers available."
  }},
  "warnings": [
    "DRV-008 assigned 6 orders (at max capacity of 6)",
    "Order Q9999 UNALLOCATED - no available wedding-capable drivers in time window"
  ]
}}

IMPORTANT NOTES:
- The "reasoning" field should have ONE ENTRY PER ORDER (not per driver)
- Each order's reasoning should explain WHY that specific order was assigned to that specific driver
- Include information about: region matching, capability requirements, time conflicts checked, alternative options considered

DOUBLE-CHECK BEFORE RESPONDING:
1. ✓ Every wedding/VIP/large event order is assigned to a wedding-capable driver
2. ✓ Every corporate order is assigned to a corporate-capable driver (or wedding-capable if needed)
3. ✓ NO driver has overlapping time windows for their orders
4. ✓ NO driver exceeds their max_orders_per_day
5. ✓ Wedding-capable drivers are primarily used for wedding orders
6. ✓ Regular orders are handled by standard/corporate drivers when possible
7. ✓ Region matches are maximized (aim for >90% match rate)
8. ✓ All driver IDs and order IDs in your response exactly match the input data
9. ✓ Reasoning is provided for EVERY allocated order (not every driver)

IMPORTANT: 
- TIME CONFLICTS are the #1 issue to avoid - check carefully
- DO NOT waste wedding-capable drivers on regular orders if wedding orders need them
- Prefer region matching - only assign to different regions if necessary
- Only return the JSON, no additional text
- If an order cannot be allocated due to constraints, include it in warnings with specific reason
- Provide reasoning for EACH ORDER explaining the assignment decision
"""
        return prompt
    
    @staticmethod
    def build_correction_prompt(previous_allocation: Dict[str, Any],
                              validation_issues: List[str],
                              order_analysis: Dict, driver_analysis: Dict,
                              drivers: List[Driver], orders: List[Order]) -> str:
        """Create prompt to fix validation issues"""
        
        # Convert model objects to dicts
        drivers_data = [d.to_dict() for d in drivers]
        orders_data = [o.to_dict() for o in orders]
        
        # Categorize issues
        from allocator.utils import categorize_validation_issues
        issue_breakdown = categorize_validation_issues(validation_issues)
        
        time_conflicts = [i for i in validation_issues if 'TIME CONFLICT' in i]
        capability_issues = [i for i in validation_issues if 'lacks' in i and 'capability' in i]
        capacity_issues = [i for i in validation_issues if 'assigned' in i and 'max is' in i]
        region_issues = [i for i in validation_issues if 'region matching' in i]
        resource_waste = [i for i in validation_issues if 'wedding-capable driver wasted' in i or 'RESOURCE WASTE' in i]
        
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
{json.dumps(drivers_data, indent=2)}

ORDERS DATA:
{json.dumps(orders_data, indent=2)}

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
- Orders with 'wedding' tags MUST go to wedding-capable drivers
- NO time conflicts allowed
- Never exceed driver max_orders_per_day
- Minimize waste of wedding-capable driver capacity
- Maintain or improve region match rate
- Number of orders assigned should not exceed original number of orders (i.e. it should not be 66 assigned orders if there's only 60 orders to begin with)

RESPONSE FORMAT:
Return a corrected allocation in the same JSON format:
{{
  "allocations": {{ ... }},
  "reasoning": {{ 
    "ORDER_ID": "Explanation for why this order was assigned to this driver",
    ...
  }},
  "warnings": [ ... ]
}}

REMEMBER: Provide reasoning for EACH ORDER (not each driver). Each order should have one reasoning entry explaining the assignment decision.

Focus on fixing the validation issues above. Only return the JSON, no additional text.
"""
        return prompt