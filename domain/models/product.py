# app/domain/models/product.py
from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class Product:
    """製品モデル - 実際のproductsテーブル構造に完全対応"""
    id: int
    #data_no: Optional[int] = None
    # factory: Optional[str] = None
    # client_code: Optional[int] = None
    # calculation_date: Optional[date] = None
    # production_complete_date: Optional[date] = None
    # modified_factory: Optional[str] = None
    # product_category: Optional[str] = None
    product_code: Optional[str] = None
    # ac_code: Optional[str] = None
    # processing_content: Optional[str] = None
    product_name: Optional[str] = None
    delivery_location: Optional[str] = None
    box_type: Optional[str] = None
    capacity: Optional[int] = None
    # grouping_category: Optional[str] = None
    # form_category: Optional[str] = None
    inspection_category: Optional[str] = None
    # ordering_category: Optional[str] = None
    # regular_replenishment_category: Optional[str] = None
    # lead_time: Optional[int] = None
    # fixed_point_days: Optional[int] = None
    # shipping_factory: Optional[str] = None
    # client_product_code: Optional[str] = None
    # purchasing_org: Optional[str] = None
    # item_group: Optional[str] = None
    # processing_type: Optional[str] = None
    # inventory_transfer_category: Optional[str] = None
    # created_at: Optional[str] = None
    container_width: Optional[int] = None
    container_depth: Optional[int] = None
    container_height: Optional[int] = None
    stackable: Optional[bool] = True
    used_container_id: Optional[int] = None  # 使用容器ID
    used_truck_ids: Optional[str] = None  # 使用トラックID（カンマ区切り）
    can_advance: Optional[bool] = False  # 前倒し可能フラグ（追加予定）
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成(余分なキーを無視)"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                # tinyint(1)をboolに変換
                if field_name in ['stackable', 'can_advance'] and isinstance(data[field_name], int):
                    valid_fields[field_name] = bool(data[field_name])
                else:
                    valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)


@dataclass
class ProductConstraint:
    """製品制約モデル - production_constraintsテーブル構造に完全対応"""
    product_id: int
    id: Optional[int] = None
    daily_capacity: int = 1000
    smoothing_level: float = 0.70
    volume_per_unit: float = 1.00
    is_transport_constrained: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # 結合用フィールド
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                # tinyint(1)をboolに変換
                if field_name == 'is_transport_constrained' and isinstance(data[field_name], int):
                    valid_fields[field_name] = bool(data[field_name])
                else:
                    valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)


@dataclass
class ProductContainerMapping:
    """製品×容器紐付けモデル - product_container_mappingテーブル（新規作成予定）"""
    product_id: int
    container_id: int
    id: Optional[int] = None
    max_quantity: int = 100
    is_primary: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # 結合用フィールド
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    container_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """辞書からモデルを作成"""
        valid_fields = {}
        for field_name in cls.__annotations__.keys():
            if field_name in data and data[field_name] is not None:
                if field_name == 'is_primary' and isinstance(data[field_name], int):
                    valid_fields[field_name] = bool(data[field_name])
                else:
                    valid_fields[field_name] = data[field_name]
        return cls(**valid_fields)