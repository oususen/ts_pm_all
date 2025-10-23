# app/ui/components/forms.py
import streamlit as st
from typing import Callable, Any, List,Dict
import streamlit as st

class FormComponents:
    """フォームコンポーネント"""
    
    @staticmethod
    def product_constraints_form(products, existing_constraints=None):
        """製品制約フォーム"""
        constraints_data = []
        
        for product in products:
            st.write(f"**{product.product_name}** ({product.product_code})")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                daily_capacity = st.number_input(
                    "日次生産能力",
                    min_value=0,
                    value=existing_constraints.get(product.id, {}).get('daily_capacity', 1000),
                    key=f"capacity_{product.id}"
                )
            
            with col2:
                smoothing_level = st.number_input(
                    "平均化レベル",
                    min_value=0.0,
                    max_value=1.0,
                    value=existing_constraints.get(product.id, {}).get('smoothing_level', 0.7),
                    key=f"smoothing_{product.id}"
                )
            
            with col3:
                volume_per_unit = st.number_input(
                    "単位体積(m³)",
                    min_value=0.0,
                    value=existing_constraints.get(product.id, {}).get('volume_per_unit', 1.0),
                    key=f"volume_{product.id}"
                )
            
            is_transport_constrained = st.checkbox(
                "運送制限対象",
                value=existing_constraints.get(product.id, {}).get('is_transport_constrained', False),
                key=f"transport_{product.id}"
            )
            
            constraints_data.append({
                'product_id': product.id,
                'daily_capacity': daily_capacity,
                'smoothing_level': smoothing_level,
                'volume_per_unit': volume_per_unit,
                'is_transport_constrained': is_transport_constrained
            })
            
            st.divider()
        
        return constraints_data
    # app/ui/components/forms.py の一部修正

    @staticmethod
    def container_form() -> Dict[str, Any]:
        """容器登録フォーム - mm単位に変更"""
        with st.form("container_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("容器名", value="小箱")
                width = st.number_input("幅 (mm)", min_value=1, value=800)
                depth = st.number_input("奥行 (mm)", min_value=1, value=600)
            
            with col2:
                height = st.number_input("高さ (mm)", min_value=1, value=600)
                max_weight = st.number_input("最大重量 (kg)", min_value=1, value=100)
                can_mix = st.checkbox("混載可能", value=True)
            
            submitted = st.form_submit_button("容器登録")
            
            if submitted:
                return {
                    'name': name,
                    'width': width,
                    'depth': depth,
                    'height': height,
                    'max_weight': max_weight,
                    'can_mix': can_mix
                }
        
        return None
   
    @staticmethod
    def truck_form() -> Dict[str, Any]:
        """トラック登録フォーム - mm単位に変更"""
        with st.form("truck_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("トラック名", value="1便")
                width = st.number_input("荷台幅 (mm)", min_value=1, value=2100)
                depth = st.number_input("荷台奥行 (mm)", min_value=1, value=3200)
                height = st.number_input("荷台高さ (mm)", min_value=1, value=2100)
            
            with col2:
                max_weight = st.number_input("最大積載重量 (kg)", min_value=1, value=2000)
                departure_time = st.time_input("出発時刻", value=None)
                
                arrival_time = st.time_input("到着時刻", value=None)
                arrival_day_offset = st.selectbox("到着日", options=[0, 1], format_func=lambda x: "当日" if x == 0 else "翌日")
                arr_time_str = arrival_time.strftime('%H:%M:%S') if arrival_time else "12:00:00"
                default_use = st.checkbox("デフォルト便", value=False)
                # 追加：優先積載製品コード入力欄
                priority_input = st.text_input(
                    "優先積載製品コード（カンマ区切り）",
                    placeholder="例: PRD001,PRD002"
                )
            
            submitted = st.form_submit_button("トラック登録")
            
            if submitted:
                # 時刻のデフォルト値処理
                dep_time = departure_time if departure_time else "08:00:00"
                arr_time = arrival_time if arrival_time else "12:00:00"
                
                return {
                    'name': name,
                    'width': width,
                    'depth': depth,
                    'height': height,
                    'max_weight': max_weight,
                    'departure_time': dep_time.strftime('%H:%M:%S') if hasattr(dep_time, 'strftime') else dep_time,
                    'arrival_time': arr_time.strftime('%H:%M:%S') if hasattr(arr_time, 'strftime') else arr_time,
                    'default_use': default_use,
                     # 新規追加：優先積載製品コードを返す（空欄ならNone）
                    'priority_product_codes': priority_input.strip() if priority_input else None
            
                }
        
        return None    
   
# app/ui/components/forms.py に以下のメソッドを追加

    
    @staticmethod
    def product_form(containers=None, trucks_df=None) -> dict:
        """製品登録フォーム - DB構造に完全対応"""
        with st.form("product_form", clear_on_submit=True):
            st.write("**新規製品情報**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**基本情報**")
                product_code = st.text_input("製品コード *", placeholder="例: P001")
                product_name = st.text_input("製品名 *", placeholder="例: 製品A")
                capacity = st.number_input("入り数 *", min_value=0, value=0, step=1)
                inspection_category = st.selectbox(
                    "検査区分",
                    options=['N', 'NS', 'FS', 'F', "" '$S'],
                    index=0
                )
                lead_time = st.number_input(
                    "リードタイム (日)",
                    min_value=0,
                    value=0,
                    step=1,
                    help="納品日の何日前に積載するか（0=納品日当日、2=2日前など）"
                )
                fixed_point_days = st.number_input("固定日数 (日)", min_value=0, value=0, step=1)
            
            with col2:
                st.write("**容器・トラック設定**")
                
                # 使用容器選択
                if containers:
                    container_options = {c.name: c.id for c in containers}
                    selected_container = st.selectbox(
                        "使用容器 *",
                        options=['未設定'] + list(container_options.keys())
                    )
                    used_container_id = container_options.get(selected_container) if selected_container != '未設定' else None
                else:
                    used_container_id = None
                    st.info("容器が登録されていません")
                
                # 使用トラック選択（複数選択）
                if trucks_df is not None and not trucks_df.empty:
                    truck_options = dict(zip(trucks_df['name'], trucks_df['id']))
                    selected_trucks = st.multiselect(
                        "使用トラック（複数選択可）",
                        options=list(truck_options.keys()),
                        help="この製品を運ぶトラックを選択してください"
                    )
                    selected_truck_ids = [truck_options[name] for name in selected_trucks]
                    used_truck_ids = ','.join(map(str, selected_truck_ids)) if selected_truck_ids else None
                else:
                    used_truck_ids = None
                    st.info("トラックが登録されていません")
                
                can_advance = st.checkbox("前倒可 (平準化対象)", value=False, 
                                        help="需要平準化の対象製品にする場合はチェック")
            
            submitted = st.form_submit_button("➕ 製品を登録", type="primary")
            
            if submitted:
                if not product_code or not product_name:
                    st.error("製品コードと製品名は必須です")
                    return None
                
                return {
                    "product_code": product_code,
                    "product_name": product_name,
                    "capacity": capacity,
                    "inspection_category": inspection_category,
                    "used_container_id": used_container_id,
                    "lead_time_days": lead_time,
                    "fixed_point_days": fixed_point_days,
                    "can_advance": can_advance,
                    "used_truck_ids": used_truck_ids,
                    # その他のフィールドはNone/デフォルト値
                    "data_no": None,
                    "factory": None,
                    "client_code": None,
                    "calculation_date": None,
                    "production_complete_date": None,
                    "modified_factory": None,
                    "product_category": None,
                    "ac_code": None,
                    "processing_content": None,
                    "delivery_location": None,
                    "box_type": None,
                    "grouping_category": None,
                    "form_category": None,
                    "ordering_category": None,
                    "regular_replenishment_category": None,
                    "shipping_factory": None,
                    "client_product_code": None,
                    "purchasing_org": None,
                    "item_group": None,
                    "processing_type": None,
                    "inventory_transfer_category": None,
                    "container_width": None,
                    "container_depth": None,
                    "container_height": None,
                    "stackable": True
                }
            
            return None
# app/ui/components/forms.py に以下のメソッドを追加

# (No duplicate or misaligned product_form method here; keep only the previous correct implementation.)