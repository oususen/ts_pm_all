# app/repository/delivery_progress_repository.py
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import date, datetime, time
import pandas as pd
from .database_manager import DatabaseManager


class DeliveryProgressRepository:
    """納入進度データアクセス"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_delivery_progress(self, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """
        納入進度データ取得
        
        Args:
            start_date: 開始日
            end_date: 終了日
        
        Returns:
            pd.DataFrame: 納入進度データ
        """
        session = self.db.get_session()
        
        try:
            if start_date and end_date:
                query = text("""
                    SELECT 
                        dp.id,
                        dp.order_id,
                        dp.product_id,
                        p.product_code,
                        p.product_name,
                        p.used_container_id,
                        p.used_truck_ids,
                        p.capacity,
                        p.can_advance,
                        dp.order_date,
                        dp.delivery_date,
                        dp.order_quantity,
                        dp.planned_quantity,
                        dp.shipped_quantity,
                        dp.planned_progress_quantity,
                        dp.remaining_quantity,
                        dp.manual_planning_quantity,
                        dp.status,
                        dp.customer_code,
                        dp.customer_name,
                        dp.delivery_location,
                        dp.priority
                    FROM delivery_progress dp
                    LEFT JOIN products p ON dp.product_id = p.id
                    WHERE dp.delivery_date BETWEEN :start_date AND :end_date
                    AND dp.status != 'キャンセル'
                    ORDER BY dp.delivery_date, dp.priority
                """)
                result = session.execute(query, {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                })
            else:
                query = text("""
                    SELECT 
                        dp.id,
                        dp.order_id,
                        dp.product_id,
                        p.product_code,
                        p.product_name,
                        p.used_container_id,
                        p.used_truck_ids,
                        p.capacity,
                        p.can_advance,
                        dp.order_date,
                        dp.delivery_date,
                        dp.order_quantity,
                        dp.planned_quantity,
                        dp.shipped_quantity,
                        dp.planned_progress_quantity,
                        dp.remaining_quantity,
                        dp.manual_planning_quantity,
                        dp.status,
                        dp.customer_code,
                        dp.customer_name,
                        dp.delivery_location,
                        dp.priority
                    FROM delivery_progress dp
                    LEFT JOIN products p ON dp.product_id = p.id
                    WHERE dp.status != 'キャンセル'
                    ORDER BY dp.delivery_date, dp.priority
                """)
                result = session.execute(query)
            
            rows = result.fetchall()
            
            if rows:
                columns = result.keys()
                df = pd.DataFrame(rows, columns=columns)
                
                # 日付型に変換
                if 'delivery_date' in df.columns:
                    df['delivery_date'] = pd.to_datetime(df['delivery_date']).dt.date
                if 'order_date' in df.columns:
                    df['order_date'] = pd.to_datetime(df['order_date']).dt.date
                
                return df
            else:
                return pd.DataFrame()
                
        except SQLAlchemyError as e:
            print(f"納入進度取得エラー: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def get_progress_by_product_and_date(self, product_id: int, delivery_date: date) -> Optional[Dict[str, Any]]:
        """製品と納期日で納入進度を1件取得"""
        session = self.db.get_session()

        try:
            query = text("""
                SELECT *
                FROM delivery_progress
                WHERE product_id = :product_id
                  AND DATE(delivery_date) = :delivery_date
                ORDER BY delivery_date, id
                LIMIT 1
            """)

            result = session.execute(query, {
                'product_id': product_id,
                'delivery_date': delivery_date
            }).fetchone()

            if result:
                return dict(result._mapping)
            return None

        except SQLAlchemyError as e:
            print(f"delivery_progress取得エラー: {e}")
            return None
        finally:
            session.close()
    
    def create_shipment_record(self, shipment_data: Dict[str, Any]) -> bool:
        """
        出荷実績を登録
        
        Args:
            shipment_data: 出荷データ
        
        Returns:
            bool: 成功した場合True
        """
        session = self.db.get_session()
        
        try:
            query = text("""
                INSERT INTO shipment_records
                (progress_id, truck_id, shipment_date, shipped_quantity, 
                container_id, num_containers, actual_departure_time, actual_arrival_time, 
                driver_name, notes)
                VALUES 
                (:progress_id, :truck_id, :shipment_date, :shipped_quantity,
                :container_id, :num_containers, :actual_departure_time, :actual_arrival_time,
                :driver_name, :notes)
            """)
            
            # TIME型をDATETIME型に変換
            departure_datetime = None
            arrival_datetime = None
            
            if shipment_data.get('actual_departure_time'):
                if isinstance(shipment_data['actual_departure_time'], time):
                    # date + timeをdatetimeに結合
                    departure_datetime = datetime.combine(
                        shipment_data['shipment_date'],
                        shipment_data['actual_departure_time']
                    )
                else:
                    departure_datetime = shipment_data['actual_departure_time']
            
            if shipment_data.get('actual_arrival_time'):
                if isinstance(shipment_data['actual_arrival_time'], time):
                    arrival_datetime = datetime.combine(
                        shipment_data['shipment_date'],
                        shipment_data['actual_arrival_time']
                    )
                else:
                    arrival_datetime = shipment_data['actual_arrival_time']
            
            params = {
                'progress_id': shipment_data['progress_id'],
                'truck_id': shipment_data['truck_id'],
                'shipment_date': shipment_data['shipment_date'],
                'shipped_quantity': shipment_data['shipped_quantity'],
                'container_id': shipment_data.get('container_id'),
                'num_containers': shipment_data.get('num_containers'),
                'actual_departure_time': departure_datetime,
                'actual_arrival_time': arrival_datetime,
                'driver_name': shipment_data.get('driver_name', ''),
                'notes': shipment_data.get('notes', '')
            }
            
            session.execute(query, params)
            
            # 納入進度の出荷済み数量を更新（remaining_quantityを除外）
            update_query = text("""
                UPDATE delivery_progress 
                SET shipped_quantity = shipped_quantity + :shipped_quantity,
                    status = CASE 
                        WHEN shipped_quantity + :shipped_quantity >= order_quantity THEN '出荷完了'
                        WHEN shipped_quantity + :shipped_quantity > 0 THEN '一部出荷'
                        ELSE status
                    END
                WHERE id = :progress_id
            """)
            
            session.execute(update_query, {
                'progress_id': shipment_data['progress_id'],
                'shipped_quantity': shipment_data['shipped_quantity']
            })
            
            session.commit()
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"出荷実績登録エラー: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            session.close()
    
    def get_shipment_records(self, progress_id: int = None) -> pd.DataFrame:
        """
        出荷実績を取得
        
        Args:
            progress_id: 進度ID(指定した場合はその進度の実績のみ)
        
        Returns:
            pd.DataFrame: 出荷実績データ
        """
        session = self.db.get_session()
        
        try:
            if progress_id:
                query = text("""
                    SELECT 
                        sr.*,
                        dp.order_id,
                        dp.product_id,
                        p.product_code,
                        p.product_name,
                        t.name as truck_name
                    FROM shipment_records sr
                    LEFT JOIN delivery_progress dp ON sr.progress_id = dp.id
                    LEFT JOIN products p ON dp.product_id = p.id
                    LEFT JOIN truck_master t ON sr.truck_id = t.id
                    WHERE sr.progress_id = :progress_id
                    ORDER BY sr.shipment_date DESC
                """)
                result = session.execute(query, {'progress_id': progress_id})
            else:
                query = text("""
                    SELECT 
                        sr.*,
                        dp.order_id,
                        dp.product_id,
                        p.product_code,
                        p.product_name,
                        t.name as truck_name
                    FROM shipment_records sr
                    LEFT JOIN delivery_progress dp ON sr.progress_id = dp.id
                    LEFT JOIN products p ON dp.product_id = p.id
                    LEFT JOIN truck_master t ON sr.truck_id = t.id
                    ORDER BY sr.shipment_date DESC
                """)
                result = session.execute(query)
            
            rows = result.fetchall()
            
            if rows:
                columns = result.keys()
                return pd.DataFrame(rows, columns=columns)
            else:
                return pd.DataFrame()
                
        except SQLAlchemyError as e:
            print(f"出荷実績取得エラー: {e}")
            return pd.DataFrame()
        finally:
            session.close()
    
    def update_delivery_progress(self, progress_id: int, update_data: Dict[str, Any]) -> bool:
        """
        納入進度を更新
        
        Args:
            progress_id: 進度ID
            update_data: 更新データ
        
        Returns:
            bool: 成功した場合True
        """
        session = self.db.get_session()
        
        try:
            # 動的にUPDATE文を構築
            set_clauses = []
            params = {'progress_id': progress_id}
            
            for key, value in update_data.items():
                set_clauses.append(f"{key} = :{key}")
                params[key] = value
            
            query = text(f"""
                UPDATE delivery_progress
                SET {', '.join(set_clauses)}
                WHERE id = :progress_id
            """)
            
            session.execute(query, params)
            session.commit()
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"納入進度更新エラー: {e}")
            return False
        finally:
            session.close()
    
    def create_delivery_progress(self, progress_data: Dict[str, Any]) -> int:
        """
        納入進度を新規作成
        
        Args:
            progress_data: 進度データ
        
        Returns:
            int: 作成された進度ID(失敗時は0)
        """
        session = self.db.get_session()
        
        try:
            progress_data = dict(progress_data)
            progress_data.setdefault('manual_planning_quantity', None)
            query = text("""
                INSERT INTO delivery_progress
                (order_id, product_id, order_date, delivery_date, order_quantity,
                 customer_code, customer_name, delivery_location, priority, notes, manual_planning_quantity)
                VALUES
                (:order_id, :product_id, :order_date, :delivery_date, :order_quantity,
                 :customer_code, :customer_name, :delivery_location, :priority, :notes, :manual_planning_quantity)
            """)
            
            result = session.execute(query, progress_data)
            session.commit()
            
            return result.lastrowid
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"納入進度作成エラー: {e}")
            return 0
        finally:
            session.close()
    
    def delete_delivery_progress(self, progress_id: int) -> bool:
        """
        納入進度を削除
        
        Args:
            progress_id: 進度ID
        
        Returns:
            bool: 成功した場合True
        """
        session = self.db.get_session()
        
        try:
            query = text("""
                DELETE FROM delivery_progress WHERE id = :progress_id
            """)
            
            session.execute(query, {'progress_id': progress_id})
            session.commit()
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"納入進度削除エラー: {e}")
            return False
        finally:
            session.close()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """
        納入進度サマリーを取得
        
        Returns:
            Dict: サマリー情報
        """
        session = self.db.get_session()
        
        try:
            # delayedをdelayed_countに変更（予約語回避）
            query = text("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = '未出荷' THEN 1 ELSE 0 END) as unshipped,
                    SUM(CASE WHEN status = '一部出荷' THEN 1 ELSE 0 END) as partial,
                    SUM(CASE WHEN status = '出荷完了' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN DATEDIFF(delivery_date, CURDATE()) < 0 AND status != '出荷完了' THEN 1 ELSE 0 END) as delayed_count,
                    SUM(CASE WHEN DATEDIFF(delivery_date, CURDATE()) BETWEEN 0 AND 3 AND status != '出荷完了' THEN 1 ELSE 0 END) as urgent,
                    SUM(order_quantity) as total_quantity,
                    SUM(shipped_quantity) as total_shipped,
                    SUM(remaining_quantity) as total_remaining
                FROM delivery_progress
                WHERE status != 'キャンセル'
            """)
            
            result = session.execute(query).fetchone()
            
            return {
                'total_orders': result[0] or 0,
                'unshipped': result[1] or 0,
                'partial': result[2] or 0,
                'completed': result[3] or 0,
                'delayed': result[4] or 0,
                'urgent': result[5] or 0,
                'total_quantity': result[6] or 0,
                'total_shipped': result[7] or 0,
                'total_remaining': result[8] or 0
            }
            
        except SQLAlchemyError as e:
            print(f"サマリー取得エラー: {e}")
            return {}
        finally:
            session.close()
