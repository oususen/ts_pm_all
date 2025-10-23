# app/services/production_service.py
from typing import List
from repository.product_repository import ProductRepository
from repository.production_repository import ProductionRepository
from domain.calculators.production_calculator import ProductionCalculator
from domain.models.product import Product, ProductConstraint
from domain.models.production import ProductionInstruction, ProductionPlan
import streamlit as st

class ProductionService:
    """生産関連ビジネスロジック"""
    
    def __init__(self, db_manager):
        self.product_repo = ProductRepository(db_manager)
        self.production_repo = ProductionRepository(db_manager)
        self.calculator = ProductionCalculator()
    
    def get_all_products(self) -> List[Product]:
        """全製品取得 - 安全なモデル変換"""
        try:
            df = self.product_repo.get_all_products()
            products = []
            for _, row in df.iterrows():
                try:
                    product = Product.from_dict(row.to_dict())
                    products.append(product)
                except Exception as e:
                    print(f"製品データ変換エラー: {e}")
                    continue
            return products
        except Exception as e:
            st.error(f"製品データ取得エラー: {e}")
            return []
    
    def get_production_instructions(self, start_date=None, end_date=None) -> List[ProductionInstruction]:
        """生産指示取得 - 安全なモデル変換"""
        try:
            df = self.production_repo.get_production_instructions(start_date, end_date)
            instructions = []
            for _, row in df.iterrows():
                try:
                    instruction = ProductionInstruction.from_dict(row.to_dict())
                    instructions.append(instruction)
                except Exception as e:
                    print(f"生産指示データ変換エラー: {e}")
                    continue
            return instructions
        except Exception as e:
            st.error(f"生産指示データ取得エラー: {e}")
            return []
    
    def get_product_constraints(self) -> List[ProductConstraint]:
        """製品制約取得 - 安全なモデル変換"""
        try:
            df = self.product_repo.get_product_constraints()
            constraints = []
            for _, row in df.iterrows():
                try:
                    constraint = ProductConstraint.from_dict(row.to_dict())
                    constraints.append(constraint)
                except Exception as e:
                    print(f"制約データ変換エラー: {e}")
                    continue
            return constraints
        except Exception as e:
            st.error(f"制約データ取得エラー: {e}")
            return []
    
    def calculate_production_plan(self, start_date, end_date) -> List[ProductionPlan]:
        """生産計画計算"""
        try:
            instructions = self.get_production_instructions(start_date, end_date)
            constraints = self.get_product_constraints()
            
            if not instructions:
                st.warning("生産指示データがありません")
                return []
                
            return self.calculator.calculate_production_plan(instructions, constraints)
        except Exception as e:
            st.error(f"生産計画計算エラー: {e}")
            return []
    
    def save_product_constraints(self, constraints_df) -> bool:
        """製品制約保存"""
        try:
            return self.product_repo.save_product_constraints(constraints_df)
        except Exception as e:
            st.error(f"制約保存エラー: {e}")
            return False
    def create_production(self, plan_data: dict) -> bool:
        """生産計画を新規登録"""
        return self.production_repo.create_production(plan_data)
    def get_productions(self) -> List[ProductionInstruction]:
        """登録済み生産計画を取得"""
        try:
            df = self.production_repo.get_productions()
            productions = []
            for _, row in df.iterrows():
                try:
                    production = ProductionInstruction.from_dict(row.to_dict())
                    productions.append(production)
                except Exception as e:
                    print(f"生産計画データ変換エラー: {e}")
                    continue
            return productions
        except Exception as e:
            st.error(f"生産計画データ取得エラー: {e}")
            return []
    def update_production(self, plan_id: int, update_data: dict) -> bool:
        """生産計画を更新"""
        return self.production_repo.update_production(plan_id, update_data) or False
    def delete_production(self, plan_id: int) -> bool:
        """生産計画を削除"""
        return self.production_repo.delete_production(plan_id) or False
    
    def create_product(self, product_data: dict) -> bool:
        """製品を新規登録"""
        return self.product_repo.create_product(product_data) or False      
    def update_product(self, product_id: int, update_data: dict) -> bool:
        """製品を更新"""
        return self.product_repo.update_product(product_id, update_data) or False
    def delete_product(self, product_id: int) -> bool:
        """製品を削除"""
        return self.product_repo.delete_product(product_id) or False

    def get_product_groups(self):
        """製品群一覧を取得"""
        return self.product_repo.get_product_groups()
