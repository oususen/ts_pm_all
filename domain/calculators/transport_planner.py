# app/domain/calculators/transport_planner.py
from typing import List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from collections import defaultdict
import pandas as pd

class TransportPlanner:
    """
    運送計画計算機 - 新ルール対応版
    【基本ルール】
    1. 底面積ベースで計算（体積ではない）
    2. デフォルト3台 + 非デフォルト1台
    3. 前倒しは1日前のみ
    4. トラックの優先積載製品を考慮
    【計画プロセス】
    Step1: 需要分析とトラック台数決定
    Step2: 前倒し処理（最終日から逆順）
    Step3: 日次積載計画作成（優先製品→同容器製品→異容器製品）
    Step4: 非デフォルトトラック活用
    """
    def __init__(self, calendar_repo=None):
        self.calendar_repo = calendar_repo

    def calculate_loading_plan_from_orders(self,
                                          orders_df: pd.DataFrame,
                                          products_df: pd.DataFrame,
                                          containers: List[Any],
                                          trucks_df: pd.DataFrame,
                                          truck_container_rules: List[Any],
                                          start_date: date,
                                          days: int = 7,
                                          calendar_repo=None) -> Dict[str, Any]:
        """新ルールに基づく積載計画作成"""
        self.calendar_repo = calendar_repo
        # 営業日のみで計画期間を構築
        working_dates = self._get_working_dates(start_date, days, calendar_repo)
        # データ準備
        container_map = {c.id: c for c in containers}
        # トラックマップ作成（NaNチェック）
        truck_map = {}
        for _, row in trucks_df.iterrows():
            try:
                truck_id = row['id']
                if pd.isna(truck_id):
                    continue
                truck_map[int(truck_id)] = row
            except (ValueError, TypeError):
                continue
        # 製品マップ作成（NaNチェック）
        product_map = {}
        for _, row in products_df.iterrows():
            try:
                product_id = row['id']
                if pd.isna(product_id):
                    continue
                product_map[int(product_id)] = row
            except (ValueError, TypeError):
                continue
        # Step1: 需要分析とトラック台数決定
        daily_demands, use_non_default = self._analyze_demand_and_decide_trucks(
            orders_df, product_map, container_map, truck_map, working_dates
        )
        # Step2: 前倒し処理（最終日から逆順）
        adjusted_demands = self._forward_scheduling(
            daily_demands, truck_map, container_map, working_dates, use_non_default
        )
        # Step3: 日次積載計画作成
        daily_plans = {}
        all_remaining_demands = []  # 全日の積み残しを収集
        for working_date in working_dates:
            date_str = working_date.strftime('%Y-%m-%d')
            if date_str not in adjusted_demands or not adjusted_demands[date_str]:
                daily_plans[date_str] = {'trucks': [], 'total_trips': 0, 'warnings': [], 'remaining_demands': []}
                continue
            plan = self._create_daily_loading_plan(
                adjusted_demands[date_str],
                truck_map,
                container_map,
                product_map,
                use_non_default,
                working_date
            )
            daily_plans[date_str] = plan
            # 積み残しを収集
            if plan.get('remaining_demands'):
                all_remaining_demands.extend(plan['remaining_demands'])
        # Step4: 積み残しを他のトラック候補で再配置
        if all_remaining_demands:
            self._relocate_remaining_demands(
                all_remaining_demands,
                daily_plans,
                truck_map,
                container_map,
                working_dates,
                use_non_default
            )
        # Step5: 積み残しを前倒し（前倒し可能な製品のみ）
        self._forward_remaining_demands(
            daily_plans,
            truck_map,
            container_map,
            working_dates,
            use_non_default
        )
        # Step6: 積み残しを翌日以降に再配置
        self._relocate_to_next_days(
            daily_plans,
            truck_map,
            container_map,
            working_dates,
            use_non_default
        )
        # まとめ対象日付を実際の計画日で絞り込み
        planned_dates = [
            date for date in working_dates
            if date.strftime('%Y-%m-%d') in daily_plans and daily_plans[date.strftime('%Y-%m-%d')]['trucks']
        ]
        if not planned_dates:
            planned_dates = working_dates
        # Step7: 最終日の積み残しに特別フラグを設定
        final_date_str = planned_dates[-1].strftime('%Y-%m-%d') if planned_dates else None
        if final_date_str and final_date_str in daily_plans:
            final_plan = daily_plans[final_date_str]
            if final_plan.get('remaining_demands'):
                for demand in final_plan['remaining_demands']:
                    demand['final_day_overflow'] = True
        # Step8: 翌日着トラックの積載日を前日に調整
        self._adjust_for_next_day_arrival_trucks(daily_plans, truck_map, start_date)
        
        # Step9: トラック移動後にplanned_datesを再計算（期間外の日付も含める）
        all_dates_with_trucks = [
            datetime.strptime(date_str, '%Y-%m-%d').date()
            for date_str in daily_plans.keys()
            if daily_plans[date_str]['trucks']
        ]
        if all_dates_with_trucks:
            all_dates_with_trucks.sort()
            planned_dates = all_dates_with_trucks
            period_start = planned_dates[0]
            period_end = planned_dates[-1]
        else:
            period_start = working_dates[0]
            period_end = working_dates[-1]
        
        # サマリー作成
        summary = self._create_summary(daily_plans, use_non_default, planned_dates)
        return {
            'daily_plans': daily_plans,
            'summary': summary,
            'unloaded_tasks': [],  # 互換性のため
            'period': f"{period_start.strftime('%Y-%m-%d')} ~ {period_end.strftime('%Y-%m-%d')}",
            'working_dates': [d.strftime('%Y-%m-%d') for d in planned_dates],
            'use_non_default_truck': use_non_default
        }

    def _get_working_dates(self, start_date: date, days: int, calendar_repo) -> List[date]:
        """営業日のみを取得"""
        working_dates = []
        current_date = start_date
        while len(working_dates) < days:
            if not calendar_repo or calendar_repo.is_working_day(current_date):
                working_dates.append(current_date)
            current_date += timedelta(days=1)
        return working_dates

    def _can_arrive_on_time(self, truck_info: Dict[str, Any], loading_date: date, delivery_date: date) -> bool:
        """
        トラックが納期までに到着できるか判定
        
        注意：第一段階ではarrival_day_offsetを無視（常に0として扱う）
        翌日着トラックの調整は第二段階で実施
        """
        if delivery_date is None or loading_date is None:
            return True
        # arrival_day_offsetを無視して、積載日=到着日として判定
        offset = 0
        arrival_date = loading_date + timedelta(days=offset)
        return arrival_date <= delivery_date

    def _analyze_demand_and_decide_trucks(self, orders_df, product_map, container_map, 
                                         truck_map, working_dates) -> Tuple[Dict, bool]:
        """
        Step1: 需要分析とトラック台数決定
        Returns:
            daily_demands: {日付: [需要リスト]}
            use_non_default: 非デフォルトトラックを使用するか
        """
        daily_demands = defaultdict(list)
        total_floor_area = 0
        
        # デフォルトトラックの総底面積を計算（mm²をm²に変換）
        default_trucks = [t for _, t in truck_map.items() if t.get('default_use', False)]
        default_total_floor_area = sum((t['width'] * t['depth']) / 1_000_000 for t in default_trucks)
        
        # 各受注を処理
        for _, order in orders_df.iterrows():
            # 製品ID取得
            try:
                product_id = order.get('product_id')
                if pd.isna(product_id):
                    continue
                product_id = int(product_id)
            except (ValueError, TypeError, KeyError):
                continue
            
            if product_id not in product_map:
                continue
            
            product = product_map[product_id]
            
            # 納期取得
            delivery_date = self._parse_date(order.get('delivery_date') or order.get('instruction_date'))
            if not delivery_date:
                continue
            
            # 容器情報取得
            container_id = product.get('used_container_id')
            if not container_id or pd.isna(container_id):
                continue
            
            try:
                container_id = int(container_id)
            except (ValueError, TypeError):
                continue
            
            container = container_map.get(container_id)
            if not container:
                continue
            
            try:
                raw_capacity = product.get('capacity')
                if raw_capacity is None or pd.isna(raw_capacity):
                    raw_capacity = 1
                capacity = max(1, int(raw_capacity))
            except Exception:
                capacity = 1

    # 旧 planned_quantity は使わず、残数量ベースに統一
            def _to_int(x, default=0):
                try:
                    import pandas as pd
                    if x is None or (hasattr(pd, "isna") and pd.isna(x)):
                        return default
                    return int(x)
                except Exception:
                    return default

            manual_fixed = False
            manual_qty = order.get('manual_planning_quantity', None)

            if manual_qty is not None and not pd.isna(manual_qty):
                manual_fixed = True
                desired_qty = _to_int(manual_qty, 0)
                shipped_done = _to_int(order.get('shipped_quantity'), 0)
                quantity = max(0, desired_qty - shipped_done)
            elif 'remaining_quantity' in getattr(order, 'index', []):
                # 1) remaining_quantity があれば最優先
                quantity = max(0, _to_int(order.get('remaining_quantity'), 0))
            else:
                # 2) order_quantity と shipped_quantity 差分を計算
                oq = _to_int(order.get('order_quantity'), 0)
                sq = order.get('shipped_quantity', None)
                if sq is not None:
                    sq = _to_int(sq, 0)
                    quantity = max(0, oq - sq)
                else:
                    # 3) 最後の手段として order_quantity
                    quantity = max(0, oq)

            # 0 以下はスキップ
            if quantity <= 0:
                continue


            remainder = quantity % capacity
            if quantity == 0:
                num_containers = 0
            else:
                num_containers = (quantity + capacity - 1) // capacity
            surplus = capacity - remainder if remainder > 0 else 0
            total_quantity = quantity
            
            # 容器ごとの底面積計算（段積み考慮）
            floor_area_per_container = (container.width * container.depth) / 1_000_000
            max_stack = getattr(container, 'max_stack', 1)
            
            if max_stack > 1 and getattr(container, 'stackable', False):
                stacked_containers = (num_containers + max_stack - 1) // max_stack
                total_floor_area_needed = floor_area_per_container * stacked_containers
            else:
                total_floor_area_needed = floor_area_per_container * num_containers
            
            total_floor_area += total_floor_area_needed
            
            # トラックIDを取得（arrival_day_offsetは後で調整）
            truck_ids_str = product.get('used_truck_ids')
            if truck_ids_str and not pd.isna(truck_ids_str):
                truck_ids = [int(tid.strip()) for tid in str(truck_ids_str).split(',')]
            else:
                truck_ids = [tid for tid, t in truck_map.items() if t.get('default_use', False)]
            
            # 納期日を積載日として使用（arrival_day_offsetは最後に調整）
            primary_loading_date = delivery_date
            
            # 営業日チェック
            if self.calendar_repo:
                for _ in range(7):
                    if self.calendar_repo.is_working_day(primary_loading_date):
                        break
                    primary_loading_date -= timedelta(days=1)
            
            # 計画期間内のみ
            if primary_loading_date and primary_loading_date in working_dates:
                date_str = primary_loading_date.strftime('%Y-%m-%d')

                # ✅ 最終的な数量チェックと補正 直した　下記アウトしたs
                final_capacity = capacity * num_containers
                if final_capacity > quantity and remainder == 0:
                    optimized_containers = max(1, quantity // capacity)
                    num_containers = optimized_containers

                daily_demands[date_str].append({
                    'product_id': product_id,
                    'product_code': product.get('product_code', ''),
                    'product_name': product.get('product_name', ''),
                    'container_id': container_id,
                    'num_containers': num_containers,
                    'total_quantity': total_quantity ,  
                    'calculated_quantity': total_quantity ,  # 計算値も同じ 
                    'capacity': capacity,
                    'remainder': remainder,  # 余りを保存
                    'surplus': surplus,  # 余剰を保存
                    'floor_area': total_floor_area_needed,
                    'floor_area_per_container': floor_area_per_container,
                    'delivery_date': delivery_date,
                    'loading_date': primary_loading_date,
                    'truck_ids': truck_ids,
                    'max_stack': max_stack,
                    'stackable': getattr(container, 'stackable', False),
                    'can_advance': False if manual_fixed else bool(product.get('can_advance', 0)),
                    'manual_fixed': manual_fixed,
                    'manual_requested_quantity': manual_qty if manual_fixed else None,
                    'is_advanced': False
                })
        # 日平均積載量を計算
        avg_floor_area = total_floor_area / len(working_dates) if working_dates else 0
                # 非デフォルトトラック使用判定
        use_non_default = avg_floor_area > default_total_floor_area
        
        return dict(daily_demands), use_non_default

    def _forward_scheduling(self, daily_demands, truck_map, container_map, 
                           working_dates, use_non_default) -> Dict:
        """
        Step2: 前倒し処理（最終日から逆順）
        各日の積載量がトラック能力を超過する場合、前倒しOK製品を前日に前倒し
        ✅ 修正: 製品ごとの利用可能トラックで判定（全トラック合計ではない）
        ✅ 最終日の容量オーバー検出と特別処理を追加
        """
        adjusted_demands = {d.strftime('%Y-%m-%d'): [] for d in working_dates}
        # 初期需要をコピー
        for date_str, demands in daily_demands.items():
            adjusted_demands[date_str] = [d.copy() for d in demands]
        # 使用可能なトラックを取得
        if use_non_default:
            available_trucks = {tid: t for tid, t in truck_map.items()}
        else:
            available_trucks = {tid: t for tid, t in truck_map.items() if t.get('default_use', False)}
        # 最終日から逆順に処理
        for i in range(len(working_dates) - 1, 0, -1):
            current_date = working_dates[i]
            prev_date = working_dates[i - 1]
            current_date_str = current_date.strftime('%Y-%m-%d')
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            # ✅ 最終日は前倒し禁止（容量オーバーでもそのまま残す）
            if current_date == working_dates[-1]:
                continue
            # ✅ 修正: トラックごとの積載状況を追跡（mm²をm²に変換）
            truck_loads = {}
            for truck_id, truck_info in available_trucks.items():
                truck_loads[truck_id] = {
                    'floor_area': 0,
                    'capacity': (truck_info['width'] * truck_info['depth']) / 1_000_000
                }
            # 当日の需要を各トラックに仮割り当て
            demands_to_forward = []
            remaining_demands = []
            for demand in adjusted_demands[current_date_str]:
                # ✅ 既に前倒しされた需要は再度前倒ししない（1日前のみルール）
                if demand.get('is_advanced', False):
                    remaining_demands.append(demand)
                    continue
                # この製品が使用できるトラックを取得
                allowed_truck_ids = demand.get('truck_ids', [])
                if not allowed_truck_ids:
                    allowed_truck_ids = list(available_trucks.keys())
                # シンプルに全てのallowed_truck_idsを使用
                valid_truck_ids = [tid for tid in allowed_truck_ids if tid in available_trucks]
                # ✅ 修正: 複数トラックへの分割積載を試みる
                remaining_demand = demand.copy()
                has_loaded_any = False  # 何か積載できたかフラグ
                for truck_id in valid_truck_ids:
                    if truck_id not in truck_loads:
                        continue
                    remaining_capacity = truck_loads[truck_id]['capacity'] - truck_loads[truck_id]['floor_area']
                    if remaining_demand['floor_area'] <= remaining_capacity:
                        # 全量積載可能
                        truck_loads[truck_id]['floor_area'] += remaining_demand['floor_area']
                        has_loaded_any = True
                        remaining_demand['floor_area'] = 0
                        remaining_demand['num_containers'] = 0
                        break
                    elif remaining_capacity > 0:
                        # 一部のみ積載可能 - 分割
                        container = container_map.get(demand['container_id'])
                        if container:
                            floor_area_per_container = (container.width * container.depth) / 1_000_000
                            max_stack = getattr(container, 'max_stack', 1)
                            # 段積み考慮で積載可能な容器数を計算
                            if max_stack > 1 and getattr(container, 'stackable', False):
                                max_stacks = int(remaining_capacity / floor_area_per_container)
                                loadable_containers = max_stacks * max_stack
                            else:
                                loadable_containers = int(remaining_capacity / floor_area_per_container)
                            if loadable_containers > 0:
                                # 分割積載
                                if max_stack > 1 and getattr(container, 'stackable', False):
                                    stacked = (loadable_containers + max_stack - 1) // max_stack
                                    loadable_floor_area = floor_area_per_container * stacked
                                else:
                                    loadable_floor_area = floor_area_per_container * loadable_containers
                                truck_loads[truck_id]['floor_area'] += loadable_floor_area
                                remaining_demand['floor_area'] -= loadable_floor_area
                                remaining_demand['num_containers'] -= loadable_containers
                                has_loaded_any = True
                # 積載結果を判定
                if remaining_demand['num_containers'] <= 0:
                    # 全量積載成功 - そのまま残す（この日に積載完了）
                    remaining_demands.append(demand)
                elif has_loaded_any:
                    # 一部積載できた - 積載できた分は記録、残りは前倒しor積み残し
                    if remaining_demand['num_containers'] < demand['num_containers']:
                        # 積載できた分を記録
                        loaded_demand = demand.copy()
                        loaded_demand['num_containers'] = demand['num_containers'] - remaining_demand['num_containers']
                        loaded_demand['total_quantity'] = loaded_demand['num_containers'] * demand['capacity'] - remaining_demand['surplus']  # 直した
                        loaded_demand['floor_area'] = demand['floor_area'] - remaining_demand['floor_area']
                        remaining_demands.append(loaded_demand)
                    # 残りを前倒し候補に
                    if demand.get('can_advance', False):
                        remaining_demand['is_advanced'] = True
                        remaining_demand['loading_date'] = prev_date
                        demands_to_forward.append(remaining_demand)
                    else:
                        # 前倒し不可 - 積み残し
                        remaining_demands.append(remaining_demand)
                else:
                    # 全く積載できなかった - 前倒し候補
                    if demand.get('can_advance', False):
                        demand['is_advanced'] = True
                        demand['loading_date'] = prev_date
                        demands_to_forward.append(demand)
                    else:
                        # 前倒し不可 - そのまま残す（警告は後で出る）
                        remaining_demands.append(demand)
            # 前日に追加
            if demands_to_forward:
                adjusted_demands[prev_date_str].extend(demands_to_forward)
            # 当日は残った需要のみ
            adjusted_demands[current_date_str] = remaining_demands
        return adjusted_demands

    def _create_daily_loading_plan(self, demands, truck_map, container_map, 
                                   product_map, use_non_default, current_date=None) -> Dict:
        """
        Step3: 日次積載計画作成
        製品ごとに適切なトラックを選択して積載
        ✅ 修正: 分割積載時の数量計算を厳密化
        """
        truck_plans = {}
        remaining_demands = []
        warnings = []
        # 使用可能なトラックを取得
        if use_non_default:
            available_trucks = {tid: t for tid, t in truck_map.items()}
        else:
            available_trucks = {tid: t for tid, t in truck_map.items() if t.get('default_use', False)}
        # トラック状態を初期化（mm²をm²に変換）
        truck_states = {}
        for truck_id, truck_info in available_trucks.items():
            truck_floor_area = (truck_info['width'] * truck_info['depth']) / 1_000_000
            truck_states[truck_id] = {
                'truck_id': truck_id,
                'truck_name': truck_info['name'],
                'truck_info': truck_info,
                'loaded_items': [],
                'remaining_floor_area': truck_floor_area,
                'total_floor_area': truck_floor_area,
                'loaded_container_ids': set(),
                'priority_products': self._get_priority_products(truck_info),
                'is_default': truck_info.get('default_use', False)
            }
        # 製品を優先度順にソート
        sorted_demands = self._sort_demands_by_priority(demands, truck_states)
        
        # 利用可能なトラックをフィルタリング（納期に間に合わないトラックを除外）
        filtered_truck_states = {}
        for truck_id, state in truck_states.items():
            truck_info = truck_map[truck_id]
            arrival_day_offset = truck_info.get('arrival_day_offset', 0)
            # 翌日到着のトラックは当日納期の製品には使用不可
            if arrival_day_offset > 0:
                state['unavailable_for_same_day'] = True
            filtered_truck_states[truck_id] = state
            
        # 各製品を適切なトラックに積載
        for demand in sorted_demands:
            loaded = False
            # ✅ 元の総注文数量を保存（検証用）
            original_total_quantity = demand['total_quantity']
            original_num_containers = demand['num_containers']
            # 製品のトラック制約を取得
            allowed_truck_ids = demand.get('truck_ids', [])
            if not allowed_truck_ids:
                allowed_truck_ids = list(available_trucks.keys())
            # 制約に合うトラックのみを対象（順序を保持）
            candidate_trucks = [tid for tid in allowed_truck_ids if tid in truck_states]
            if not candidate_trucks:
                # 候補トラックがない場合、積み残し
                remaining_demands.append(demand)
                continue
            # 到着日に間に合うトラックのみ残す
            demand_delivery_date = demand.get('delivery_date')
            candidate_trucks = [
                tid for tid in candidate_trucks
                if self._can_arrive_on_time(truck_map[tid], current_date, demand_delivery_date)
            ]
            if not candidate_trucks:
                remaining_demands.append(demand)
                continue
            # 候補トラックを優先順位でソート
            candidate_trucks = self._sort_candidate_trucks(
                candidate_trucks, demand, truck_states, truck_map, current_date
            )
            # トラックに積載を試みる
            remaining_demand = demand.copy()
            # ✅ 改善: 複数トラックへの分割積載を積極的に試みる
            for truck_id in candidate_trucks:
                if remaining_demand['num_containers'] <= 0:
                    # 全量積載完了
                    break
                truck_state = truck_states[truck_id]
                truck_info = truck_map[truck_id]
                container_id = remaining_demand['container_id']
                
                # 納期チェック（シンプル化：current_dateから到着可能かのみチェック）
                demand_delivery_date = remaining_demand.get('delivery_date')
                if not self._can_arrive_on_time(truck_info, current_date, demand_delivery_date):
                    continue
                # 同じ容器が既に積載されているか確認（段積み統合用）
                same_container_items = [item for item in truck_state['loaded_items'] 
                                       if item['container_id'] == container_id]
                if same_container_items:
                    # 同じ容器が既にある場合、段積みとして統合できるか確認
                    container = container_map.get(container_id)
                    if container and getattr(container, 'stackable', False):
                        max_stack = getattr(container, 'max_stack', 1)
                        floor_area_per_container = (container.width * container.depth) / 1_000_000
                        # 既存の容器数を計算（同じ容器IDの全製品）
                        existing_containers = sum(item['num_containers'] for item in same_container_items)
                        new_total_containers = existing_containers + remaining_demand['num_containers']
                        # 既存の配置数
                        existing_stacks = (existing_containers + max_stack - 1) // max_stack
                        # 新しい配置数
                        new_stacks = (new_total_containers + max_stack - 1) // max_stack
                        # 追加で必要な配置数
                        additional_stacks = new_stacks - existing_stacks
                        additional_floor_area = additional_stacks * floor_area_per_container
                        if additional_floor_area <= truck_state['remaining_floor_area']:
                            # 段積みとして統合可能
                            truck_state['loaded_items'].append(remaining_demand)
                            truck_state['remaining_floor_area'] -= additional_floor_area
                            loaded = True
                            break
                # 通常の積載チェック
                if remaining_demand['floor_area'] <= truck_state['remaining_floor_area']:
                    # 全量積載可能
                    loaded_item = remaining_demand.copy()
                    # ✅ 数量の整合性を確認
                    expected_quantity = min(loaded_item['num_containers'] * loaded_item['capacity'] - loaded_item['surplus'], # 直した
                                         original_total_quantity)
                    if loaded_item['total_quantity'] != expected_quantity:
                        print(f"      🔄 数量を補正: {loaded_item['total_quantity']} → {expected_quantity}")
                    loaded_item['total_quantity'] = expected_quantity
                    truck_state['loaded_items'].append(loaded_item)
                    truck_state['remaining_floor_area'] -= remaining_demand['floor_area']
                    truck_state['loaded_container_ids'].add(remaining_demand['container_id'])
                    loaded = True
                    remaining_demand['num_containers'] = 0
                    break
                elif truck_state['remaining_floor_area'] > 0:
                    # 一部積載可能（分割）
                    container = container_map.get(remaining_demand['container_id'])
                    if container:
                        floor_area_per_container = (container.width * container.depth) / 1_000_000
                        max_stack = getattr(container, 'max_stack', 1)
                        # 段積み考慮で積載可能な容器数を計算
                        if max_stack > 1 and getattr(container, 'stackable', False):
                            max_stacks = int(truck_state['remaining_floor_area'] / floor_area_per_container)
                            loadable_containers = max_stacks * max_stack
                        else:
                            loadable_containers = int(truck_state['remaining_floor_area'] / floor_area_per_container)
                        if loadable_containers > 0 and loadable_containers < remaining_demand['num_containers']:
                            # 分割積載の数量計算
                            capacity = remaining_demand.get('capacity', 1)
                            original_demand_quantity = demand.get('total_quantity', 0)
                            remaining_quantity = remaining_demand.get('total_quantity', 0)
                            
                            # 積載可能数量の計算（最大容量と残り数量の小さい方）
                            max_loadable_quantity = min(loadable_containers * capacity, remaining_quantity)
                            loadable_quantity = min(max_loadable_quantity, remaining_quantity)
                            
                            # 容器数を再計算（過剰な容器を割り当てない）
                            loadable_containers = (loadable_quantity + capacity - 1) // capacity
                            # 段積み後の底面積
                            if max_stack > 1 and getattr(container, 'stackable', False):
                                stacked = (loadable_containers + max_stack - 1) // max_stack
                                loadable_floor_area = floor_area_per_container * stacked
                            else:
                                loadable_floor_area = floor_area_per_container * loadable_containers
                            
                            # 数量の整合性チェックと補正
                            calculated_quantity = loadable_containers * demand['capacity']
                            actual_quantity = min(calculated_quantity, original_demand_quantity)
                            
                            # ✅ 分割して積載（loaded_itemとして追加）
                            actual_quantity = min(loadable_containers * capacity - demand['surplus'], original_demand_quantity - demand['surplus']) # 直した
                            loaded_item = {
                                'product_id': demand['product_id'],
                                'product_code': demand['product_code'],
                                'product_name': demand['product_name'],
                                'container_id': demand['container_id'],
                                'container_name': container.name,
                                'num_containers': loadable_containers,  # ← 積載できた容器数
                                'total_quantity': actual_quantity,     # ✅ 注文数量を超えない
                                'floor_area': loadable_floor_area,
                                'floor_area_per_container': floor_area_per_container,
                                'delivery_date': demand['delivery_date'],
                                'loading_date': demand.get('loading_date'),
                                'capacity': capacity,
                                'remainder': demand.get('remainder', 0),
                                'surplus': demand.get('surplus', 0),
                                'can_advance': demand.get('can_advance', False),
                                'is_advanced': demand.get('is_advanced', False),
                                'truck_ids': demand.get('truck_ids', []),
                                'stackable': getattr(container, 'stackable', False),
                                'max_stack': max_stack
                            }
                            # 数量が容器数×容量と元の注文数量の小さい方と一致するか確認
                            expected_quantity = min(loaded_item['num_containers'] * capacity - loaded_item['surplus'], original_demand_quantity - loaded_item['surplus'])
                            truck_state['loaded_items'].append(loaded_item)
                            truck_state['remaining_floor_area'] -= loadable_floor_area
                            truck_state['loaded_container_ids'].add(demand['container_id'])
                            # ✅ 残りを更新（必ず容器数ベースで再計算）
                            remaining_demand['num_containers'] -= loadable_containers
                            remaining_demand['total_quantity'] = remaining_demand['num_containers'] * demand['capacity'] - remaining_demand['surplus'] # 直した
                            remaining_demand['floor_area'] -= loadable_floor_area
                            # 残り数量が元の総数量を超えていないかの確認は省略（計算ロジックで保証）
                            # 次のトラックへ継続（まだ残りがあれば）
                            if remaining_demand['num_containers'] > 0:   # ここまで直した
                                continue
                            else:
                                loaded = True
                                break
            # ✅ フォールバック: 低稼働率トラックへの再配置
            if not loaded and remaining_demand['num_containers'] > 0:
                low_utilization_threshold = 0.7
                fallback_candidates = [
                    state for state in truck_states.values()
                    if state['total_floor_area'] > 0 and
                    (1 - state['remaining_floor_area'] / state['total_floor_area']) < low_utilization_threshold
                ]
                fallback_candidates.sort(key=lambda s: s['remaining_floor_area'], reverse=True)
                for truck_state in fallback_candidates:
                    if remaining_demand['num_containers'] <= 0:
                        break
                    candidate_container = container_map.get(remaining_demand['container_id'])
                    if not candidate_container:
                        continue
                    floor_area_per_container = (candidate_container.width * candidate_container.depth) / 1_000_000
                    if floor_area_per_container <= 0:
                        continue
                    max_stack = getattr(candidate_container, 'max_stack', 1)
                    stackable = getattr(candidate_container, 'stackable', False)
                    available_area = truck_state['remaining_floor_area']
                    if available_area <= 0:
                        continue
                    if stackable and max_stack > 1:
                        nominal_slots = int(available_area / floor_area_per_container)
                        loadable_containers = nominal_slots * max_stack
                        stacked = (loadable_containers + max_stack - 1) // max_stack if loadable_containers > 0 else 0
                        loadable_floor_area = floor_area_per_container * stacked
                    else:
                        loadable_containers = int(available_area / floor_area_per_container)
                        loadable_floor_area = loadable_containers * floor_area_per_container
                    if loadable_containers <= 0:
                        continue
                    loadable_containers = min(loadable_containers, remaining_demand['num_containers'])
                    capacity = remaining_demand.get('capacity', 1)
                    # 数量は必ず「容器数×容量」で計算
                    loadable_quantity = loadable_containers * capacity
                    if stackable and max_stack > 1:
                        stacked = (loadable_containers + max_stack - 1) // max_stack
                        loadable_floor_area = floor_area_per_container * stacked
                    else:
                        loadable_floor_area = floor_area_per_container * loadable_containers
                    fallback_item = {
                        'product_id': remaining_demand['product_id'],
                        'product_code': remaining_demand['product_code'],
                        'product_name': remaining_demand.get('product_name', ''),
                        'container_id': remaining_demand['container_id'],
                        'container_name': candidate_container.name,
                        'num_containers': loadable_containers,
                        'remainder': demand.get('remainder', 0),
                        'surplus': demand.get('surplus', 0),
                        'total_quantity': loadable_containers * demand['capacity'] - demand['surplus'],  # ✅ 必ず「容器数×容量」-余りで計算 直した
                        'floor_area': loadable_floor_area,
                        'floor_area_per_container': floor_area_per_container,
                        'delivery_date': remaining_demand['delivery_date'],
                        'loading_date': remaining_demand.get('loading_date'),
                        'capacity': capacity,
                        'can_advance': remaining_demand.get('can_advance', False),
                        'is_advanced': remaining_demand.get('is_advanced', False),
                        'truck_ids': remaining_demand.get('truck_ids', []),
                        'stackable': stackable,
                        'max_stack': max_stack
                    }
                    # 数量計算の検証は省略（計算ロジックで保証）
                    truck_state['loaded_items'].append(fallback_item)
                    truck_state['remaining_floor_area'] -= loadable_floor_area
                    truck_state['loaded_container_ids'].add(remaining_demand['container_id'])
                    remaining_demand['num_containers'] -= loadable_containers
                    remaining_demand['total_quantity'] = remaining_demand['num_containers'] * demand['capacity'] - demand['surplus']
                    remaining_demand['floor_area'] -= loadable_floor_area
                    loaded = True
                if remaining_demand['num_containers'] > 0:
                    # 最終検証: 積み残し数量が正しいか確認
                    expected_remaining_quantity = remaining_demand['num_containers'] * remaining_demand['capacity'] - remaining_demand['surplus']
                    if remaining_demand['total_quantity'] != expected_remaining_quantity:
                        remaining_demand['total_quantity'] = expected_remaining_quantity
                    remaining_demands.append(remaining_demand)
        # トラックプランを作成（積載があるトラックのみ）
        final_truck_plans = []
        for truck_id, truck_state in truck_states.items():
            if truck_state['loaded_items']:
                # 各loaded_itemの数量を検証
                for item in truck_state['loaded_items']:
                    expected_quantity = item['num_containers'] * item.get('capacity', 1)- item.get('surplus', 0)
                    if item['total_quantity'] != expected_quantity:
                        item['total_quantity'] = expected_quantity
                # 積載率を計算（容器別に段積み考慮）
                container_totals = {}  # container_id -> 容器数の合計
                # 容器別に集計
                for item in truck_state['loaded_items']:
                    container_id = item['container_id']
                    if container_id not in container_totals:
                        container_totals[container_id] = {
                            'num_containers': 0,
                            'floor_area_per_container': item['floor_area_per_container'],
                            'stackable': item.get('stackable', False),
                            'max_stack': item.get('max_stack', 1)
                        }
                    container_totals[container_id]['num_containers'] += item['num_containers']
                # 容器別に底面積を計算
                total_loaded_area = 0
                for container_id, info in container_totals.items():
                    if info['stackable'] and info['max_stack'] > 1:
                        # 段積み可能
                        stacked_containers = (info['num_containers'] + info['max_stack'] - 1) // info['max_stack']
                        container_area = info['floor_area_per_container'] * stacked_containers
                    else:
                        # 段積みなし
                        container_area = info['floor_area_per_container'] * info['num_containers']
                    total_loaded_area += container_area
                utilization_rate = round(total_loaded_area / truck_state['total_floor_area'] * 100, 1)
                truck_plan = {
                    'truck_id': truck_id,
                    'truck_name': truck_state['truck_name'],
                    'loaded_items': truck_state['loaded_items'],
                    'utilization': {
                        'floor_area_rate': utilization_rate,
                        'volume_rate': utilization_rate,
                        'weight_rate': 0
                    }
                }
                final_truck_plans.append(truck_plan)
        # 積み残し警告
        if remaining_demands:
            for demand in remaining_demands:
                can_advance = demand.get('can_advance', False)
                is_final_day_overflow = demand.get('final_day_overflow', False)
                if is_final_day_overflow:
                    # 最終日の容量オーバー - 特別警告
                    warnings.append(
                        f"🚨 最終日容量オーバー: {demand['product_code']} ({demand['num_containers']}容器={demand['total_quantity']}個) ※非デフォルトトラック追加が必要"
                    )
                elif can_advance:
                    warnings.append(
                        f"⚠ 積み残し: {demand['product_code']} ({demand['num_containers']}容器={demand['total_quantity']}個) ※前倒し配送可能"
                    )
                else:
                    warnings.append(
                        f"❌ 積み残し: {demand['product_code']} ({demand['num_containers']}容器={demand['total_quantity']}個) ※前倒し不可"
                    )
        return {
            'trucks': final_truck_plans,
            'total_trips': len(final_truck_plans),
            'warnings': warnings,
            'remaining_demands': remaining_demands
        }

    def _get_priority_products(self, truck_info) -> List[str]:
        """トラックの優先積載製品を取得"""
        priority_products_str = truck_info.get('priority_product_codes') or truck_info.get('priority_products', '')
        if priority_products_str and not pd.isna(priority_products_str):
            return [p.strip() for p in str(priority_products_str).split(',')]
        return []

    def _sort_demands_by_priority(self, demands, truck_states):
        """
        製品を優先度順にソート
        優先順位:
        1. 前倒しされた製品（最優先）
        2. トラック制約が1つのみの製品
        3. 優先積載製品に指定されている製品
        4. トラック制約がある製品
        5. その他
        """
        def get_priority(demand):
            product_code = demand['product_code']
            truck_ids = demand.get('truck_ids', [])
            is_advanced = demand.get('is_advanced', False)
            # 1. 前倒しされた製品（最優先）
            if is_advanced:
                return (0, truck_ids[0] if truck_ids else 0, product_code)
            # 2. トラック制約が1つのみの製品
            if truck_ids and len(truck_ids) == 1:
                return (1, truck_ids[0], product_code)
            # 3. 優先積載製品に指定されている場合
            for truck_id, truck_state in truck_states.items():
                if product_code in truck_state['priority_products']:
                    return (2, truck_id, product_code)
            # 4. トラック制約がある場合
            if truck_ids:
                return (3, truck_ids[0], product_code)
            # 5. その他
            return (4, 0, product_code)
        return sorted(demands, key=get_priority)

    def _sort_candidate_trucks(self, candidate_trucks, demand, truck_states, truck_map, current_date=None):
        """候補トラックを優先順位でソート
        優先順位：
        0. 納期に間に合うトラック（最優先）
        1. 製品のused_truck_idsの順序
        2. 優先積載製品に指定されている
        3. 同容器が既に積載されている
        4. 空き容量が大きい
        """
        product_code = demand['product_code']
        container_id = demand['container_id']
        truck_ids = demand.get('truck_ids', [])
        delivery_date = demand.get('delivery_date')
        def get_truck_priority(truck_id):
            truck_state = truck_states[truck_id]
            truck_info = truck_map[truck_id]
            
            # 0. 納期に間に合うトラックを最優先
            if current_date and delivery_date:
                if not self._can_arrive_on_time(truck_info, current_date, delivery_date):
                    return (1, 9999, 1, 1, 0)  # 納期に間に合わないトラックは最低優先度
            
            # 1. 製品のused_truck_idsの順序を優先（インデックスが小さいほど優先）
            if truck_ids and truck_id in truck_ids:
                truck_priority_index = truck_ids.index(truck_id)
            else:
                truck_priority_index = 9999  # リストにない場合は低優先度
            # 2. 優先積載製品に指定されている
            if product_code in truck_state['priority_products']:
                priority_product_flag = 0
            else:
                priority_product_flag = 1
            # 3. 同容器が既に積載されている
            if container_id in truck_state['loaded_container_ids']:
                same_container_flag = 0
            else:
                same_container_flag = 1
            # 4. 空き容量（大きい方が優先）
            remaining_area = truck_state['remaining_floor_area']
            # 5. 現在の利用率（低い方を優先）
            utilized_area = truck_state['total_floor_area'] - truck_state['remaining_floor_area']
            utilization_rate = utilized_area / truck_state['total_floor_area'] if truck_state['total_floor_area'] else 0
            return (
                truck_priority_index,
                priority_product_flag,
                same_container_flag,
                -remaining_area,
                utilization_rate
            )
        return sorted(candidate_trucks, key=get_truck_priority)

    def _parse_date(self, date_value):
        """日付を解析"""
        if not date_value:
            return None
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except:
                try:
                    return datetime.strptime(date_value, '%Y/%m/%d').date()
                except:
                    return None
        if hasattr(date_value, 'date'):
            return date_value.date()
        return None
    def _get_remaining_quantity(self, order) -> int:
        def to_int(v, default=0):
            try:
                import pandas as pd
                if v is None or (hasattr(pd, "isna") and pd.isna(v)):
                    return default
                return int(v)
            except Exception:
                return default

        # 1) remaining_quantity 優先
        if 'remaining_quantity' in getattr(order, 'index', []):
            rem = to_int(order.get('remaining_quantity'), 0)
            return max(0, rem)

        # 2) order - shipped
        oq = order.get('order_quantity', None)
        sq = order.get('shipped_quantity', None)
        if oq is not None and sq is not None:
            return max(0, to_int(oq) - to_int(sq))

        # 3) 最後の手段として order_quantity（planned_quantity は使わない）
        return max(0, to_int(order.get('order_quantity'), 0))
 

    def _relocate_remaining_demands(self, remaining_demands, daily_plans, truck_map, 
                                    container_map, working_dates, use_non_default):
        """
        Step4: 積み残しを他のトラック候補で再配置
        各積み残しについて、他のトラック候補の積載日に空きがあれば再配置
        """
        # Step4: 積み残し再配置開始
        for demand in remaining_demands:
            relocated = False
            truck_ids = demand.get('truck_ids', [])
            original_loading_date = demand.get('loading_date')
            
            # 全てのトラック候補を試す
            for truck_id in truck_ids:
                # 同じ日の同じトラックは既に試したのでスキップ
                target_date = original_loading_date
                if not target_date:
                    continue
                target_date_str = target_date.strftime('%Y-%m-%d')
                
                # 計画期間内かチェック
                if target_date not in working_dates:
                    continue
                # その日の計画を取得
                if target_date_str not in daily_plans:
                    continue
                day_plan = daily_plans[target_date_str]
                # 使用可能なトラックを取得
                if use_non_default:
                    available_trucks = {tid: t for tid, t in truck_map.items()}
                else:
                    available_trucks = {tid: t for tid, t in truck_map.items() if t.get('default_use', False)}
                # このトラックが使用可能かチェック
                if truck_id not in available_trucks:
                    continue
                # このトラックの状態を確認（mm²をm²に変換）
                truck_info = truck_map[truck_id]
                if not self._can_arrive_on_time(truck_info, target_date, demand.get('delivery_date')):
                    continue
                truck_name = truck_info['name']
                truck_floor_area = (truck_info['width'] * truck_info['depth']) / 1_000_000
                # 既存のトラックプランを探す
                target_truck_plan = None
                for truck_plan in day_plan['trucks']:
                    if truck_plan['truck_id'] == truck_id:
                        target_truck_plan = truck_plan
                        break
                # トラックプランが存在する場合、残り容量を計算
                if target_truck_plan:
                    # 既存の積載量を計算
                    loaded_area = 0
                    container_totals = {}
                    for item in target_truck_plan['loaded_items']:
                        container_id = item['container_id']
                        if container_id not in container_totals:
                            container_totals[container_id] = {
                                'num_containers': 0,
                                'floor_area_per_container': item['floor_area_per_container'],
                                'stackable': item.get('stackable', False),
                                'max_stack': item.get('max_stack', 1)
                            }
                        container_totals[container_id]['num_containers'] += item['num_containers']
                    for container_id, info in container_totals.items():
                        if info['stackable'] and info['max_stack'] > 1:
                            stacked_containers = (info['num_containers'] + info['max_stack'] - 1) // info['max_stack']
                            container_area = info['floor_area_per_container'] * stacked_containers
                        else:
                            container_area = info['floor_area_per_container'] * info['num_containers']
                        loaded_area += container_area
                    remaining_area = truck_floor_area - loaded_area
                else:
                    # トラックプランが存在しない場合、全容量が空き
                    remaining_area = truck_floor_area
                # 積載可能かチェック
                if demand['floor_area'] <= remaining_area:
                    # 積載可能
                    loaded_item = demand.copy()
                    loaded_item['loading_date'] = target_date
                    # 数量検証
                    expected_quantity = loaded_item['num_containers'] * loaded_item['capacity']
                    if loaded_item['total_quantity'] != expected_quantity:
                        loaded_item['total_quantity'] = expected_quantity
                    if original_loading_date:
                        loaded_item.setdefault('original_date', original_loading_date)
                    if target_truck_plan:
                        # 既存のトラックプランに追加
                        target_truck_plan['loaded_items'].append(loaded_item)
                        # 積載率を再計算
                        new_loaded_area = loaded_area + demand['floor_area']
                        new_utilization_rate = round(new_loaded_area / truck_floor_area * 100, 1)
                        target_truck_plan['utilization']['floor_area_rate'] = new_utilization_rate
                        target_truck_plan['utilization']['volume_rate'] = new_utilization_rate
                    else:
                        # 新しいトラックプランを作成
                        new_utilization_rate = round(demand['floor_area'] / truck_floor_area * 100, 1)
                        new_truck_plan = {
                            'truck_id': truck_id,
                            'truck_name': truck_name,
                            'loaded_items': [loaded_item],
                            'utilization': {
                                'floor_area_rate': new_utilization_rate,
                                'volume_rate': new_utilization_rate,
                                'weight_rate': 0
                            }
                        }
                        day_plan['trucks'].append(new_truck_plan)
                        day_plan['total_trips'] += 1
                    # 元の日の警告を削除
                    original_date = demand.get('loading_date')
                    if original_date:
                        original_date_str = original_date.strftime('%Y-%m-%d')
                        if original_date_str in daily_plans:
                            original_plan = daily_plans[original_date_str]
                            # 積み残し警告を削除
                            product_code = demand['product_code']
                            num_containers = demand['num_containers']
                            original_plan['warnings'] = [
                                w for w in original_plan['warnings']
                                if not (product_code in w and f"{num_containers}容器" in w)
                            ]
                            # remaining_demandsからも削除
                            if 'remaining_demands' in original_plan:
                                original_plan['remaining_demands'] = [
                                    d for d in original_plan['remaining_demands']
                                    if not (d['product_code'] == product_code and d['num_containers'] == num_containers)
                                ]
                    relocated = True
                    break
        return daily_plans

    def _forward_remaining_demands(self, daily_plans, truck_map, container_map, 
                                   working_dates, use_non_default):
        """
        Step5: 積み残しを前倒し配送
        各日の積み残しを確認し、前倒し可能な製品を前日に移動
        """
        # 使用可能なトラックを取得
        if use_non_default:
            available_trucks = {tid: t for tid, t in truck_map.items()}
        else:
            available_trucks = {tid: t for tid, t in truck_map.items() if t.get('default_use', False)}
        # 最終日から逆順に処理
        for i in range(len(working_dates) - 1, 0, -1):
            current_date = working_dates[i]
            prev_date = working_dates[i - 1]
            current_date_str = current_date.strftime('%Y-%m-%d')
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            if current_date_str not in daily_plans:
                continue
            current_plan = daily_plans[current_date_str]
            prev_plan = daily_plans.get(prev_date_str)
            if not prev_plan:
                continue
            # 積み残しを確認
            remaining_demands = current_plan.get('remaining_demands', [])
            if not remaining_demands:
                continue
            # 前倒し可能な積み残しを抽出
            demands_to_forward = []
            for demand in remaining_demands:
                # 前倒し可能かチェック
                if not demand.get('can_advance', False):
                    continue
                # 数量検証
                expected_quantity = demand['num_containers'] * demand['capacity']
                if demand['total_quantity'] != expected_quantity:
                    demand['total_quantity'] = expected_quantity
                # この製品が使用できるトラックを取得
                allowed_truck_ids = demand.get('truck_ids', [])
                if not allowed_truck_ids:
                    allowed_truck_ids = list(available_trucks.keys())
                # 前日の各トラックの空き容量を確認
                for truck_id in allowed_truck_ids:
                    if truck_id not in available_trucks:
                        continue
                    # 前日のこのトラックの状態を確認（mm²をm²に変換）
                    truck_info = truck_map[truck_id]
                    if not self._can_arrive_on_time(truck_info, prev_date, demand.get('delivery_date')):
                        continue
                    truck_floor_area = (truck_info['width'] * truck_info['depth']) / 1_000_000
                    # 既存のトラックプランを探す
                    target_truck_plan = None
                    for truck_plan in prev_plan['trucks']:
                        if truck_plan['truck_id'] == truck_id:
                            target_truck_plan = truck_plan
                            break
                    # 残り容量を計算
                    if target_truck_plan:
                        loaded_area = 0
                        container_totals = {}
                        for item in target_truck_plan['loaded_items']:
                            container_id = item['container_id']
                            if container_id not in container_totals:
                                container_totals[container_id] = {
                                    'num_containers': 0,
                                    'floor_area_per_container': item['floor_area_per_container'],
                                    'stackable': item.get('stackable', False),
                                    'max_stack': item.get('max_stack', 1)
                                }
                            container_totals[container_id]['num_containers'] += item['num_containers']
                        for container_id, info in container_totals.items():
                            if info['stackable'] and info['max_stack'] > 1:
                                stacked_containers = (info['num_containers'] + info['max_stack'] - 1) // info['max_stack']
                                container_area = info['floor_area_per_container'] * stacked_containers
                            else:
                                container_area = info['floor_area_per_container'] * info['num_containers']
                            loaded_area += container_area
                        remaining_area = truck_floor_area - loaded_area
                    else:
                        # トラックプランが存在しない場合、新規作成が必要
                        remaining_area = truck_floor_area
                    # 積載可能かチェック
                    demand_floor_area = demand['floor_area']
                    if demand_floor_area <= remaining_area:
                        # 積載可能 - 前倒し実行
                        container = container_map.get(demand['container_id'])
                        if not container:
                            continue
                        # 前日のトラックプランに追加
                        if not target_truck_plan:
                            # 新規トラックプラン作成
                            target_truck_plan = {
                                'truck_id': truck_id,
                                'truck_name': truck_info['name'],
                                'loaded_items': [],
                                'utilization': {'floor_area_rate': 0, 'volume_rate': 0, 'weight_rate': 0}
                            }
                            prev_plan['trucks'].append(target_truck_plan)
                            prev_plan['total_trips'] = len(prev_plan['trucks'])
                        # アイテムを追加
                        capacity = demand['capacity']
                        expected_quantity = demand['num_containers'] * capacity
                        target_truck_plan['loaded_items'].append({
                            'product_id': demand['product_id'],
                            'product_code': demand['product_code'],
                            'product_name': demand.get('product_name', ''),
                            'container_id': demand['container_id'],
                            'container_name': container.name,
                            'num_containers': demand['num_containers'],
                            'total_quantity': expected_quantity,
                            'floor_area_per_container': demand['floor_area'] / demand['num_containers'],
                            'delivery_date': demand['delivery_date'],
                            'loading_date': prev_date,
                            'is_advanced': True,  # 前倒しフラグ
                            'stackable': container.stackable,
                            'max_stack': container.max_stack,
                            'capacity': capacity
                        })
                        # 積載率を再計算
                        self._recalculate_utilization(target_truck_plan, truck_info, container_map)
                        # 前倒し成功を記録
                        demands_to_forward.append(demand)
                        # 当日の警告を削除
                        product_code = demand['product_code']
                        num_containers = demand['num_containers']
                        current_plan['warnings'] = [
                            w for w in current_plan['warnings']
                            if not (product_code in w and f"{num_containers}容器" in w)
                        ]
                        break  # このdemandは処理完了
            # 前倒ししたdemandを積み残しリストから削除
            if demands_to_forward:
                current_plan['remaining_demands'] = [
                    d for d in remaining_demands
                    if d not in demands_to_forward
                ]

    def _recalculate_utilization(self, truck_plan, truck_info, container_map):
        """トラックの積載率を再計算（mm²をm²に変換）"""
        truck_floor_area = (truck_info['width'] * truck_info['depth']) / 1_000_000
        truck_volume = (truck_info['width'] * truck_info['depth'] * truck_info['height']) / 1_000_000_000
        truck_max_weight = truck_info['max_weight']
        loaded_area = 0
        loaded_volume = 0
        loaded_weight = 0
        container_totals = {}
        # 数量検証しながら集計
        for item in truck_plan['loaded_items']:
            container_id = item['container_id']
            # 数量検証
            expected_quantity = item['num_containers'] * item.get('capacity', 1)
            if item['total_quantity'] != expected_quantity:
                item['total_quantity'] = expected_quantity
            if container_id not in container_totals:
                container = container_map.get(container_id)
                if not container:
                    continue
                container_totals[container_id] = {
                    'num_containers': 0,
                    'floor_area_per_container': item['floor_area_per_container'],
                    'volume_per_container': (container.width * container.depth * container.height) / 1_000_000_000,
                    'weight_per_container': container.max_weight,
                    'stackable': container.stackable,
                    'max_stack': container.max_stack
                }
            container_totals[container_id]['num_containers'] += item['num_containers']
        for container_id, info in container_totals.items():
            if info['stackable'] and info['max_stack'] > 1:
                # 段積み可能
                stacked_containers = (info['num_containers'] + info['max_stack'] - 1) // info['max_stack']
                container_area = info['floor_area_per_container'] * stacked_containers
            else:
                # 段積みなし
                container_area = info['floor_area_per_container'] * info['num_containers']
            loaded_area += container_area
            loaded_volume += info['volume_per_container'] * info['num_containers']
            loaded_weight += info['weight_per_container'] * info['num_containers']
        truck_plan['utilization'] = {
            'floor_area_rate': round(loaded_area / truck_floor_area * 100, 1) if truck_floor_area > 0 else 0,
            'volume_rate': round(loaded_volume / truck_volume * 100, 1) if truck_volume > 0 else 0,
            'weight_rate': round(loaded_weight / truck_max_weight * 100, 1) if truck_max_weight > 0 else 0
        }

    def _relocate_to_next_days(self, daily_plans, truck_map, container_map, 
                               working_dates, use_non_default):
        """
        Step6: 前日特便配送
        前倒しできなかった積み残しは前日特便！非デフォルトトラックを出す
        非デフォルトトラックは翌日着のため、前倒しとならない
        """
        # 非デフォルトトラックを取得
        non_default_trucks = {tid: t for tid, t in truck_map.items() if not t.get('default_use', False)}
        if not non_default_trucks:
            # 非デフォルトトラックがない場合は何もしない
            return
        # 各日の積み残しを確認
        for i in range(len(working_dates)):
            current_date = working_dates[i]
            current_date_str = current_date.strftime('%Y-%m-%d')
            if current_date_str not in daily_plans:
                continue
            current_plan = daily_plans[current_date_str]
            remaining_demands = current_plan.get('remaining_demands', [])
            if not remaining_demands:
                continue
            # 前日に非デフォルトトラック（特便）を出す
            for demand in list(remaining_demands):
                relocated = False
                # 数量検証
                expected_quantity = demand['num_containers'] * demand['capacity']
                if demand['total_quantity'] != expected_quantity:
                    demand['total_quantity'] = expected_quantity
                # ✅ 特便は緊急対応のため、トラック制約を無視して全非デフォルトトラックを使用可能
                candidate_trucks = list(non_default_trucks.keys())
                if not candidate_trucks:
                    continue
                # 各非デフォルトトラック候補を試す
                for truck_id in candidate_trucks:
                    truck_info = truck_map[truck_id]
                    if not self._can_arrive_on_time(truck_info, current_date, demand.get('delivery_date')):
                        continue
                    truck_floor_area = (truck_info['width'] * truck_info['depth']) / 1_000_000
                    # 前日のこのトラックの状態を確認
                    target_truck_plan = None
                    for truck_plan in current_plan['trucks']:
                        if truck_plan['truck_id'] == truck_id:
                            target_truck_plan = truck_plan
                            break
                    # 残り容量を計算
                    if target_truck_plan:
                        loaded_area = 0
                        container_totals = {}
                        for item in target_truck_plan['loaded_items']:
                            container_id = item['container_id']
                            if container_id not in container_totals:
                                container_totals[container_id] = {
                                    'num_containers': 0,
                                    'floor_area_per_container': item['floor_area_per_container'],
                                    'stackable': item.get('stackable', False),
                                    'max_stack': item.get('max_stack', 1)
                                }
                            container_totals[container_id]['num_containers'] += item['num_containers']
                        for container_id, info in container_totals.items():
                            if info['stackable'] and info['max_stack'] > 1:
                                stacked_containers = (info['num_containers'] + info['max_stack'] - 1) // info['max_stack']
                                container_area = info['floor_area_per_container'] * stacked_containers
                            else:
                                container_area = info['floor_area_per_container'] * info['num_containers']
                            loaded_area += container_area
                        remaining_area = truck_floor_area - loaded_area
                    else:
                        # トラックプランが存在しない場合、全容量が空き
                        remaining_area = truck_floor_area
                    # 積載可能かチェック
                    demand_floor_area = demand['floor_area']
                    if demand_floor_area <= remaining_area:
                        # 積載可能 - 前日に特便を出す
                        container = container_map.get(demand['container_id'])
                        if not container:
                            continue
                        # 前日のトラックプランに追加
                        if not target_truck_plan:
                            # 新規トラックプラン作成
                            target_truck_plan = {
                                'truck_id': truck_id,
                                'truck_name': truck_info['name'],
                                'loaded_items': [],
                                'utilization': {'floor_area_rate': 0, 'volume_rate': 0, 'weight_rate': 0}
                            }
                            current_plan['trucks'].append(target_truck_plan)
                            current_plan['total_trips'] = len(current_plan['trucks'])
                        # アイテムを追加（特便フラグを設定）
                        capacity = demand['capacity']
                        expected_quantity = demand['num_containers'] * capacity
                        target_truck_plan['loaded_items'].append({
                            'product_id': demand['product_id'],
                            'product_code': demand['product_code'],
                            'product_name': demand.get('product_name', ''),
                            'container_id': demand['container_id'],
                            'container_name': container.name,
                            'num_containers': demand['num_containers'],
                            'total_quantity': expected_quantity,
                            'floor_area_per_container': demand['floor_area'] / demand['num_containers'],
                            'delivery_date': demand['delivery_date'],
                            'loading_date': current_date,
                            'is_special_delivery': True,  # 特便フラグ
                            'stackable': container.stackable,
                            'max_stack': container.max_stack,
                            'capacity': capacity
                        })
                        # 積載率を再計算
                        self._recalculate_utilization(target_truck_plan, truck_info, container_map)
                        # 当日の警告を削除
                        product_code = demand['product_code']
                        num_containers = demand['num_containers']
                        current_plan['warnings'] = [
                            w for w in current_plan['warnings']
                            if not (product_code in w and f"{num_containers}容器" in w)
                        ]
                        # 積み残しリストから削除
                        current_plan['remaining_demands'].remove(demand)
                        relocated = True
                        break
    def _verify_quantity(self, num_containers, capacity, original_quantity):
        """数量の整合性を検証して正しい値を返す"""
        calculated_quantity = num_containers * capacity
        verified_quantity = min(calculated_quantity, original_quantity)
        if calculated_quantity != verified_quantity:
            print(f"    🔄 数量補正: {calculated_quantity} → {verified_quantity}")
        return verified_quantity

    def _adjust_for_next_day_arrival_trucks(self, daily_plans, truck_map, start_date):
        """
        翌日着トラック（arrival_day_offset=1）の積載日を前日に調整
        
        重要：到着日は納期日のまま変わらないため、can_advance（前倒し可否）のチェックは不要
        お客さんから見れば納期日に届くので「前倒し」ではない
        
        期間外でもOK（例：期間が10-15～10-28の場合、10-15のトラックを10-14に移動）
        """
        # 翌日着トラックの積載日調整を開始
        
        # 日付順にソート
        sorted_dates = sorted(daily_plans.keys())
        
        for date_str in sorted_dates:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_plan = daily_plans[date_str]
            
            # この日のトラックプランをチェック
            trucks_to_move = []
            for truck_plan in day_plan['trucks']:
                truck_id = truck_plan['truck_id']
                if truck_id not in truck_map:
                    continue
                    
                truck_info = truck_map[truck_id]
                arrival_offset = int(truck_info.get('arrival_day_offset', 0) or 0)
                
                # arrival_day_offset=1のトラックを前日に移動
                if arrival_offset == 1:
                    trucks_to_move.append(truck_plan)
            
            # 移動対象のトラックを前日に移動
            for truck_plan in trucks_to_move:
                # 営業日の前日を探す
                prev_date = current_date - timedelta(days=1)
                
                # 非営業日の場合、営業日を遡る
                if self.calendar_repo:
                    max_attempts = 7  # 最大7日遡る
                    for _ in range(max_attempts):
                        if self.calendar_repo.is_working_day(prev_date):
                            break
                        prev_date -= timedelta(days=1)
                    else:
                        # 営業日が見つからない場合はそのまま処理継続
                        pass
                
                prev_date_str = prev_date.strftime('%Y-%m-%d')
                
                # 前日のプランが存在しない場合は作成
                if prev_date_str not in daily_plans:
                    daily_plans[prev_date_str] = {
                        'trucks': [],
                        'total_trips': 0,
                        'warnings': [],
                        'remaining_demands': []
                    }
                
                # トラックプランを前日に移動（到着日は変わらないため、can_advanceチェック不要）
                
                # 全ての積載アイテムのloading_dateを更新
                for item in truck_plan['loaded_items']:
                    item['loading_date'] = prev_date
                    item['adjusted_for_next_day_arrival'] = True  # フラグを追加
                
                # 前日のプランに追加
                daily_plans[prev_date_str]['trucks'].append(truck_plan)
                daily_plans[prev_date_str]['total_trips'] = len(daily_plans[prev_date_str]['trucks'])
                
                # 当日のプランから削除
                day_plan['trucks'].remove(truck_plan)
                day_plan['total_trips'] = len(day_plan['trucks'])
        
        # 翌日着トラックの積載日調整が完了

    def _create_summary(self, daily_plans, use_non_default, planned_dates=None) -> Dict:
        """サマリー作成"""
        if planned_dates is None:
            planned_keys = daily_plans.keys()
        else:
            planned_keys = [date.strftime('%Y-%m-%d') for date in planned_dates]
        total_trips = sum(daily_plans[key]['total_trips'] for key in planned_keys if key in daily_plans)
        total_warnings = sum(len(daily_plans[key]['warnings']) for key in planned_keys if key in daily_plans)
        return {
            'total_days': len(planned_keys),
            'total_trips': total_trips,
            'total_warnings': total_warnings,
            'unloaded_count': 0,  # 互換性のため
            'use_non_default_truck': use_non_default,
            'status': '正常' if total_warnings == 0 else '警告あり'
        }
