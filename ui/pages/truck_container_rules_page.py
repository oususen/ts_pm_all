# app/ui/pages/truck_container_rules_page.py
import streamlit as st
import pandas as pd
from typing import Dict, Any

class TruckContainerRulesPage:
    """トラック×容器ルール管理ページ"""
    def __init__(self, transport_service):
        self.transport_service = transport_service

    def _load_master(self):
        trucks_df = self.transport_service.get_trucks() or pd.DataFrame()
        containers = self.transport_service.get_containers() or []
        rules = self.transport_service.get_truck_container_rules() or []

        truck_id_to_name = {}
        truck_name_to_id = {}
        if trucks_df is not None and not trucks_df.empty:
            truck_id_to_name = dict(zip(trucks_df['id'], trucks_df['name']))
            truck_name_to_id = dict(zip(trucks_df['name'], trucks_df['id']))
        container_id_to_name = {c.id: c.name for c in containers}
        container_name_to_id = {c.name: c.id for c in containers}
        return trucks_df, containers, rules, truck_id_to_name, truck_name_to_id, container_id_to_name, container_name_to_id

    def _render_create_form(self, truck_name_to_id: Dict[str, int], container_name_to_id: Dict[str, int]):
        st.subheader("➕ ルール追加/更新")
        with st.form("tcr_create_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                truck_name = st.selectbox("トラック名", options=["選択"] + list(truck_name_to_id.keys()))
            with col2:
                container_name = st.selectbox("容器名", options=["選択"] + list(container_name_to_id.keys()))
            with col3:
                priority = st.number_input("優先度", min_value=0, value=0, step=1)

            col4, col5 = st.columns(2)
            with col4:
                max_quantity = st.number_input("最大積載量(容器数)", min_value=0, value=0, step=1)
            with col5:
                stack_count = st.number_input("段積み数(任意)", min_value=0, value=0, step=1,
                                             help="未設定の場合は容器のmax_stackを利用")

            submitted = st.form_submit_button("保存", type="primary")
            if submitted:
                if truck_name == "選択" or container_name == "選択":
                    st.error("トラック名と容器名を選択してください")
                    return
                try:
                    data: Dict[str, Any] = {
                        'truck_id': int(truck_name_to_id[truck_name]),
                        'container_id': int(container_name_to_id[container_name]),
                        'max_quantity': int(max_quantity),
                        'priority': int(priority)
                    }
                    if stack_count and int(stack_count) > 0:
                        data['stack_count'] = int(stack_count)
                    self.transport_service.save_truck_container_rule(data)
                    st.success("ルールを保存しました")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存エラー: {e}")

    def _render_rules_table(self, rules, truck_id_to_name, container_id_to_name):
        st.subheader("📋 登録済みルール")
        if not rules:
            st.info("ルールがありません")
            return
        # 表示用整形
        display = []
        for r in rules:
            display.append({
                'id': r.get('id'),
                'トラック名': truck_id_to_name.get(r.get('truck_id'), r.get('truck_id')),
                '容器名': container_id_to_name.get(r.get('container_id'), r.get('container_id')),
                '最大積載量(容器)': r.get('max_quantity'),
                '段積み数': r.get('stack_count'),
                '優先度': r.get('priority', 0),
            })
        df = pd.DataFrame(display)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 削除操作
        st.divider()
        st.subheader("🗑️ ルール削除")
        target_id = st.selectbox("削除するルールID", options=["選択"] + [str(r.get('id')) for r in rules if r.get('id') is not None])
        if st.button("削除", type="secondary", disabled=(target_id == "選択")):
            try:
                self.transport_service.delete_truck_container_rule(int(target_id))
                st.success("削除しました")
                st.rerun()
            except Exception as e:
                st.error(f"削除エラー: {e}")

    def show(self):
        st.title("🚚 トラック×容器ルール管理")
        trucks_df, containers, rules, truck_id_to_name, truck_name_to_id, container_id_to_name, container_name_to_id = self._load_master()

        if trucks_df is None or trucks_df.empty:
            st.warning("トラックが未登録です。先にトラックを登録してください。")
        if not containers:
            st.warning("容器が未登録です。先に容器を登録してください。")

        self._render_create_form(truck_name_to_id, container_name_to_id)
        self._render_rules_table(rules, truck_id_to_name, container_id_to_name)
