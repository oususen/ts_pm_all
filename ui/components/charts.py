# app/ui/components/charts.py
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

class ChartComponents:
    """チャートコンポーネント"""
    
    @staticmethod
    def create_demand_trend_chart(instructions_df: pd.DataFrame):
        """需要トレンドチャート作成"""
        if instructions_df.empty:
            return None
            
        trend_data = instructions_df.groupby('instruction_date')['instruction_quantity'].sum().reset_index()
        fig = px.line(trend_data, x='instruction_date', y='instruction_quantity', 
                     title='日次需要量トレンド', labels={'instruction_quantity': '需要量', 'instruction_date': '日付'})
        return fig
    
    @staticmethod
    def create_production_plan_chart(plan_df: pd.DataFrame):
        """生産計画チャート作成"""
        if plan_df.empty:
            return None
        
        daily_summary = plan_df.groupby('date').agg({
            'demand_quantity': 'sum',
            'planned_quantity': 'sum'
        }).reset_index()
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('需要量 vs 計画生産量', '制約対象製品の生産状況'),
            vertical_spacing=0.1
        )
        
        # 需要量と計画生産量
        fig.add_trace(
            go.Scatter(
                x=daily_summary['date'], y=daily_summary['demand_quantity'],
                name='需要量', line=dict(color='red'), mode='lines+markers'
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=daily_summary['date'], y=daily_summary['planned_quantity'],
                name='計画生産量', line=dict(color='blue'), mode='lines+markers'
            ),
            row=1, col=1
        )
        
        # 制約対象製品の生産状況
        constrained_plan = plan_df[plan_df['is_constrained'] == True]
        if not constrained_plan.empty:
            constrained_daily = constrained_plan.groupby('date')['planned_quantity'].sum().reset_index()
            fig.add_trace(
                go.Bar(
                    x=constrained_daily['date'], y=constrained_daily['planned_quantity'],
                    name='制約製品生産量', marker_color='orange'
                ),
                row=2, col=1
            )
        
        fig.update_layout(height=600, showlegend=True)
        fig.update_xaxes(title_text="日付", row=2, col=1)
        fig.update_yaxes(title_text="数量", row=1, col=1)
        fig.update_yaxes(title_text="数量", row=2, col=1)
        
        return fig