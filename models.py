import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class FundObj:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    obj_type: str = ''
    name: str = ''
    data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        d = d.copy()
        try:
            d['created_at'] = datetime.fromisoformat(d['created_at'])
        except (ValueError, TypeError):
            d['created_at'] = datetime.now()
        
        try:
            d['updated_at'] = datetime.fromisoformat(d['updated_at'])
        except (ValueError, TypeError):
            d['updated_at'] = datetime.now()
            
        return cls(**d)
