# app/ui/components/tables.py
import streamlit as st
import pandas as pd

class TableComponents:
    """テーブルコンポーネント"""
    
    @staticmethod
    def display_dataframe(df: pd.DataFrame, title: str = None):
        """データフレーム表示"""
        if title:
            st.write(f"**{title}**")
        st.dataframe(df, use_container_width=True)
    
    @staticmethod
    def display_loading_plan(plan_result: dict):
        """積載計画表示"""
        if not plan_result['plans']:
            st.warning("積載計画がありません")
            return
        
        st.subheader("積載計画サマリー")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("総便数", plan_result['total_trips'])
        with col2:
            st.metric("積載効率", f"{plan_result['efficiency']*100:.1f}%")
        with col3:
            st.metric("残りアイテム", len(plan_result['remaining_items']))
        
        for i, plan in enumerate(plan_result['plans'], 1):
            st.subheader(f"便 {i}: {plan.truck.name}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("体積利用率", f"{plan.volume_utilization*100:.1f}%")
            with col2:
                st.metric("重量利用率", f"{plan.weight_utilization*100:.1f}%")
            
            # 積載アイテム表示
            if plan.loaded_items:
                items_data = []
                for item in plan.loaded_items:
                    items_data.append({
                        '製品ID': item.product_id,
                        '容器ID': item.container_id,
                        '数量': item.quantity,
                        '重量/個': item.weight_per_unit
                    })
                st.dataframe(pd.DataFrame(items_data), use_container_width=True)