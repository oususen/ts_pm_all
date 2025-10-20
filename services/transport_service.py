# app/services/transport_service.py（カレンダー統合版）
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from repository.transport_repository import TransportRepository
from repository.production_repository import ProductionRepository
from repository.product_repository import ProductRepository
from repository.loading_plan_repository import LoadingPlanRepository
from repository.delivery_progress_repository import DeliveryProgressRepository
from repository.calendar_repository import CalendarRepository  # ✅ 追加
from domain.calculators.transport_planner import TransportPlanner
from domain.validators.loading_validator import LoadingValidator
from domain.models.transport import LoadingItem
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
from sqlalchemy import text
import math

class TransportService:
    """運送関連ビジネスロジック（カレンダー統合版）"""
    
    EDITABLE_COLUMN_ORDER = [
        'edit_key',
        'loading_date',
        'truck_name',
        'truck_id',
        'trip_number',
        'product_code',
        'product_name',
        'product_id',
        'container_id',
        'num_containers',
        'total_quantity',
        'delivery_date',
        'original_num_containers',
        'original_total_quantity',
        'original_delivery_date',
        'capacity_per_container',
        'surplus',
        'notes'
    ]

    EDITABLE_COLUMN_LABELS = {
        'edit_key': '編集キー',
        'loading_date': '積込日',
        'truck_name': 'トラック名',
        'truck_id': 'トラックID',
        'trip_number': '便番号',
        'product_code': '製品コード',
        'product_name': '製品名',
        'product_id': '製品ID',
        'container_id': 'コンテナID',
        'num_containers': 'コンテナ数',
        'total_quantity': '総数量',
        'delivery_date': '納品日',
        'original_num_containers': '元コンテナ数',
        'original_total_quantity': '元総数量',
        'original_delivery_date': '元納品日',
        'capacity_per_container': 'コンテナ容量',
        'surplus': '残数量',
        'notes': '備考'
    }

    EDITABLE_COLUMN_REVERSE = {label: key for key, label in EDITABLE_COLUMN_LABELS.items()}

    def __init__(self, db_manager):
        self.transport_repo = TransportRepository(db_manager)
        self.production_repo = ProductionRepository(db_manager)
        self.product_repo = ProductRepository(db_manager)
        self.loading_plan_repo = LoadingPlanRepository(db_manager)
        self.delivery_progress_repo = DeliveryProgressRepository(db_manager)
        self.calendar_repo = CalendarRepository(db_manager)  # ✅ 追加
        
        self.planner = TransportPlanner()
        self.db = db_manager
    
    def get_containers(self):
        """容器一覧取得"""
        return self.transport_repo.get_containers()

    def get_trucks(self):
        """トラック一覧取得"""
        return self.transport_repo.get_trucks()

    def delete_truck(self, truck_id: int) -> bool:
        """トラック削除"""
        return self.transport_repo.delete_truck(truck_id) 
    
    def update_truck(self, truck_id: int, update_data: dict) -> bool:
        """トラック更新"""
        return self.transport_repo.update_truck(truck_id, update_data)

    def create_container(self, container_data: dict) -> bool:
        container_data.pop("max_volume", None)
        container_data.pop("created_at", None)
        return self.transport_repo.save_container(container_data)

    def update_container(self, container_id: int, update_data: dict) -> bool:
        update_data.pop("max_volume", None)
        update_data.pop("created_at", None)
        return self.transport_repo.update_container(container_id, update_data)
    
    def delete_container(self, container_id: int) -> bool:
        """容器削除"""
        return self.transport_repo.delete_container(container_id)

    def create_truck(self, truck_data: dict) -> bool:
        """トラック作成"""
        return self.transport_repo.save_truck(truck_data)
    
    def get_truck_container_rules(self) -> list:
        return self.transport_repo.get_truck_container_rules()

    def save_truck_container_rule(self, rule_data: dict) -> bool:
        # 必須キーの最小バリデーション
        required = ['truck_id', 'container_id', 'max_quantity']
        for k in required:
            if k not in rule_data or rule_data[k] in (None, ''):
                raise ValueError(f"'{k}' は必須です")
        return self.transport_repo.save_truck_container_rule(rule_data)

    def delete_truck_container_rule(self, rule_id: int) -> bool:
        return self.transport_repo.delete_truck_container_rule(rule_id)
    
    def update_truck_container_rule(self, rule_id: int, update_data: Dict[str, Any]) -> bool:
        """トラック×容器ルールの一部項目を更新"""
        if not isinstance(update_data, dict):
            return False
        allowed = {k: v for k, v in update_data.items() if k in {"max_quantity", "stack_count", "priority"}}
        if not allowed:
            return True
        # 数値化
        for k in list(allowed.keys()):
            if allowed[k] is None or allowed[k] == "":
                allowed.pop(k)
                continue
            try:
                allowed[k] = int(allowed[k])
            except Exception:
                pass
        if not allowed:
            return True
        return self.transport_repo.update_truck_container_rule(rule_id, allowed)

    def calculate_loading_plan_from_orders(self, 
                                          start_date: date, 
                                          days: int = 7,
                                          use_delivery_progress: bool = True,
                                          use_calendar: bool = True) -> Dict[str, Any]:  # ✅ use_calendar追加
        """
        オーダー情報から積載計画を自動作成（カレンダー対応）
        
        Args:
            start_date: 計画開始日
            days: 計画日数
            use_delivery_progress: 納入進度を使用するか
            use_calendar: 会社カレンダーを使用するか（営業日のみで計画）
        """
        
        end_date = start_date + timedelta(days=days - 1)
        
        if use_delivery_progress:
            orders_df = self.delivery_progress_repo.get_delivery_progress(start_date, end_date)
            
            if orders_df.empty:
                orders_df = self.production_repo.get_production_instructions(start_date, end_date)
                
                if not orders_df.empty:
                    orders_df = orders_df.rename(columns={
                        'instruction_date': 'delivery_date',
                        'instruction_quantity': 'order_quantity'
                    })
        else:
            orders_df = self.production_repo.get_production_instructions(start_date, end_date)
            
            if not orders_df.empty:
                orders_df = orders_df.rename(columns={
                    'instruction_date': 'delivery_date',
                    'instruction_quantity': 'order_quantity'
                })
        
        if orders_df is not None and not orders_df.empty:
            if 'delivery_date' in orders_df.columns:
                orders_df['delivery_date'] = pd.to_datetime(orders_df['delivery_date']).dt.date

            if use_calendar and self.calendar_repo:
                orders_df = orders_df[
                    orders_df['delivery_date'].apply(self.calendar_repo.is_working_day)
                ].reset_index(drop=True)
        
        if orders_df is not None and not orders_df.empty:
            if 'delivery_date' in orders_df.columns:
                orders_df['delivery_date'] = pd.to_datetime(orders_df['delivery_date']).dt.date

            if use_calendar and self.calendar_repo:
                orders_df = orders_df[
                    orders_df['delivery_date'].apply(self.calendar_repo.is_working_day)
                ].reset_index(drop=True)

            # 納入進捗・計画進度を加味した計画数量を算出
            manual_mask = pd.Series(False, index=orders_df.index)
            manual_remaining = pd.Series(0, index=orders_df.index, dtype='float64')
            if 'manual_planning_quantity' in orders_df.columns:
                manual_series = pd.to_numeric(orders_df['manual_planning_quantity'], errors='coerce')
                orders_df['manual_planning_quantity'] = manual_series
                manual_mask = manual_series.notna()
                if 'shipped_quantity' in orders_df.columns:
                    shipped_series = pd.to_numeric(orders_df['shipped_quantity'], errors='coerce').fillna(0)
                else:
                    shipped_series = pd.Series(0, index=orders_df.index, dtype='float64')
                if not isinstance(shipped_series, pd.Series):
                    shipped_series = pd.Series(shipped_series, index=orders_df.index)
                manual_remaining.loc[manual_mask] = (
                    manual_series.loc[manual_mask].fillna(0) - shipped_series.loc[manual_mask].fillna(0)
                ).clip(lower=0)
                orders_df['manual_planning_applied'] = manual_mask
            else:
                orders_df['manual_planning_applied'] = False
            remaining_qty = None
            if 'remaining_quantity' in orders_df.columns:
                remaining_qty = orders_df['remaining_quantity']
            elif {'order_quantity', 'shipped_quantity'}.issubset(orders_df.columns):
                remaining_qty = orders_df['order_quantity'] - orders_df['shipped_quantity']

            if remaining_qty is not None:
                orders_df['__remaining_qty'] = remaining_qty.fillna(0).clip(lower=0)
            else:
                if 'order_quantity' in orders_df.columns:
                    remaining_base = orders_df['order_quantity'].fillna(0)
                else:
                    remaining_base = pd.Series(0, index=orders_df.index)
                orders_df['__remaining_qty'] = remaining_base.clip(lower=0)

            if manual_mask.any():
                orders_df.loc[manual_mask, '__remaining_qty'] = manual_remaining.loc[manual_mask]

            if 'planned_progress_quantity' in orders_df.columns:
                orders_df['__progress_deficit'] = orders_df['planned_progress_quantity'].fillna(0).apply(
                    lambda x: max(0, -x)
                )
            else:
                orders_df['__progress_deficit'] = 0

            # 計画数量は基本的に残数量。計画進度がマイナスの場合は不足分を優先しつつ残数量を上限とする
            orders_df['planning_quantity'] = orders_df['__remaining_qty']
            backlog_mask = orders_df['__progress_deficit'] > 0
            if backlog_mask.any():
                orders_df.loc[backlog_mask, 'planning_quantity'] = orders_df.loc[backlog_mask].apply(
                    lambda row: min(row['__remaining_qty'], row['__progress_deficit']) if row['__remaining_qty'] > 0 else 0,
                    axis=1
                )

            # 残/不足ともに0の場合はスキップ
            if manual_mask.any():
                orders_df.loc[manual_mask, 'planning_quantity'] = manual_remaining.loc[manual_mask]

            orders_df = orders_df[orders_df['planning_quantity'] > 0].reset_index(drop=True)

            orders_df.drop(columns=['__remaining_qty', '__progress_deficit'], inplace=True, errors='ignore')

        if orders_df is None or orders_df.empty:
            return {
                'daily_plans': {},
                'summary': {
                    'total_days': days,
                    'total_trips': 0,
                    'total_warnings': 0,
                    'unloaded_count': 0,
                    'status': '正常'
                },
                'unloaded_tasks': [],
                'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
            }
        
        products_df = self.product_repo.get_all_products()
        containers = self.get_containers()
        trucks_df = self.get_trucks()
        truck_container_rules = self.transport_repo.get_truck_container_rules()
        
        # ✅ カレンダーリポジトリを渡す
        result = self.planner.calculate_loading_plan_from_orders(
            orders_df=orders_df,
            products_df=products_df,
            containers=containers,
            trucks_df=trucks_df,
            truck_container_rules=truck_container_rules,
            start_date=start_date,
            days=days,
            calendar_repo=self.calendar_repo if use_calendar else None  # カレンダー渡す
        )

        self._annotate_loading_plan_items(result)

        result['unplanned_orders'] = self._find_unplanned_orders(orders_df, result)

        return result

    def _annotate_loading_plan_items(self, plan_result: Dict[str, Any]) -> None:
        """積載計画データにExcel編集用の識別子と初期値を付与する。"""
        if not plan_result or 'daily_plans' not in plan_result:
            return

        sequence = 0
        daily_plans = plan_result.get('daily_plans', {})
        for date_str in sorted(daily_plans.keys()):
            day_plan = daily_plans.get(date_str) or {}
            trucks = day_plan.get('trucks', [])

            for trip_idx, truck_plan in enumerate(trucks, start=1):
                truck_plan.setdefault('trip_number', trip_idx)
                truck_plan.setdefault('trip_key', f"{date_str}|{truck_plan.get('truck_id', '')}|{trip_idx}")

                loaded_items = truck_plan.get('loaded_items', [])
                for item_idx, item in enumerate(loaded_items, start=1):
                    sequence += 1
                    truck_id = truck_plan.get('truck_id')
                    product_id = item.get('product_id', '')
                    key_parts = [
                        str(date_str),
                        str(truck_id) if truck_id is not None else '',
                        str(trip_idx),
                        str(item_idx),
                        str(product_id),
                        str(sequence)
                    ]
                    edit_key = "|".join(key_parts)
                    item.setdefault('edit_key', edit_key)
                    item.setdefault('trip_number', trip_idx)
                    item.setdefault('loading_date', date_str)
                    item.setdefault('original_num_containers', item.get('num_containers'))
                    item.setdefault('original_total_quantity', item.get('total_quantity'))
                    item.setdefault('truck_trip_key', truck_plan.get('trip_key'))

                    # 数量の整合性を強制的に合わせる
                    try:
                        num_containers = item.get('num_containers')
                        if pd.isna(num_containers):
                            num_containers = 0
                        num_containers = int(num_containers or 0)
                    except Exception:
                        num_containers = 0

                    capacity = item.get('capacity')
                    if capacity is None:
                        capacity = item.get('capacity_per_container')
                    try:
                        if pd.isna(capacity):
                            capacity = 0
                        capacity = int(capacity or 0)
                    except Exception:
                        capacity = 0

                    surplus_value = item.get('surplus', 0)
                    if pd.isna(surplus_value):
                        surplus_value = 0
                    try:
                        surplus_value = int(surplus_value)
                    except Exception:
                        try:
                            surplus_value = float(surplus_value)
                        except Exception:
                            surplus_value = 0

                    expected_quantity = None
                    if capacity and num_containers:
                        expected_quantity = max(0, num_containers * capacity - surplus_value)

                    manual_requested = item.get('manual_requested_quantity')
                    if expected_quantity is not None and manual_requested is not None:
                        try:
                            manual_requested = int(manual_requested)
                            expected_quantity = min(expected_quantity, manual_requested)
                        except Exception:
                            pass

                    if expected_quantity is not None:
                        item['total_quantity'] = expected_quantity
                        item.setdefault('original_total_quantity', expected_quantity)
                        item['capacity_per_container'] = capacity
                        item['surplus'] = surplus_value

    def save_loading_plan(self, plan_result: Dict[str, Any], plan_name: str = None) -> int:
        """積載計画をDBに保存"""
        return self.loading_plan_repo.save_loading_plan(plan_result, plan_name)
    
    def get_loading_plan(self, plan_id: int) -> Dict[str, Any]:
        """保存済み積載計画を取得"""
        plan = self.loading_plan_repo.get_loading_plan(plan_id)
        self._annotate_loading_plan_items(plan)
        return plan
    
    def get_all_loading_plans(self) -> List[Dict]:
        """全積載計画のリスト取得"""
        return self.loading_plan_repo.get_all_plans()
    
    def get_loading_plan_details_by_date(self, loading_date: date, truck_id: int = None) -> List[Dict[str, Any]]:
        """指定日の積載計画明細を取得"""
        return self.loading_plan_repo.get_plan_details_by_date_and_truck(loading_date, truck_id)
    
    def delete_loading_plan(self, plan_id: int) -> bool:
        """積載計画を削除"""
        return self.loading_plan_repo.delete_loading_plan(plan_id)
    
    def get_delivery_progress(self, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """納入進度取得"""
        return self.delivery_progress_repo.get_delivery_progress(start_date, end_date)
    
    def get_delivery_progress_by_product_and_date(self, product_id: int, delivery_date: date) -> Optional[Dict[str, Any]]:
        """製品と納期日で納入進度を取得"""
        return self.delivery_progress_repo.get_progress_by_product_and_date(product_id, delivery_date)
    
    def create_delivery_progress(self, progress_data: Dict[str, Any]) -> int:
        """納入進度を新規作成"""
        return self.delivery_progress_repo.create_delivery_progress(progress_data)
    
    def update_delivery_progress(self, progress_id: int, update_data: Dict[str, Any]) -> bool:
        """納入進度を更新"""
        return self.delivery_progress_repo.update_delivery_progress(progress_id, update_data)
    
    def delete_delivery_progress(self, progress_id: int) -> bool:
        """納入進度を削除"""
        return self.delivery_progress_repo.delete_delivery_progress(progress_id)
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """納入進度サマリー取得"""
        return self.delivery_progress_repo.get_progress_summary()
    
    def create_shipment_record(self, shipment_data: Dict[str, Any]) -> bool:
        """出荷実績を登録"""
        return self.delivery_progress_repo.create_shipment_record(shipment_data)
    
    def get_shipment_records(self, progress_id: int = None) -> pd.DataFrame:
        """出荷実績を取得"""
        return self.delivery_progress_repo.get_shipment_records(progress_id)
   
    def export_loading_plan_to_excel(self, plan_result: Dict[str, Any], 
                                     export_format: str = 'daily') -> BytesIO:
        """積載計画をExcelファイルとして出力"""
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            summary_df = pd.DataFrame([{
                '項目': k,
                '値': v
            } for k, v in plan_result['summary'].items()])
            summary_df.to_excel(writer, sheet_name='サマリー', index=False)
            
            if export_format == 'daily':
                self._export_daily_plan(writer, plan_result)
            elif export_format == 'weekly':
                self._export_weekly_plan(writer, plan_result)
            
            edit_rows = self._build_editable_rows(plan_result)
            if edit_rows:
                edit_df = pd.DataFrame(edit_rows)
                column_order = [col for col in self.EDITABLE_COLUMN_ORDER if col in edit_df.columns]
                if column_order:
                    edit_df = edit_df[column_order]
                edit_df = edit_df.rename(columns=self.EDITABLE_COLUMN_LABELS)
                edit_df.to_excel(writer, sheet_name='編集用', index=False)

            if plan_result.get('unloaded_tasks'):
                unloaded_df = pd.DataFrame([{
                    '製品コード': task['product_code'],
                    '製品名': task['product_name'],
                    '容器数': task['num_containers'],
                    '合計数量': task['total_quantity'],
                    '納期': task['delivery_date'].strftime('%Y-%m-%d')
                } for task in plan_result['unloaded_tasks']])
                unloaded_df.to_excel(writer, sheet_name='積載不可', index=False)
            
            warnings_data = []
            for date_str, plan in plan_result['daily_plans'].items():
                for warning in plan.get('warnings', []):
                    warnings_data.append({
                        '日付': date_str,
                        '警告内容': warning
                    })
            
            if warnings_data:
                warnings_df = pd.DataFrame(warnings_data)
                warnings_df.to_excel(writer, sheet_name='警告一覧', index=False)
        
        output.seek(0)
        return output
    
    def _export_daily_plan(self, writer, plan_result):
        """日別計画をExcelシートに出力"""
        
        daily_data = []
        prev_date = None
        
        for date_str in sorted(plan_result['daily_plans'].keys()):
            plan = plan_result['daily_plans'][date_str]
            
            # 日付が変わったら空白行を挿入
            if prev_date is not None and prev_date != date_str:
                daily_data.append({
                    '積載日': '',
                    'トラック名': '',
                    '製品コード': '',
                    '製品名': '',
                    '容器数': '',
                    '合計数量': '',
                    '納期': '',
                    '体積積載率': ''
                })
            
            prev_date = date_str
            
            for truck in plan.get('trucks', []):
                truck_name = truck.get('truck_name', '不明なトラック')
                truck_id = truck.get('truck_id', 0)
            
                print(f"🔍 デバッグ: {date_str} - truck_id={truck_id}, truck_name={truck_name}")
                for item in truck.get('loaded_items', []):
                    # 前倒しフラグを取得
                    is_advanced = item.get('is_advanced', False)
                    advanced_mark = '○' if is_advanced else '×'
                    
                    daily_data.append({
                        '積載日': date_str,
                        'トラック名': truck['truck_name'],
                        '製品コード': item.get('product_code', ''),
                        '製品名': item.get('product_name', ''),
                        '容器数': item.get('num_containers', 0),
                        '合計数量': item.get('total_quantity', 0),
                        '納期': item['delivery_date'].strftime('%Y-%m-%d') if 'delivery_date' in item else '',
                        '体積積載率(%)': truck['utilization']['volume_rate'],
                        '前倒し配送': advanced_mark
                    })
        
        if daily_data:
            daily_df = pd.DataFrame(daily_data)
            daily_df.to_excel(writer, sheet_name='日別計画', index=False)
    
    def _export_weekly_plan(self, writer, plan_result):
        """週別計画をExcelシートに出力"""
        
        from datetime import datetime
        
        weekly_data = {}
        
        for date_str in sorted(plan_result['daily_plans'].keys()):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            week_num = date_obj.isocalendar()[1]
            week_key = f"{date_obj.year}年第{week_num}週"
            
            if week_key not in weekly_data:
                weekly_data[week_key] = []
            
            plan = plan_result['daily_plans'][date_str]
            
            for truck in plan.get('trucks', []):
                for item in truck.get('loaded_items', []):
                    # 前倒しフラグを取得
                    is_advanced = item.get('is_advanced', False)
                    advanced_mark = '○' if is_advanced else '×'
                    
                    weekly_data[week_key].append({
                        '週': week_key,
                        '積載日': date_str,
                        'トラック名': truck['truck_name'],
                        '製品コード': item.get('product_code', ''),
                        '製品名': item.get('product_name', ''),
                        '容器数': item.get('num_containers', 0),
                        '合計数量': item.get('total_quantity', 0),
                        '納期': item['delivery_date'].strftime('%Y-%m-%d') if 'delivery_date' in item else '',
                        '前倒し配送': advanced_mark
                    })
        
        for week_key, items in weekly_data.items():
            if items:
                week_df = pd.DataFrame(items)
                sheet_name = week_key[:31]
                week_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    def _build_editable_rows(self, plan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Excelでの修正対象となる行データを作成する。"""
        rows: List[Dict[str, Any]] = []
        if not plan_result:
            return rows

        daily_plans = plan_result.get('daily_plans', {})
        for date_str in sorted(daily_plans.keys()):
            day_plan = daily_plans.get(date_str) or {}
            for truck_plan in day_plan.get('trucks', []):
                trip_number = truck_plan.get('trip_number')
                truck_id = truck_plan.get('truck_id')
                truck_name = truck_plan.get('truck_name')

                for item in truck_plan.get('loaded_items', []):
                    delivery_date = item.get('delivery_date')
                    if isinstance(delivery_date, datetime):
                        delivery_value = delivery_date.date()
                    else:
                        delivery_value = delivery_date

                    original_delivery = item.get('original_date')
                    if isinstance(original_delivery, datetime):
                        original_delivery = original_delivery.date()

                    rows.append({
                        'edit_key': str(item.get('edit_key', '')),
                        'loading_date': date_str,
                        'truck_id': truck_id,
                        'truck_name': truck_name,
                        'trip_number': trip_number,
                        'product_id': item.get('product_id'),
                        'product_code': item.get('product_code'),
                        'product_name': item.get('product_name'),
                        'container_id': item.get('container_id'),
                        'num_containers': item.get('num_containers'),
                        'total_quantity': item.get('total_quantity'),
                        'original_num_containers': item.get('original_num_containers'),
                        'original_total_quantity': item.get('original_total_quantity'),
                        'delivery_date': delivery_value,
                        'original_delivery_date': original_delivery,
                        'capacity_per_container': item.get('capacity'),
                        'surplus': item.get('surplus'),
                        'notes': item.get('memo') or item.get('notes')
                    })

        return rows

    def _recalculate_plan_utilizations(self, plan_result: Dict[str, Any], affected_trip_keys: List[tuple]) -> None:
        """�S�Z�b�g�ɋύX�����g���b�N�p�̓��ϗ��v�Z"""
        if not plan_result or not affected_trip_keys:
            return

        containers = self.get_containers() or []
        container_map = {c.id: c for c in containers if hasattr(c, 'id')}

        trucks_df = self.get_trucks()
        truck_info_map: Dict[int, Dict[str, Any]] = {}
        if trucks_df is not None and not getattr(trucks_df, 'empty', False):
            for _, row in trucks_df.iterrows():
                truck_id = row.get('id')
                if pd.isna(truck_id):
                    continue
                try:
                    truck_info_map[int(truck_id)] = row.to_dict()
                except (TypeError, ValueError):
                    continue

        for date_str, truck_id, trip_number in affected_trip_keys:
            day_plan = plan_result.get('daily_plans', {}).get(date_str)
            if not day_plan:
                continue

            for truck_plan in day_plan.get('trucks', []):
                plan_truck_id = truck_plan.get('truck_id')
                plan_trip = truck_plan.get('trip_number')

                if trip_number is not None and plan_trip != trip_number:
                    continue

                if str(plan_truck_id) != str(truck_id):
                    continue

                self._recalculate_truck_plan_utilization(truck_plan, truck_info_map, container_map)
                break

    def _recalculate_truck_plan_utilization(
        self,
        truck_plan: Dict[str, Any],
        truck_info_map: Dict[int, Dict[str, Any]],
        container_map: Dict[int, Any]
    ) -> None:
        """�V���O�g���b�N�p�̉��ϗ��v�Z"""
        truck_id = truck_plan.get('truck_id')
        truck_info = None
        candidate_keys = []
        if truck_id is not None:
            candidate_keys.append(truck_id)
            try:
                candidate_keys.append(int(round(float(truck_id))))
            except (TypeError, ValueError):
                pass

        for key in candidate_keys:
            if key is None:
                continue
            normalized = key
            try:
                normalized = int(key)
            except (TypeError, ValueError):
                pass

            if normalized in truck_info_map:
                truck_info = truck_info_map[normalized]
                break
            if key in truck_info_map:
                truck_info = truck_info_map[key]
                break

        if not truck_info:
            return

        def _to_float(val):
            if pd.isna(val):
                return 0.0
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        width = _to_float(truck_info.get('width'))
        depth = _to_float(truck_info.get('depth'))
        height = _to_float(truck_info.get('height'))
        max_weight = _to_float(truck_info.get('max_weight'))

        truck_floor_area = (width * depth) / 1_000_000 if width and depth else 0.0
        truck_volume = (width * depth * height) / 1_000_000_000 if width and depth and height else 0.0

        container_totals: Dict[int, Dict[str, Any]] = {}

        for item in truck_plan.get('loaded_items', []):
            container_id = item.get('container_id')
            container = container_map.get(container_id)
            if not container:
                continue

            try:
                num_containers = int(round(float(item.get('num_containers', 0) or 0)))
            except (TypeError, ValueError):
                num_containers = 0

            num_containers = max(num_containers, 0)

            per_area = ((container.width or 0) * (container.depth or 0)) / 1_000_000
            per_volume = ((container.width or 0) * (container.depth or 0) * (container.height or 0)) / 1_000_000_000
            per_weight = getattr(container, 'max_weight', 0) or 0
            stackable = bool(getattr(container, 'stackable', False))
            max_stack = getattr(container, 'max_stack', 1) or 1

            item['num_containers'] = num_containers
            item['floor_area_per_container'] = per_area
            item['floor_area'] = per_area * num_containers
            item['volume_per_container'] = per_volume
            item['weight_per_container'] = per_weight

            totals = container_totals.setdefault(container_id, {
                'num_containers': 0,
                'per_area': per_area,
                'per_volume': per_volume,
                'per_weight': per_weight,
                'stackable': stackable,
                'max_stack': max_stack
            })
            totals['num_containers'] += num_containers

        loaded_area = 0.0
        loaded_volume = 0.0
        loaded_weight = 0.0

        for totals in container_totals.values():
            num = totals['num_containers']
            if totals['stackable'] and totals['max_stack'] > 1:
                used_slots = math.ceil(num / totals['max_stack'])
            else:
                used_slots = num

            loaded_area += totals['per_area'] * used_slots
            loaded_volume += totals['per_volume'] * num

        utilization = truck_plan.setdefault('utilization', {})
        utilization['floor_area_rate'] = round(loaded_area / truck_floor_area * 100, 1) if truck_floor_area > 0 else 0
        utilization['volume_rate'] = round(loaded_volume / truck_volume * 100, 1) if truck_volume > 0 else 0

    def export_loading_plan_to_csv(self, plan_result: Dict[str, Any]) -> str:
        """積載計画をCSV形式で出力"""
        
        daily_data = []
        
        for date_str in sorted(plan_result['daily_plans'].keys()):
            plan = plan_result['daily_plans'][date_str]
            
            for truck in plan.get('trucks', []):
                for item in truck.get('loaded_items', []):
                    # 前倒しフラグを取得
                    is_advanced = item.get('is_advanced', False)
                    advanced_mark = '○' if is_advanced else '×'
                    
                    daily_data.append({
                        '積載日': date_str,
                        'トラック名': truck['truck_name'],
                        '製品コード': item.get('product_code', ''),
                        '製品名': item.get('product_name', ''),
                        '容器数': item.get('num_containers', 0),
                        '合計数量': item.get('total_quantity', 0),
                        '納期': item['delivery_date'].strftime('%Y-%m-%d') if 'delivery_date' in item else '',
                        '体積積載率(%)': truck['utilization']['volume_rate'],
                        '前倒し配送': advanced_mark
                    })
        
        # 警告情報も追加
        warning_data = []
        for date_str in sorted(plan_result['daily_plans'].keys()):
            plan = plan_result['daily_plans'][date_str]
            for warning in plan.get('warnings', []):
                warning_data.append({
                    '日付': date_str,
                    '警告内容': warning
                })
        
        if daily_data:
            df = pd.DataFrame(daily_data)
            csv_output = df.to_csv(index=False, encoding='utf-8-sig')
            
            # 警告がある場合は追加
            if warning_data:
                csv_output += '\n\n'
                warning_df = pd.DataFrame(warning_data)
                csv_output += warning_df.to_csv(index=False, encoding='utf-8-sig')
            
            return csv_output
        else:
            return ""

    def apply_excel_adjustments(self, plan_result: Dict[str, Any], excel_source: Any) -> Dict[str, Any]:
        """Excelで編集された計画の変更を取り込み、再計算する。"""
        response = {
            'plan': plan_result,
            'changes': [],
            'errors': []
        }

        if plan_result is None:
            response['errors'].append("計画データがありません。")
            return response

        if excel_source is None:
            response['errors'].append("Excelファイルが指定されていません。")
            return response

        if isinstance(excel_source, BytesIO):
            excel_bytes = excel_source.getvalue()
        elif hasattr(excel_source, "getvalue"):
            excel_bytes = excel_source.getvalue()
        elif hasattr(excel_source, "read"):
            excel_bytes = excel_source.read()
        elif isinstance(excel_source, (bytes, bytearray)):
            excel_bytes = excel_source
        else:
            response['errors'].append("Excelファイルを読み込めませんでした。")
            return response

        buffer = BytesIO(excel_bytes)
        sheet_candidates = ['編集用', 'EditPlan', 'EditablePlan', 'Editable']
        edit_df = None
        used_sheet = None

        for sheet in sheet_candidates:
            try:
                buffer.seek(0)
                edit_df = pd.read_excel(buffer, sheet_name=sheet)
                used_sheet = sheet
                break
            except ValueError:
                continue
            except Exception as exc:
                response['errors'].append(f"Excel読み込みエラー: {exc}")
                return response

        if edit_df is None:
            response['errors'].append("編集用シート(編集用 / EditPlan)が見つかりません。")
            return response

        edit_df.columns = [str(col).strip() for col in edit_df.columns]
        rename_candidates = {
            col: self.EDITABLE_COLUMN_REVERSE[col]
            for col in edit_df.columns
            if col in self.EDITABLE_COLUMN_REVERSE
        }
        if rename_candidates:
            edit_df = edit_df.rename(columns=rename_candidates)

        if 'edit_key' not in edit_df.columns:
            response['errors'].append("編集用シートにedit_key列がありません。")
            return response

        edit_df = edit_df.copy()
        edit_df = edit_df[~edit_df['edit_key'].isna()]
        edit_df['edit_key'] = edit_df['edit_key'].astype(str).str.strip()
        edit_df = edit_df[(edit_df['edit_key'] != '') & (edit_df['edit_key'].str.lower() != 'nan')]

        if edit_df.empty:
            response['errors'].append("編集用シートに有効なデータがありません。")
            return response

        duplicated_keys = edit_df['edit_key'][edit_df['edit_key'].duplicated()].unique()
        if len(duplicated_keys) > 0:
            response['errors'].append(f"edit_keyが重複しています: {', '.join(map(str, duplicated_keys))}")
            return response

        daily_plans = plan_result.get('daily_plans', {})
        item_lookup: Dict[str, Dict[str, Any]] = {}
        for date_str, day_plan in daily_plans.items():
            for truck_plan in day_plan.get('trucks', []):
                for item in truck_plan.get('loaded_items', []):
                    key = str(item.get('edit_key', '')).strip()
                    if not key or key in item_lookup:
                        continue
                    item_lookup[key] = {
                        'date': date_str,
                        'truck_plan': truck_plan,
                        'item': item
                    }

        def _is_blank(value) -> bool:
            if value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ''
            return pd.isna(value)

        def _normalize_int(value) -> Optional[int]:
            if _is_blank(value):
                return None
            if isinstance(value, int):
                return int(value)
            if isinstance(value, float):
                if math.isnan(value):
                    return None
                return int(round(value))
            value_str = str(value).strip()
            if value_str == '':
                return None
            try:
                return int(round(float(value_str)))
            except (TypeError, ValueError):
                raise ValueError(f"数値に変換できません: {value}")

        def _normalize_date(value) -> Optional[date]:
            if _is_blank(value):
                return None
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            value_str = str(value).strip()
            if value_str == '':
                return None
            try:
                return datetime.strptime(value_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return pd.to_datetime(value_str).date()
                except Exception as exc:
                    raise ValueError(f"日付に変換できません: {value}") from exc

        changes: List[Dict[str, Any]] = []
        affected_trips = set()
        now_str = datetime.now().isoformat()

        for row in edit_df.to_dict('records'):
            key = row.get('edit_key')
            if key not in item_lookup:
                response['errors'].append(f"edit_key {key} は現在の計画に存在しません。")
                continue

            entry = item_lookup[key]
            item = entry['item']
            truck_plan = entry['truck_plan']
            change_fields: Dict[str, Dict[str, Any]] = {}

            if 'num_containers' in row:
                try:
                    new_num = _normalize_int(row.get('num_containers'))
                except ValueError as exc:
                    response['errors'].append(f"{key} のnum_containers: {exc}")
                    continue
                if new_num is not None:
                    if new_num < 0:
                        response['errors'].append(f"{key} のnum_containersが負の値です。")
                        continue
                    if new_num != item.get('num_containers'):
                        change_fields['num_containers'] = {
                            'before': item.get('num_containers'),
                            'after': new_num
                        }
                        item['num_containers'] = new_num

            if 'total_quantity' in row:
                try:
                    new_qty = _normalize_int(row.get('total_quantity'))
                except ValueError as exc:
                    response['errors'].append(f"{key} のtotal_quantity: {exc}")
                    continue
                if new_qty is not None:
                    if new_qty < 0:
                        response['errors'].append(f"{key} のtotal_quantityが負の値です。")
                        continue
                    if new_qty != item.get('total_quantity'):
                        change_fields['total_quantity'] = {
                            'before': item.get('total_quantity'),
                            'after': new_qty
                        }
                        item['total_quantity'] = new_qty

            if 'delivery_date' in edit_df.columns:
                try:
                    new_date = _normalize_date(row.get('delivery_date'))
                except ValueError as exc:
                    response['errors'].append(f"{key} のdelivery_date: {exc}")
                    continue
                if new_date is not None:
                    current = item.get('delivery_date')
                    if isinstance(current, datetime):
                        current = current.date()
                    if current != new_date:
                        change_fields['delivery_date'] = {
                            'before': current,
                            'after': new_date
                        }
                        item['delivery_date'] = new_date

            if not change_fields:
                continue

            item['manual_adjusted'] = True
            item['last_manual_update'] = now_str

            changes.append({
                'edit_key': key,
                'loading_date': entry['date'],
                'truck_name': truck_plan.get('truck_name'),
                'product_code': item.get('product_code'),
                'product_name': item.get('product_name'),
                'changes': change_fields
            })
            affected_trips.add((entry['date'], truck_plan.get('truck_id'), truck_plan.get('trip_number')))

        if changes:
            self._recalculate_plan_utilizations(plan_result, list(affected_trips))
            summary = plan_result.setdefault('summary', {})
            summary['manual_adjusted'] = True
            summary['manual_adjustment_count'] = len(changes)
            metadata = plan_result.setdefault('metadata', {})
            metadata['excel_adjusted_at'] = now_str
            metadata['excel_adjusted_sheet'] = used_sheet
            response['changes'] = changes
        else:
            if not response['errors']:
                response['errors'].append("Excelの変更が検出されませんでした。")

        return response

    def _find_unplanned_orders(self, orders_df: pd.DataFrame, plan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """積載計画に含まれなかった受注を抽出"""
        if orders_df is None or orders_df.empty:
            return []
        if 'delivery_date' not in orders_df.columns or 'product_id' not in orders_df.columns:
            return []

        quantity_col = None
        for candidate in ['order_quantity', 'instruction_quantity']:
            if candidate in orders_df.columns:
                quantity_col = candidate
                break
        if quantity_col is None:
            return []

        orders = orders_df.copy()
        orders['delivery_date'] = pd.to_datetime(orders['delivery_date']).dt.date
        orders['product_id'] = pd.to_numeric(orders['product_id'], errors='coerce')
        orders = orders.dropna(subset=['product_id', 'delivery_date'])
        orders['product_id'] = orders['product_id'].astype(int)
        orders[quantity_col] = pd.to_numeric(orders[quantity_col], errors='coerce').fillna(0)

        manual_available = 'manual_planning_quantity' in orders.columns
        if manual_available:
            orders['manual_planning_quantity'] = pd.to_numeric(
                orders['manual_planning_quantity'], errors='coerce'
            )
            orders['target_quantity'] = orders['manual_planning_quantity'].combine_first(orders[quantity_col])
        else:
            orders['target_quantity'] = orders[quantity_col]
        orders['target_quantity'] = orders['target_quantity'].fillna(0)

        planned_rows = []
        for plan in plan_result.get('daily_plans', {}).values():
            for truck in plan.get('trucks', []):
                for item in truck.get('loaded_items', []):
                    product_id = item.get('product_id')
                    delivery_date = item.get('delivery_date')
                    if product_id is None or delivery_date is None:
                        continue
                    if isinstance(delivery_date, datetime):
                        delivery_date = delivery_date.date()
                    planned_rows.append({
                        'product_id': product_id,
                        'delivery_date': delivery_date,
                        'loaded_quantity': item.get('total_quantity', 0)
                    })

        if planned_rows:
            planned_df = pd.DataFrame(planned_rows)
            planned_df['delivery_date'] = pd.to_datetime(planned_df['delivery_date']).dt.date
            planned_summary = (
                planned_df.groupby(['product_id', 'delivery_date'])['loaded_quantity']
                .sum()
                .reset_index()
            )
            orders = orders.merge(planned_summary, how='left', on=['product_id', 'delivery_date'])
        else:
            orders['loaded_quantity'] = 0

        if 'loaded_quantity' not in orders.columns:
            orders['loaded_quantity'] = 0

        orders['loaded_quantity'] = orders['loaded_quantity'].fillna(0)
        orders['remaining_quantity'] = orders['target_quantity'] - orders['loaded_quantity']

        unplanned = orders[orders['remaining_quantity'] > 0].copy()
        if unplanned.empty:
            return []

        column_order = []
        optional_fields = ['order_id', 'instruction_id', 'product_code', 'product_name', 'customer_name']
        if manual_available:
            optional_fields.append('manual_planning_quantity')
        for optional in optional_fields:
            if optional in unplanned.columns:
                column_order.append(optional)

        required = ['product_id', 'delivery_date', quantity_col, 'target_quantity', 'loaded_quantity', 'remaining_quantity']
        column_order.extend(required)
        # 重複を削除しつつ順序を維持
        seen = set()
        ordered_columns = []
        for col in column_order:
            if col in unplanned.columns and col not in seen:
                ordered_columns.append(col)
                seen.add(col)

        unplanned['delivery_date'] = pd.to_datetime(unplanned['delivery_date']).dt.strftime('%Y-%m-%d')
        return unplanned[ordered_columns].to_dict('records')

    def update_loading_plan(self, plan_id: int, updates: List[Dict]) -> bool:
        """積載計画を更新"""
        try:
            for update in updates:
                # 明細更新
                if 'detail_id' in update:
                    success = self.loading_plan_repo.update_loading_plan_detail(
                        update['detail_id'], 
                        update['changes']
                    )
                    
                    if success:
                        # 編集履歴を保存
                        history_data = {
                            'plan_id': plan_id,
                            'user_id': update.get('user_id', 'system'),
                            'field_changed': 'detail_update',
                            'old_value': str(update.get('old_values', {})),
                            'new_value': str(update['changes']),
                            'detail_id': update['detail_id']
                        }
                        self.loading_plan_repo.save_edit_history(history_data)
            
            return True
            
        except Exception as e:
            print(f"計画更新エラー: {e}")
            return False

    def create_plan_version(self, plan_id: int, version_name: str, user_id: str = None) -> int:
        """計画バージョンを作成"""
        try:
            # 現在の計画データを取得
            current_plan = self.get_loading_plan(plan_id)
            
            version_data = {
                'plan_id': plan_id,
                'version_name': version_name,
                'created_by': user_id or 'system',
                'snapshot_data': json.dumps(current_plan, default=str),
                'notes': f"手動バージョン作成: {version_name}"
            }
            
            return self.loading_plan_repo.create_plan_version(version_data)
            
        except Exception as e:
            print(f"バージョン作成エラー: {e}")
            return 0        
    #ストアドを呼び出して計画進度を再計算
    def recompute_planned_progress(self, product_id: int, start_date: date, end_date: date) -> None:
        """登録済みストアドを呼び出して計画進度を再計算"""
        session = self.db.get_session()
        try:
            session.execute(
                text("CALL recompute_planned_progress_by_product(:pid, :s, :e)"),
                {"pid": product_id, "s": start_date, "e": end_date}
            )
            session.commit()
        finally:
            session.close()

    def recompute_planned_progress_all(self, start_date: date, end_date: date) -> None:
        products = self.product_repo.get_all_products()
        if products is None or products.empty or 'id' not in products.columns:
            return
        product_ids = products['id'].dropna().astype(int).tolist()
        for pid in product_ids:
            self.recompute_planned_progress(pid, start_date, end_date)
    # --- 実績進度（shipped_remaining_quantity）の再計算 ---
    def recompute_shipped_remaining(self, product_id: int, start_date: date, end_date: date) -> None:
        """
        ストアドを呼び出して実績進度（shipped_remaining_quantity）を再計算
        期待するSP名: recompute_shipped_remaining_by_product(pid, start, end)
        """
        session = self.db.get_session()
        try:
            session.execute(
                text("CALL recompute_shipped_remaining_by_product(:pid, :s, :e)"),
                {"pid": product_id, "s": start_date, "e": end_date}
            )
            session.commit()
        finally:
            session.close()

    def recompute_shipped_remaining_all(self, start_date: date, end_date: date) -> None:
        """
        全製品分を一括再計算（期間内の全製品IDを対象）
        - 既存の planned_all と同様に product_repo を使う簡易版
        - 期間内に存在する製品だけに絞りたい場合は delivery_progress から DISTINCT 取得に差し替え可
        """
        products = self.product_repo.get_all_products()
        if products is None or products.empty or 'id' not in products.columns:
            return
        product_ids = products['id'].dropna().astype(int).tolist()
        for pid in product_ids:
            self.recompute_shipped_remaining(pid, start_date, end_date)

