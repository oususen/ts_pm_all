# app/repository/production_repository.py
from .database_manager import DatabaseManager
import pandas as pd
from datetime import date

class ProductionRepository:
    """生産関連データアクセス"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_production_instructions(self, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """生産指示データ取得 - 完全修正版"""
        try:
            # パラメータを文字列に変換（SQLインジェクション注意）
            if start_date and end_date:
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                
                query = f"""
                SELECT 
                    pid.id,
                    pid.product_id,
                    pid.instruction_date,
                    pid.instruction_quantity,
                    pid.inspection_category,
                    p.product_code,
                    p.product_name
                FROM production_instructions_detail pid
                LEFT JOIN products p ON pid.product_id = p.id
                WHERE pid.instruction_quantity IS NOT NULL 
                AND pid.instruction_quantity > 0
                AND pid.instruction_date BETWEEN '{start_str}' AND '{end_str}'
                ORDER BY pid.instruction_date
                """
            else:
                query = """
                SELECT 
                    pid.id,
                    pid.product_id,
                    pid.instruction_date,
                    pid.instruction_quantity,
                    pid.inspection_category,
                    p.product_code,
                    p.product_name
                FROM production_instructions_detail pid
                LEFT JOIN products p ON pid.product_id = p.id
                WHERE pid.instruction_quantity IS NOT NULL 
                AND pid.instruction_quantity > 0
                ORDER BY pid.instruction_date
                """
            
            # パラメータなしで実行
            result = self.db.execute_query(query)
            
            # DataFrameに変換（安全なチェック）
            if result is None:
                return pd.DataFrame()
            
            if isinstance(result, pd.DataFrame):
                # 既にDataFrameの場合
                df = result
            elif isinstance(result, list) and len(result) > 0:
                # リストの場合
                df = pd.DataFrame(result)
            else:
                # 空の場合
                return pd.DataFrame()
            
            # 空チェック
            if df.empty:
                return df
            
            # 日付型に変換
            if 'instruction_date' in df.columns:
                df['instruction_date'] = pd.to_datetime(df['instruction_date']).dt.date
            
            return df
                
        except Exception as e:
            print(f"❌ オーダーデータ取得エラー: {e}")
            return pd.DataFrame()