from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict, Any
from repository.database_manager import DatabaseManager
from domain.models.transport import Container, Truck, TruckContainerRule , TransportConstraint
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import  text


class TransportRepository:
    """輸送関連データアクセス"""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager


    def get_containers(self):
        """容器一覧取得 - 全カラムを確実に取得"""
        session = self.db_manager.get_session()
        try:
            query = text("""
                SELECT 
                    id, name, width, depth, height, 
                    max_weight, max_volume, can_mix, 
                    stackable, max_stack, created_at
                FROM container_capacity
                ORDER BY id
            """)
            result = session.execute(query)
            rows = result.fetchall()
            
            # 辞書形式で返す（擬似オブジェクト）
            containers = []
            for row in rows:
                # SimpleNamespaceを使って属性アクセス可能にする
                from types import SimpleNamespace
                container = SimpleNamespace(
                    id=row[0],
                    name=row[1],
                    width=row[2],
                    depth=row[3],
                    height=row[4],
                    max_weight=row[5],
                    max_volume=row[6],
                    can_mix=row[7],
                    stackable=bool(row[8]) if row[8] is not None else False,
                    max_stack=row[9] if row[9] is not None else 1,
                    created_at=row[10]
                )
                containers.append(container)
            
            return containers
            
        except Exception as e:
            print(f"Container取得エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            session.close()
   

    def save_container(self, container_data: dict) -> bool:
        session = self.db_manager.get_session()
        try:
            container = Container(**container_data)
            session.add(container)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Container保存エラー: {e}")
            return False
        finally:
            session.close()



    def get_trucks(self) -> pd.DataFrame:
        """トラック一覧取得 - DataFrame で返す"""
        session = self.db_manager.get_session()
        try:
            trucks = session.query(Truck).all()
            return pd.DataFrame([{
                "id": t.id,
                "name": t.name,
                "width": t.width,
                "depth": t.depth,
                "height": t.height,
                "max_weight": t.max_weight,
                "departure_time": t.departure_time,
                "arrival_time": t.arrival_time,
                "default_use": t.default_use,
                "arrival_day_offset": t.arrival_day_offset,
                # 追加：優先積載製品コードを含める
                "priority_product_codes": t.priority_product_codes
            } for t in trucks])
        except SQLAlchemyError as e:
            print(f"truck_masterテーブル取得エラー: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    

    def save_truck(self, truck_data: dict) -> bool:
        """トラック保存 - truck_masterテーブルを使用 (DATETIME対応)"""
        session = self.db_manager.get_session()
        try:
            # departure_time/arrival_time が str や time の場合を吸収して DATETIME にする
            dep_time = truck_data.get("departure_time")
            arr_time = truck_data.get("arrival_time")
            offset   = truck_data.get("arrival_day_offset", 0)

            # time型やstrをdatetimeに変換
            if isinstance(dep_time, str):
                dep_time = datetime.combine(date.today(), datetime.strptime(dep_time, "%H:%M:%S").time())
            elif hasattr(dep_time, "hour"):  # timeオブジェクト
                dep_time = datetime.combine(date.today(), dep_time)

            if isinstance(arr_time, str):
                arr_time = datetime.combine(date.today() + timedelta(days=offset),
                                            datetime.strptime(arr_time, "%H:%M:%S").time())
            elif hasattr(arr_time, "hour"):  # timeオブジェクト
                arr_time = datetime.combine(date.today() + timedelta(days=offset), arr_time)

            truck = Truck(
                name=truck_data["name"],
                width=truck_data["width"],
                depth=truck_data["depth"],
                height=truck_data["height"],
                max_weight=truck_data["max_weight"],
                departure_time=dep_time,
                arrival_time=arr_time,
                default_use=truck_data.get("default_use", False),
                arrival_day_offset=offset,
                # 新規追加：優先積載製品コード
                priority_product_codes=truck_data.get("priority_product_codes")
            )
            session.add(truck)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Truck保存エラー: {e}")
            return False
        finally:
            session.close()
   
    

    def delete_truck(self, truck_id: int) -> bool:
        session = self.db_manager.get_session()
        try:
            truck = session.get(Truck, truck_id)
            if truck:
                session.delete(truck)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Truck削除エラー: {e}")
            return False
        finally:
            session.close()
# app/repository/transport_repository.py の get_truck_container_rules メソッド
    '''トラックと容器はサイズベースで計算するため、ルールは必須ではない
    そのため、ルールが無くてもエラーにしないように修正
    def get_truck_container_rules(self):
        """トラック×容器ルールを取得 - 安全な実装"""
        try:
            query = """
            SELECT 
                id, truck_id, container_id, max_quantity, created_at
            FROM truck_container_rules
            ORDER BY truck_id, container_id
            """
            
            result = self.db.execute_query(query)
            
            if result.empty:
                print("⚠️ 警告: トラック容器ルールが0件")
                return []
            
            # ✅ 単純な辞書のリストとして返す
            rules = []
            for _, row in result.iterrows():
                rules.append({
                    'id': row['id'],
                    'truck_id': row['truck_id'],
                    'container_id': row['container_id'],
                    'max_quantity': row['max_quantity']
                })
            
            print(f"✅ デバッグ: {len(rules)}件のトラック容器ルールを取得")
            return rules
            
        except Exception as e:
            print(f"❌ トラック容器ルール取得エラー: {e}")
            return []  # エラー時は空リストを返す
    '''
    # repository/transport_repository.py の get_truck_container_rules()
    # トラックと容器はサイズベースで計算するため、ルールは必須ではない
    # そのため、ルールが無くてもエラーにしないように修正
    def get_truck_container_rules(self):
        """トラック×容器ルールを取得 - 安全な実装"""
        try:
            query = """
            SELECT 
                id, truck_id, container_id, max_quantity, created_at
            FROM truck_container_rules
            ORDER BY truck_id, container_id
            """
            
            # ✅ 修正
            result = self.db_manager.execute_query(query)
            
            if result.empty:
                print("ℹ️ トラック容器ルールが未設定（サイズベースで計算します）")
                return []
            
            rules = []
            for _, row in result.iterrows():
                rules.append({
                    'id': row['id'],
                    'truck_id': row['truck_id'],
                    'container_id': row['container_id'],
                    'max_quantity': row['max_quantity']
                })
            
            print(f"✅ {len(rules)}件のトラック容器ルールを取得")
            return rules
            
        except Exception as e:
            print(f"⚠️ トラック容器ルール取得エラー（サイズベース計算を使用）: {e}")
            return []
    def save_truck_container_rule(self, rule_data: dict) -> bool:
        session = self.db_manager.get_session()
        try:
            rule = TruckContainerRule(**rule_data)
            session.merge(rule)  # UPSERT 的に扱う
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"TruckContainerRule保存エラー: {e}")
            return False
        finally:
            session.close()

    def get_transport_constraints(self):
        session = self.db_manager.get_session()
        try:
            return session.query(TransportConstraint).order_by(
                TransportConstraint.updated_at.desc()
            ).first()
        except SQLAlchemyError as e:
            print(f"TransportConstraint取得エラー: {e}")
            return None
        finally:
            session.close()

    def save_transport_constraints(self, constraints_data: dict) -> bool:
        session = self.db_manager.get_session()
        try:
            session.query(TransportConstraint).delete()  # 全削除
            constraint = TransportConstraint(**constraints_data)
            session.add(constraint)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"TransportConstraint保存エラー: {e}")
            return False
        finally:
            session.close()
    def delete_container(self, container_id: int) -> bool:
        """容器を削除"""
        session = self.db_manager.get_session()
        try:
            container = session.get(Container, container_id)
            if container:
                session.delete(container)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Container削除エラー: {e}")
            return False
        finally:
            session.close()
    def delete_truck_container_rule(self, rule_id: int) -> bool:
        """トラック容器ルールを削除"""
        session = self.db_manager.get_session()
        try:
            rule = session.get(TruckContainerRule, rule_id)
            if rule:
                session.delete(rule)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"TruckContainerRule削除エラー: {e}")
            return False
        finally:
            session.close()
    def update_container(self, container_id: int, update_data: dict) -> bool:
        """容器を更新"""
        session = self.db_manager.get_session()
        try:
            container = session.get(Container, container_id)
            if container:
                for key, value in update_data.items():
                    setattr(container, key, value)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Container更新エラー: {e}")
            return False
        finally:
            session.close()
    def update_truck(self, truck_id: int, update_data: dict) -> bool:
        """トラックを更新"""
        session = self.db_manager.get_session()
        try:
            truck = session.get(Truck, truck_id)
            if truck:
                for key, value in update_data.items():
                    setattr(truck, key, value)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Truck更新エラー: {e}")
            return False
        finally:
            session.close()
    def update_truck_container_rule(self, rule_id: int, update_data: dict) -> bool:
        """トラック容器ルールを更新"""
        session = self.db_manager.get_session()
        try:
            rule = session.get(TruckContainerRule, rule_id)
            if rule:
                for key, value in update_data.items():
                    setattr(rule, key, value)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"TruckContainerRule更新エラー: {e}")
            return False
        finally:
            session.close()
    def update_transport_constraints(self, update_data: dict) -> bool:
        """輸送制約を更新"""
        session = self.db_manager.get_session()
        try:
            constraint = session.query(TransportConstraint).first()
            if constraint:
                for key, value in update_data.items():
                    setattr(constraint, key, value)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"TransportConstraint更新エラー: {e}")
            return False
        finally:
            session.close()
    def get_container_by_id(self, container_id: int) -> Optional[Container]:
        """IDで容器を取得"""
        session = self.db_manager.get_session()
        try:
            return session.get(Container, container_id)
        except SQLAlchemyError as e:
            print(f"Container取得エラー: {e}")
            return None
        finally:
            session.close()
    def get_truck_by_id(self, truck_id: int) -> Optional[Truck]:
        """IDでトラックを取得"""
        session = self.db_manager.get_session()
        try:
            return session.get(Truck, truck_id)
        except SQLAlchemyError as e:
            print(f"Truck取得エラー: {e}")
            return None
        finally:
            session.close()
    def get_truck_container_rule_by_id(self, rule_id: int) -> Optional[TruckContainerRule]:
        """IDでトラック容器ルールを取得"""
        session = self.db_manager.get_session()
        try:
            return session.get(TruckContainerRule, rule_id)
        except SQLAlchemyError as e:
            print(f"TruckContainerRule取得エラー: {e}")
            return None
        finally:
            session.close()
            