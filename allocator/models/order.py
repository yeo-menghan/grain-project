# allocator/models/order.py
"""Order model"""
from datetime import datetime
from typing import List, Dict, Any


class Order:
    """Represents a delivery order"""
    
    def __init__(self, data: Dict[str, Any]):
        self.order_id: str = data['order_id']
        self.region: str = data.get('region', '')
        self.pickup_time: datetime = datetime.fromisoformat(data['pickup_time'])
        self.teardown_time: datetime = datetime.fromisoformat(data['teardown_time'])
        self.pax_count: int = data.get('pax_count', 0)
        self.tags: List[str] = data.get('tags', [])
        self._raw_data = data
    
    @property
    def is_wedding_order(self) -> bool:
        """Check if this is a wedding order"""
        from allocator.utils import has_wedding_capability
        return has_wedding_capability(self.tags, tags=self.tags)
    
    @property
    def is_corporate_order(self) -> bool:
        """Check if this is a corporate order"""
        from allocator.utils import has_corporate_capability
        return has_corporate_capability(self.tags, tags=self.tags)
    
    def conflicts_with(self, other: 'Order') -> bool:
        """Check if this order has time conflict with another order"""
        return not (self.teardown_time <= other.pickup_time or 
                   other.teardown_time <= self.pickup_time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._raw_data.copy()
    
    def __repr__(self) -> str:
        return f"Order({self.order_id}, {self.region}, {self.pickup_time})"