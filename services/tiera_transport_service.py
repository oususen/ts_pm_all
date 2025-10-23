# services/tiera_transport_service.py
"""
Tiera様専用の運送サービス

TransportServiceを継承し、積載計画のロジックのみをTiera様専用に変更
"""

from typing import Dict, Any
from datetime import date, timedelta
from services.transport_service import TransportService
from domain.calculators.tiera_transport_planner import TieraTransportPlanner
import pandas as pd


class TieraTransportService(TransportService):
    """Tiera様専用運送サービス"""

    def __init__(self, db_manager):
        super().__init__(db_manager)
        # Tiera様専用プランナーを使用
        self.planner = TieraTransportPlanner()

    def calculate_loading_plan_from_orders(self,
                                          start_date: date,
                                          days: int = 7,
                                          use_delivery_progress: bool = True,
                                          use_calendar: bool = True) -> Dict[str, Any]:
        """
        Tiera様の積載計画作成

        【Kubota様との違い】
        - 前倒し無し（リードタイム固定）
        - 特便無し
        - 夕便優先
        - シンプルに積めるだけ積む
        """

        end_date = start_date + timedelta(days=days - 1)

        # 受注データ取得（Kubota様と同じ）
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

        # 日付変換
        if orders_df is not None and not orders_df.empty:
            if 'delivery_date' in orders_df.columns:
                orders_df['delivery_date'] = pd.to_datetime(orders_df['delivery_date']).dt.date

            # 営業日フィルタ
            if use_calendar and self.calendar_repo:
                orders_df = orders_df[
                    orders_df['delivery_date'].apply(self.calendar_repo.is_working_day)
                ].reset_index(drop=True)

        # 計画数量計算（Kubota様と同じロジック）
        if orders_df is not None and not orders_df.empty:
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

            orders_df['planning_quantity'] = orders_df['__remaining_qty']
            backlog_mask = orders_df['__progress_deficit'] > 0
            if backlog_mask.any():
                orders_df.loc[backlog_mask, 'planning_quantity'] = orders_df.loc[backlog_mask].apply(
                    lambda row: min(row['__remaining_qty'], row['__progress_deficit']) if row['__remaining_qty'] > 0 else 0,
                    axis=1
                )

            if manual_mask.any():
                orders_df.loc[manual_mask, 'planning_quantity'] = manual_remaining.loc[manual_mask]

            orders_df = orders_df[orders_df['planning_quantity'] > 0].reset_index(drop=True)

            orders_df.drop(columns=['__remaining_qty', '__progress_deficit'], inplace=True, errors='ignore')

        # データが無い場合
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

        # マスタデータ取得
        products_df = self.product_repo.get_all_products()
        containers = self.get_containers()
        trucks_df = self.get_trucks()
        truck_container_rules = self.transport_repo.get_truck_container_rules()

        # ✅ Tiera様専用プランナーで計画作成
        result = self.planner.calculate_loading_plan_from_orders(
            orders_df=orders_df,
            products_df=products_df,
            containers=containers,
            trucks_df=trucks_df,
            truck_container_rules=truck_container_rules,
            start_date=start_date,
            days=days,
            calendar_repo=self.calendar_repo if use_calendar else None
        )

        # 結果にアノテーション追加（Kubota様と同じ）
        self._annotate_loading_plan_items(result)

        # 未計画受注を検出（Kubota様と同じ）
        result['unplanned_orders'] = self._find_unplanned_orders(orders_df, result)

        return result
