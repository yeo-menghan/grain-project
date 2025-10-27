# allocator/models/driver.py
"""Driver model"""
from typing import List, Dict, Any


class Driver:
    """Represents a delivery driver"""
    
    def __init__(self, data: Dict[str, Any]):
        self.driver_id: str = data['driver_id']
        self.name: str = data.get('name', 'Unknown')
        self.preferred_region: str = data.get('preferred_region', '')
        self.max_orders_per_day: int = data.get('max_orders_per_day', 0)
        self.capabilities: List[str] = data.get('capabilities', [])
        self._raw_data = data
    
    @property
    def is_wedding_capable(self) -> bool:
        """Check if driver can handle wedding orders"""
        from allocator.utils import has_wedding_capability
        return has_wedding_capability(self.capabilities)
    
    @property
    def is_corporate_capable(self) -> bool:
        """Check if driver can handle corporate orders"""
        from allocator.utils import has_corporate_capability
        return has_corporate_capability(self.capabilities)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._raw_data.copy()
    
    def __repr__(self) -> str:
        return f"Driver({self.driver_id}, {self.name}, {self.preferred_region})"