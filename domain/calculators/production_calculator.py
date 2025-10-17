# app/domain/calculators/production_calculator.py
from typing import List
from ..models.production import ProductionInstruction, ProductionPlan
from ..models.product import ProductConstraint

class ProductionCalculator:
    """生産計画計算機"""
    
    def calculate_production_plan(self, 
                                instructions: List[ProductionInstruction],
                                constraints: List[ProductConstraint]) -> List[ProductionPlan]:
        """生産計画計算"""
        
        plans = []
        
        for instruction in instructions:
            # 該当製品の制約を検索
            constraint = next(
                (c for c in constraints if c.product_id == instruction.product_id), 
                None
            )
            
            if constraint:
                planned_quantity = self._calculate_smoothed_production(
                    instruction.instruction_quantity,
                    constraint.smoothing_level,
                    constraint.daily_capacity
                )
                is_constrained = True
            else:
                planned_quantity = instruction.instruction_quantity
                is_constrained = False
            
            plan = ProductionPlan(
                date=instruction.instruction_date,
                product_id=instruction.product_id,
                product_code=instruction.product_code,
                product_name=instruction.product_name,
                demand_quantity=instruction.instruction_quantity,
                planned_quantity=planned_quantity,
                inspection_category=instruction.inspection_category,
                is_constrained=is_constrained
            )
            plans.append(plan)
        
        return plans
    
    def _calculate_smoothed_production(self, demand: float, smoothing_level: float, daily_capacity: float) -> float:
        """平均化生産量計算"""
        smoothed = demand * smoothing_level
        return min(smoothed, daily_capacity)