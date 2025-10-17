# app/domain/models/production.py
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class ProductionInstruction:
    """生産指示モデル - production_instructions_detailテーブル構造に合わせる"""
    id: int
    product_id: Optional[int] = None
    record_type: Optional[str] = None
    start_month: Optional[str] = None
    total_first_month: Optional[int] = None
    total_next_month: Optional[int] = None
    total_next_next_month: Optional[int] = None
    instruction_date: Optional[date] = None
    instruction_quantity: Optional[int] = None
    inspection_category: Optional[str] = None
    month_type: Optional[str] = None
    day_number: Optional[int] = None
    created_at: Optional[str] = None
    # 結合用フィールド
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)


@dataclass
class ProductionPlan:
    """生産計画モデル"""
    date: date
    product_id: int
    product_code: str
    product_name: str
    demand_quantity: float
    planned_quantity: float
    inspection_category: str
    is_constrained: bool
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)


@dataclass
class ProductionConstraint:
    """生産制約モデル - production_constraintsテーブル構造に合わせる"""
    product_id: int
    id: Optional[int] = None
    daily_capacity: Optional[int] = None
    smoothing_level: Optional[float] = None
    volume_per_unit: Optional[float] = None
    is_transport_constrained: Optional[bool] = None
    created_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)
    
    def __eq__(self, other):
        if not isinstance(other, ProductionConstraint):
            return False
        return (self.product_id == other.product_id and
                self.daily_capacity == other.daily_capacity and
                self.smoothing_level == other.smoothing_level and
                self.volume_per_unit == other.volume_per_unit and
                self.is_transport_constrained == other.is_transport_constrained)
    
    def __hash__(self):
        return hash((self.product_id, self.daily_capacity, self.smoothing_level,
                     self.volume_per_unit, self.is_transport_constrained))