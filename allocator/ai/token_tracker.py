# allocator/ai/token_tracker.py
"""Token usage tracking"""
from typing import Dict, Any, List
from datetime import datetime
import json


class TokenUsage:
    """Represents token usage for a single API call"""
    
    def __init__(self, prompt_tokens: int, completion_tokens: int, 
                 total_tokens: int, model: str, timestamp: str = None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model = model
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'model': self.model,
            'timestamp': self.timestamp
        }
    
    def calculate_cost(self, input_price_per_1m: float, 
                      output_price_per_1m: float) -> Dict[str, float]:
        """Calculate cost based on token usage"""
        input_cost = (self.prompt_tokens / 1_000_000) * input_price_per_1m
        output_cost = (self.completion_tokens / 1_000_000) * output_price_per_1m
        total_cost = input_cost + output_cost
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost
        }


class TokenTracker:
    """Tracks token usage across multiple API calls"""
    
    def __init__(self):
        self.calls: List[TokenUsage] = []
    
    def add_usage(self, usage: TokenUsage):
        """Add a token usage record"""
        self.calls.append(usage)
    
    def get_total_usage(self) -> Dict[str, int]:
        """Get total token usage across all calls"""
        return {
            'total_prompt_tokens': sum(call.prompt_tokens for call in self.calls),
            'total_completion_tokens': sum(call.completion_tokens for call in self.calls),
            'total_tokens': sum(call.total_tokens for call in self.calls),
            'total_calls': len(self.calls)
        }
    
    def get_total_cost(self, input_price_per_1m: float, 
                      output_price_per_1m: float) -> Dict[str, float]:
        """Get total cost across all calls"""
        total_input_cost = 0.0
        total_output_cost = 0.0
        
        for call in self.calls:
            costs = call.calculate_cost(input_price_per_1m, output_price_per_1m)
            total_input_cost += costs['input_cost']
            total_output_cost += costs['output_cost']
        
        return {
            'total_input_cost': total_input_cost,
            'total_output_cost': total_output_cost,
            'total_cost': total_input_cost + total_output_cost
        }
    
    def get_usage_by_attempt(self) -> List[Dict[str, Any]]:
        """Get token usage broken down by attempt"""
        return [
            {
                'attempt': i + 1,
                **call.to_dict(),
                **call.calculate_cost(
                    input_price_per_1m=10.00,
                    output_price_per_1m=30.00
                )
            }
            for i, call in enumerate(self.calls)
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tracker to dictionary"""
        from allocator.config import PRICE_PER_1M_INPUT_TOKENS, PRICE_PER_1M_OUTPUT_TOKENS
        
        total_usage = self.get_total_usage()
        total_cost = self.get_total_cost(
            PRICE_PER_1M_INPUT_TOKENS, 
            PRICE_PER_1M_OUTPUT_TOKENS
        )
        usage_by_attempt = self.get_usage_by_attempt()
        
        return {
            'summary': {
                **total_usage,
                **total_cost,
                'pricing': {
                    'input_price_per_1m_tokens': PRICE_PER_1M_INPUT_TOKENS,
                    'output_price_per_1m_tokens': PRICE_PER_1M_OUTPUT_TOKENS,
                    'currency': 'USD'
                }
            },
            'by_attempt': usage_by_attempt,
            'timestamp': datetime.now().isoformat()
        }
    
    def save_to_file(self, filepath: str):
        """Save token usage to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"\n💰 Token usage saved to {filepath}")