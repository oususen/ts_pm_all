"""
マイグレーション: planned_shipmentsテーブル追加

各計画の出荷予定を個別に保存するテーブル
"""

import sqlite3
from datetime import datetime

def migrate():
    """マイグレーション実行"""
    conn = sqlite3.connect('transport_management.db')
    cursor = conn.cursor()
    
    try:
        # planned_shipmentsテーブル作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planned_shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loading_plan_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                delivery_date DATE NOT NULL,
                loading_date DATE NOT NULL,
                planned_quantity INTEGER NOT NULL,
                num_containers INTEGER NOT NULL,
                truck_id INTEGER,
                truck_name TEXT,
                container_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (loading_plan_id) REFERENCES loading_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        
        # インデックス作成
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_planned_shipments_plan 
            ON planned_shipments(loading_plan_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_planned_shipments_product 
            ON planned_shipments(product_id, delivery_date)
        ''')
        
        conn.commit()
        print("✅ planned_shipmentsテーブルを作成しました")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ マイグレーションエラー: {e}")
        raise
    
    finally:
        conn.close()

def rollback():
    """ロールバック"""
    conn = sqlite3.connect('transport_management.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('DROP TABLE IF EXISTS planned_shipments')
        conn.commit()
        print("✅ planned_shipmentsテーブルを削除しました")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ ロールバックエラー: {e}")
        raise
    
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        migrate()
