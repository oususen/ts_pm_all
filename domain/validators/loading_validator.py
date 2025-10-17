# app/domain/validators/loading_validator.py
from typing import List, Tuple
from ..models.transport import Container, Truck, LoadingItem

class LoadingValidator:
    """積載バリデータ"""
    
    def validate_loading(self, 
                        items: List[LoadingItem],
                        containers: List[Container],
                        truck: Truck) -> Tuple[bool, List[str]]:
        """積載バリデーション"""
        errors = []
        
        total_volume = 0
        total_weight = 0
        truck_volume = truck.width * truck.depth * truck.height
        
        for item in items:
            container = next((c for c in containers if c.id == item.container_id), None)
            if not container:
                errors.append(f"容器ID {item.container_id} が見つかりません")
                continue
            
            # 容器がトラックに収まるかチェック
            if not self._check_container_fit(container, truck):
                errors.append(f"容器 {container.name} がトラックに収まりません")
            
            item_volume = container.width * container.depth * container.height * item.quantity
            item_weight = item.weight_per_unit * item.quantity
            
            total_volume += item_volume
            total_weight += item_weight
        
        # 総体積チェック
        if total_volume > truck_volume:
            errors.append(f"総体積超過: {total_volume/1000000:.2f}m³ > {truck_volume/1000000:.2f}m³")
        
        # 総重量チェック
        if total_weight > truck.max_weight:
            errors.append(f"総重量超過: {total_weight}kg > {truck.max_weight}kg")
        
        return len(errors) == 0, errors
    
    def _check_container_fit(self, container: Container, truck: Truck) -> bool:
        """容器収容チェック"""
        return (container.width <= truck.width and 
                container.depth <= truck.depth and 
                container.height <= truck.height)