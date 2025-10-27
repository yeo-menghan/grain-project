# allocator/io/saver.py
"""Data saving functionality"""
import json
import os
from typing import Dict, Any, List
from datetime import datetime
from allocator.config import ATTEMPTS_DIR
from allocator.utils import ensure_directory, format_timestamp


class ResultSaver:
    """Handles saving of allocation results"""
    
    def __init__(self, attempts_dir: str = ATTEMPTS_DIR):
        self.attempts_dir = attempts_dir
        ensure_directory(self.attempts_dir)
    
    def save_attempt(self, attempt_num: int, allocation: Dict[str, Any],
                    validation_issues: List[str], score: int,
                    issue_breakdown: Dict[str, int],
                    actual_metrics: Dict[str, Any]) -> str:
        """Save an allocation attempt to file"""
        timestamp = format_timestamp()
        filename = f'attempt_{attempt_num:02d}_{timestamp}_score_{score}.json'
        filepath = os.path.join(self.attempts_dir, filename)
        
        attempt_data = {
            'attempt_number': attempt_num,
            'timestamp': timestamp,
            'score': score,
            'issue_breakdown': issue_breakdown,
            'total_issues': len(validation_issues),
            'validation_issues': validation_issues,
            'allocation': allocation,
            'actual_metrics': actual_metrics
        }
        
        with open(filepath, 'w') as f:
            json.dump(attempt_data, f, indent=2)
        
        print(f"   💾 Saved attempt {attempt_num} to {filename}")
        return filepath
    
    def save_final_results(self, complete_output: Dict[str, Any], 
                          output_file: str) -> None:
        """Save final allocation results to file"""
        with open(output_file, 'w') as f:
            json.dump(complete_output, f, indent=2)
        print(f"\n💾 Final results saved to {output_file}")