# app/ui/pages/dashboard_page.py
import streamlit as st
import pandas as pd
from ui.components.charts import ChartComponents

class DashboardPage:
    """ダッシュボードページ - メインの分析画面"""
    
    def __init__(self, production_service):
        self.service = production_service
        self.charts = ChartComponents()
    
    def show(self):
        """ページ表示"""
        st.title("🏭 生産計画管理ダッシュボード")
        
        # 基本情報表示
        self._show_basic_metrics()
        
        # 需要トレンドグラフ
        self._show_demand_trend()
    
    def _show_basic_metrics(self):
        """基本メトリクス表示"""
        try:
            products = self.service.get_all_products()
            instructions = self.service.get_production_instructions()
            constraints = self.service.get_product_constraints()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("登録製品数", len(products))
            
            with col2:
                st.metric("制約対象製品", len(constraints))
            
            with col3:
                total_demand = sum(inst.instruction_quantity for inst in instructions) if instructions else 0
                st.metric("総需要量", f"{total_demand:,.0f}")
            
            with col4:
                if instructions:
                    date_range = f"{min(inst.instruction_date for inst in instructions).strftime('%m/%d')} - {max(inst.instruction_date for inst in instructions).strftime('%m/%d')}"
                    st.metric("計画期間", date_range)
                else:
                    st.metric("計画期間", "データなし")
                    
        except Exception as e:
            st.error(f"データ取得エラー: {e}")
    
    def _show_demand_trend(self):
        """需要トレンド表示"""
        st.subheader("📈 需要トレンド分析")
        
        try:
            instructions = self.service.get_production_instructions()
            if instructions:
                # DataFrameに変換
                instructions_df = pd.DataFrame([{
                    'instruction_date': inst.instruction_date,
                    'instruction_quantity': inst.instruction_quantity,
                    'product_code': inst.product_code,
                    'product_name': inst.product_name
                } for inst in instructions])
                
                # トレンドグラフ表示
                fig = self.charts.create_demand_trend_chart(instructions_df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # 製品別需要
                st.subheader("製品別需要分析")
                product_demand = instructions_df.groupby(['product_code', 'product_name'])['instruction_quantity'].sum().reset_index()
                product_demand = product_demand.sort_values('instruction_quantity', ascending=False)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.dataframe(
                        product_demand,
                        column_config={
                            "product_code": "製品コード",
                            "product_name": "製品名", 
                            "instruction_quantity": st.column_config.NumberColumn(
                                "需要数量",
                                format="%d"
                            )
                        },
                        use_container_width=True
                    )
                
                with col2:
                    st.write("**需要トップ5**")
                    top_products = product_demand.head()
                    for _, product in top_products.iterrows():
                        st.write(f"• {product['product_name']}: {product['instruction_quantity']:,.0f}")
                        
            else:
                st.warning("生産指示データがありません")
                
        except Exception as e:
            st.error(f"グラフ表示エラー: {e}")