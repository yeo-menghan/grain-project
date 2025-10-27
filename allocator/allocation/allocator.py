# allocator/allocation/allocator.py
"""Main allocation engine"""
from typing import Dict, Any, List, Tuple, Optional
from allocator.models import Driver, Order
from allocator.analysis import OrderAnalyzer, DriverAnalyzer, MetricsCalculator
from allocator.ai import PromptBuilder, OpenAIClient, TokenTracker
from allocator.allocation.validator import AllocationValidator
from allocator.io import ResultSaver
from allocator.config import SCORE_WEIGHTS, TRACK_TOKEN_USAGE, TOKEN_USAGE_FILE
from allocator.utils import categorize_validation_issues


class AllocationEngine:
    """Main allocation engine coordinating the allocation process"""
    
    def __init__(self, drivers: List[Driver], orders: List[Order]):
        self.drivers = drivers
        self.orders = orders
        self.validator = AllocationValidator(drivers, orders)
        self.ai_client = OpenAIClient()
        self.saver = ResultSaver()
        self.token_tracker = TokenTracker() if TRACK_TOKEN_USAGE else None
    
    def calculate_score(self, validation_issues: List[str]) -> Tuple[int, Dict[str, int]]:
        """Calculate a score for an attempt. Lower is better."""
        categories = categorize_validation_issues(validation_issues)
        
        score = sum(
            categories[category] * weight 
            for category, weight in SCORE_WEIGHTS.items()
        )
        
        return score, categories
    
    def allocate(self, max_retries: int = 5) -> Tuple[Dict[str, Any], str]:
        """
        Generate allocation with retry logic.
        Returns the best attempt and its filepath.
        """
        print("\n🤖 Analyzing orders and drivers...")
        
        # Analyze data
        order_analysis = OrderAnalyzer.analyze(self.orders)
        driver_analysis = DriverAnalyzer.analyze(self.drivers)
        
        self._print_analysis_summary(order_analysis, driver_analysis)
        
        # Track all attempts
        all_attempts = []
        
        # First attempt
        prompt = PromptBuilder.build_initial_prompt(
            order_analysis, driver_analysis, self.drivers, self.orders
        )
        
        print(f"\n🚀 Sending allocation request to GPT-4 (Attempt 1/{max_retries + 1})...")
        
        allocation_result, token_usage = self._try_generate_allocation(prompt, attempt_num=1)
        
        if not allocation_result:
            print("❌ Failed to generate initial allocation")
            self._save_token_usage()
            return self._create_empty_allocation(), ""
        
        validation_issues = self.validator.validate(allocation_result)
        score, issue_breakdown = self.calculate_score(validation_issues)
        
        metrics = MetricsCalculator.calculate(allocation_result, self.drivers, self.orders)
        filepath = self.saver.save_attempt(
            1, allocation_result, validation_issues, score, issue_breakdown, metrics
        )
        
        all_attempts.append({
            'attempt_num': 1,
            'allocation': allocation_result,
            'validation_issues': validation_issues,
            'score': score,
            'issue_breakdown': issue_breakdown,
            'filepath': filepath
        })
        
        self._print_attempt_score(score, issue_breakdown, len(validation_issues))
        
        # Retry if needed
        for retry_count in range(max_retries):
            if not validation_issues:
                print(f"✅ Perfect allocation found on attempt {retry_count + 1}")
                break
            
            self._print_retry_info(retry_count + 1, validation_issues, issue_breakdown)
            
            print(f"🔄 Requesting corrections (Attempt {retry_count + 2}/{max_retries + 1})...")
            
            # Create correction prompt
            correction_prompt = PromptBuilder.build_correction_prompt(
                allocation_result, validation_issues, 
                order_analysis, driver_analysis,
                self.drivers, self.orders
            )
            
            # Request correction with error handling
            new_allocation, token_usage = self._try_generate_allocation(
                correction_prompt, 
                attempt_num=retry_count + 2
            )
            
            if not new_allocation:
                print(f"⚠️  Attempt {retry_count + 2} failed to generate valid allocation")
                print(f"   Keeping previous best attempt")
                continue
            
            allocation_result = new_allocation
            validation_issues = self.validator.validate(allocation_result)
            score, issue_breakdown = self.calculate_score(validation_issues)
            
            metrics = MetricsCalculator.calculate(allocation_result, self.drivers, self.orders)
            filepath = self.saver.save_attempt(
                retry_count + 2, allocation_result, validation_issues, 
                score, issue_breakdown, metrics
            )
            
            all_attempts.append({
                'attempt_num': retry_count + 2,
                'allocation': allocation_result,
                'validation_issues': validation_issues,
                'score': score,
                'issue_breakdown': issue_breakdown,
                'filepath': filepath
            })
            
            self._print_attempt_score(score, issue_breakdown, len(validation_issues))
        
        # Save token usage
        self._save_token_usage()
        
        # Select best attempt
        if not all_attempts:
            print("❌ No valid attempts generated")
            return self._create_empty_allocation(), ""
        
        best_attempt = self._select_best_attempt(all_attempts)
        
        return best_attempt['allocation'], best_attempt['filepath']
    
    def _try_generate_allocation(self, prompt: str, attempt_num: int) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
        """Try to generate allocation with error handling"""
        try:
            result, token_usage = self.ai_client.generate_allocation(prompt)
            
            # Track token usage
            if token_usage and self.token_tracker:
                self.token_tracker.add_usage(token_usage)
                self._print_token_usage(token_usage, attempt_num)
            
            # Validate that we got a proper structure
            if not isinstance(result, dict):
                print(f"⚠️  Invalid response type: {type(result)}")
                return None, token_usage
            
            if 'allocations' not in result:
                print(f"⚠️  Response missing 'allocations' field")
                result['allocations'] = {}
            
            if 'reasoning' not in result:
                result['reasoning'] = {}
            
            if 'warnings' not in result:
                result['warnings'] = []
            
            return result, token_usage
            
        except Exception as e:
            print(f"❌ Error generating allocation: {e}")
            return None, None
    
    def _print_token_usage(self, token_usage, attempt_num: int):
        """Print token usage for an attempt"""
        from allocator.config import PRICE_PER_1M_INPUT_TOKENS, PRICE_PER_1M_OUTPUT_TOKENS
        
        costs = token_usage.calculate_cost(PRICE_PER_1M_INPUT_TOKENS, PRICE_PER_1M_OUTPUT_TOKENS)
        
        print(f"   🎫 Tokens: {token_usage.total_tokens:,} "
              f"(Input: {token_usage.prompt_tokens:,}, "
              f"Output: {token_usage.completion_tokens:,})")
        print(f"   💵 Cost: ${costs['total_cost']:.4f} "
              f"(Input: ${costs['input_cost']:.4f}, "
              f"Output: ${costs['output_cost']:.4f})")
    
    def _save_token_usage(self):
        """Save token usage to file"""
        if self.token_tracker and len(self.token_tracker.calls) > 0:
            self.token_tracker.save_to_file(TOKEN_USAGE_FILE)
            self._print_total_token_usage()
    
    def _print_total_token_usage(self):
        """Print total token usage summary"""
        if not self.token_tracker:
            return
        
        from allocator.config import PRICE_PER_1M_INPUT_TOKENS, PRICE_PER_1M_OUTPUT_TOKENS
        
        total_usage = self.token_tracker.get_total_usage()
        total_cost = self.token_tracker.get_total_cost(
            PRICE_PER_1M_INPUT_TOKENS, 
            PRICE_PER_1M_OUTPUT_TOKENS
        )
        
        print("\n" + "="*80)
        print("💰 TOTAL TOKEN USAGE")
        print("="*80)
        print(f"   Total API Calls: {total_usage['total_calls']}")
        print(f"   Total Tokens: {total_usage['total_tokens']:,}")
        print(f"   Input Tokens: {total_usage['total_prompt_tokens']:,}")
        print(f"   Output Tokens: {total_usage['total_completion_tokens']:,}")
        print(f"   Total Cost: ${total_cost['total_cost']:.4f}")
        print(f"   Input Cost: ${total_cost['total_input_cost']:.4f}")
        print(f"   Output Cost: ${total_cost['total_output_cost']:.4f}")
        print("="*80)
    
    def _create_empty_allocation(self) -> Dict[str, Any]:
        """Create an empty allocation structure"""
        return {
            "allocations": {},
            "reasoning": {},
            "warnings": ["No allocation could be generated"]
        }
    
    def _select_best_attempt(self, all_attempts: List[Dict]) -> Dict:
        """Select the best attempt from all attempts"""
        print(f"\n🏆 Selecting best attempt from {len(all_attempts)} attempts...")
        
        # Filter to attempts with no critical issues
        critical_free = [
            a for a in all_attempts 
            if a['issue_breakdown']['time_conflicts'] == 0 
            and a['issue_breakdown']['capability_mismatches'] == 0
        ]
        
        if critical_free:
            best_attempt = min(critical_free, key=lambda x: x['score'])
            print(f"   ✅ Found {len(critical_free)} attempt(s) with no critical issues")
        else:
            best_attempt = min(all_attempts, key=lambda x: x['score'])
            print(f"   ⚠️  No attempts without critical issues. Selecting least problematic.")
        
        self._print_best_attempt_info(best_attempt)
        
        return best_attempt
    
    def _print_analysis_summary(self, order_analysis: Dict, driver_analysis: Dict):
        """Print analysis summary"""
        print(f"\n📊 Analysis Summary:")
        print(f"   Wedding Orders (VIP/Wedding/Large Events): {len(order_analysis['wedding_orders'])}")
        print(f"   Wedding-Capable Drivers: {len(driver_analysis['wedding_capable_drivers'])}")
        print(f"   Corporate Orders: {len(order_analysis['corporate_orders'])}")
        print(f"   Corporate-Capable Drivers: {len(driver_analysis['corporate_capable_drivers'])}")
        print(f"   Standard Drivers: {len(driver_analysis['standard_drivers'])}")
        print(f"   Regular Orders: {len(order_analysis['regular_orders'])}")
        print(f"   Total Capacity: {driver_analysis['total_capacity']} orders/day")
        print(f"   Orders by Region: {dict(sorted({k: len(v) for k, v in order_analysis['orders_by_region'].items()}.items()))}")
    
    def _print_attempt_score(self, score: int, issue_breakdown: Dict, total_issues: int):
        """Print attempt score"""
        print(f"   📊 Score: {score} | Issues: {total_issues} "
              f"(TC:{issue_breakdown['time_conflicts']}, "
              f"CM:{issue_breakdown['capability_mismatches']}, "
              f"RW:{issue_breakdown['resource_waste']})")
    
    def _print_retry_info(self, retry_num: int, issues: List[str], breakdown: Dict):
        """Print retry information"""
        print(f"\n⚠️  Found {len(issues)} validation issue(s) on attempt {retry_num}")
        print(f"   - Time conflicts: {breakdown['time_conflicts']}")
        print(f"   - Capability mismatches: {breakdown['capability_mismatches']}")
        print(f"   - Resource waste: {breakdown['resource_waste']}")
    
    def _print_best_attempt_info(self, best_attempt: Dict):
        """Print best attempt information"""
        print(f"   🎯 Best: Attempt {best_attempt['attempt_num']} "
              f"(Score: {best_attempt['score']}, "
              f"Issues: {len(best_attempt['validation_issues'])})")
        print(f"      - Time Conflicts: {best_attempt['issue_breakdown']['time_conflicts']}")
        print(f"      - Capability Mismatches: {best_attempt['issue_breakdown']['capability_mismatches']}")
        print(f"      - Resource Waste: {best_attempt['issue_breakdown']['resource_waste']}")
        print(f"      - Region Mismatches: {best_attempt['issue_breakdown']['region_mismatches']}")
    
    def build_complete_output(self, allocation: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete output with all metadata"""
        allocations_dict = allocation.get('allocations', {})
        reasoning_dict = allocation.get('reasoning', {})
        
        # Create lookup maps
        driver_map = {d.driver_id: d for d in self.drivers}
        order_map = {o.order_id: o for o in self.orders}
        
        # Track allocated orders
        allocated_order_ids = set()
        for order_ids in allocations_dict.values():
            allocated_order_ids.update(order_ids)
        
        # Build complete driver allocations
        complete_allocations = {}
        
        for driver in self.drivers:
            driver_id = driver.driver_id
            assigned_order_ids = allocations_dict.get(driver_id, [])
            
            # Build orders with full metadata and reasoning
            orders_with_metadata = []
            for order_id in assigned_order_ids:
                order = order_map.get(order_id)
                if order:
                    order_data = order.to_dict()
                    order_data['allocation_reasoning'] = reasoning_dict.get(
                        order_id, "No reasoning provided"
                    )
                    orders_with_metadata.append(order_data)
            
            complete_allocations[driver_id] = {
                "driver": driver.to_dict(),
                "assigned_orders": orders_with_metadata,
                "utilization": (len(assigned_order_ids) / driver.max_orders_per_day 
                              if driver.max_orders_per_day > 0 else 0)
            }
        
        # Build unallocated orders list
        unallocated_orders = []
        for order in self.orders:
            if order.order_id not in allocated_order_ids:
                order_data = order.to_dict()
                order_data['unallocated_reason'] = (
                    "No suitable driver available or allocation constraints not met"
                )
                unallocated_orders.append(order_data)
        
        # Build unused drivers list
        unused_drivers = []
        for driver in self.drivers:
            if (driver.driver_id not in allocations_dict or 
                len(allocations_dict[driver.driver_id]) == 0):
                unused_drivers.append(driver.to_dict())
        
        # Calculate metrics
        metrics = MetricsCalculator.calculate(allocation, self.drivers, self.orders)
        
        # Complete output
        return {
            "allocations": complete_allocations,
            "unallocated_orders": unallocated_orders,
            "unused_drivers": unused_drivers,
            "metrics": metrics,
            "warnings": allocation.get('warnings', []),
            "summary": {
                "total_drivers": len(self.drivers),
                "drivers_used": metrics['drivers_used'],
                "drivers_unused": len(unused_drivers),
                "total_orders": len(self.orders),
                "orders_allocated": metrics['total_allocated'],
                "orders_unallocated": metrics['total_unallocated']
            }
        }