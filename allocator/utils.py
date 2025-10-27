# allocator/utils.py
"""Utility functions"""
import os
from datetime import datetime
from typing import List, Dict, Any


def ensure_directory(path: str) -> None:
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)


def categorize_validation_issues(issues: List[str]) -> Dict[str, int]:
    """Categorize and count validation issues"""
    categories = {
        'time_conflicts': 0,
        'capability_mismatches': 0,
        'capacity_violations': 0,
        'resource_waste': 0,
        'region_mismatches': 0,
        'other': 0
    }
    
    for issue in issues:
        if 'TIME CONFLICT' in issue:
            categories['time_conflicts'] += 1
        elif 'lacks' in issue and 'capability' in issue:
            categories['capability_mismatches'] += 1
        elif 'CAPACITY' in issue:
            categories['capacity_violations'] += 1
        elif 'RESOURCE WASTE' in issue:
            categories['resource_waste'] += 1
        elif 'REGION' in issue:
            categories['region_mismatches'] += 1
        else:
            categories['other'] += 1
    
    return categories


def format_timestamp(dt: datetime = None) -> str:
    """Format timestamp for filenames"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y%m%d_%H%M%S')


def has_wedding_capability(capabilities: List[str], tags: List[str] = None) -> bool:
    """Check if capabilities/tags include wedding capability"""
    from allocator.config import WEDDING_CAPABILITIES
    items = capabilities if tags is None else tags
    return any(item in WEDDING_CAPABILITIES for item in items)


def has_corporate_capability(capabilities: List[str], tags: List[str] = None) -> bool:
    """Check if capabilities/tags include corporate capability"""
    from allocator.config import CORPORATE_CAPABILITIES
    items = capabilities if tags is None else tags
    return any(item in CORPORATE_CAPABILITIES for item in items)