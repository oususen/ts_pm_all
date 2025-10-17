# app/domain/models/transport.py
from dataclasses import dataclass
from typing import List, Optional
from datetime import time
from sqlalchemy import Column, Integer, String, Float, Boolean, TIMESTAMP, Time, Computed
from sqlalchemy.orm import declarative_base
import pandas as pd

Base = declarative_base()


class Container(Base):
    """コンテナモデル - SQLAlchemy ORM"""
    __tablename__ = "container_capacity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    width = Column(Integer, nullable=False)   # mm
    depth = Column(Integer, nullable=False)   # mm
    height = Column(Integer, nullable=False)  # mm
    max_weight = Column(Integer, nullable=False, default=0)
    max_volume = Column(Float, Computed("((width * depth * height) / 1000000000.0)", persisted=True))
    can_mix = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default="CURRENT_TIMESTAMP")
    stackable = Column(Boolean, default=False)
    max_stack = Column(Integer, default=1)

    def __repr__(self):
        return f"<Container(id={self.id}, name='{self.name}', size={self.width}x{self.depth}x{self.height}, max_weight={self.max_weight}, max_volume={self.max_volume}, can_mix={self.can_mix})>"


class Truck(Base):
    """トラックモデル - SQLAlchemy ORM"""
    __tablename__ = "truck_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    width = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    max_weight = Column(Integer, default=10000)
    departure_time = Column(Time, nullable=False)
    arrival_time = Column(Time, nullable=False)
    default_use = Column(Boolean, default=False)
    arrival_day_offset = Column(Integer, default=0)
    priority_product_codes = Column(String(255),nullable=True)
    def __repr__(self):
        return f"<Truck(id={self.id}, name='{self.name}', departure={self.departure_time}, arrival={self.arrival_time}, offset={self.arrival_day_offset})>"


@dataclass
class TruckContainerRule:
    """トラックと容器の紐付けルール"""
    truck_id: int
    container_id: int
    id: Optional[int] = None
    max_quantity: Optional[int] = None
    priority: int = 0
    truck_name: Optional[str] = None
    container_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)
    
    def __eq__(self, other):
        if not isinstance(other, TruckContainerRule):
            return False
        return (self.truck_id == other.truck_id and
                self.container_id == other.container_id and
                self.max_quantity == other.max_quantity and
                self.priority == other.priority)
    
    def __hash__(self):
        return hash((self.truck_id, self.container_id, self.max_quantity, self.priority))


@dataclass
class TransportConstraint:
    """輸送制約モデル"""
    product_id: int
    container_id: int
    id: Optional[int] = None
    max_quantity: Optional[int] = None
    created_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)
    
    def __repr__(self):
        return f"<TransportConstraint(id={self.id}, product_id={self.product_id}, container_id={self.container_id}, max_quantity={self.max_quantity})>"
    
    def to_dict(self):
        """辞書に変換"""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "container_id": self.container_id,
            "max_quantity": self.max_quantity,
            "created_at": self.created_at
        }
    
    @staticmethod
    def to_dataframe(constraints: List['TransportConstraint']) -> pd.DataFrame:
        """TransportConstraintのリストをDataFrameに変換"""
        data = [constraint.to_dict() for constraint in constraints]
        return pd.DataFrame(data)
    
    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> List['TransportConstraint']:
        """DataFrameからTransportConstraintのリストを作成"""
        constraints = []
        for _, row in df.iterrows():
            constraint = TransportConstraint.from_dict(row.to_dict())
            constraints.append(constraint)
        return constraints
    
    def __eq__(self, other):
        if not isinstance(other, TransportConstraint):
            return False
        return (self.product_id == other.product_id and
                self.container_id == other.container_id and
                self.max_quantity == other.max_quantity)
    
    def __hash__(self):
        return hash((self.product_id, self.container_id, self.max_quantity))


@dataclass
class LoadingItem:
    """積載アイテム"""
    product_id: int
    container_id: int
    quantity: int
    weight_per_unit: float
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)


@dataclass
class TransportPlan:
    """運送計画モデル"""
    truck: Truck
    loaded_items: List[LoadingItem]
    total_volume: float
    total_weight: float
    volume_utilization: float
    weight_utilization: float
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        return cls(
            truck=data.get('truck'),
            loaded_items=data.get('loaded_items', []),
            total_volume=data.get('total_volume'),
            total_weight=data.get('total_weight'),
            volume_utilization=data.get('volume_utilization'),
            weight_utilization=data.get('weight_utilization')
        )


@dataclass
class LoadingPlan:
    """積載計画モデル"""
    truck_id: int
    container_id: int
    product_id: int
    quantity: int
    total_volume: float
    total_weight: float
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)