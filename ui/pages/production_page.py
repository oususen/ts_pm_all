# app/ui/pages/production_page.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from ui.components.charts import ChartComponents

class ProductionPage:
    """生産計画ページ（シミュレーション + CRUD管理）"""

    def __init__(self, production_service, transport_service=None, auth_service=None):
        self.service = production_service
        self.transport_service = transport_service
        self.auth_service = auth_service
        self.charts = ChartComponents()

    def _can_edit_page(self) -> bool:
        """ページ編集権限チェック"""
        if not self.auth_service:
            return True
        user = st.session_state.get('user')
        if not user:
            return False
        return self.auth_service.can_edit_page(user['id'], "生産計画")

    # -----------------------------
    # Entry
    # -----------------------------
    def show(self):
        st.title("🏭 生産計画")

        # 権限チェック
        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("⚠️ この画面の編集権限がありません。閲覧のみ可能です。")

        tab1, tab2 = st.tabs(["📊 計画シミュレーション", "📝 生産計画管理"])

        with tab1:
            self._show_plan_simulation(can_edit)

        with tab2:
            self._show_plan_management(can_edit)

    # -----------------------------
    # 旧：計画計算＋表示（既存機能を踏襲）
    # -----------------------------
    def _show_plan_simulation(self, can_edit):
        st.subheader("📊 計画シミュレーション")
        st.write("指定した期間の生産計画を計算・表示します。")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            start_date = st.date_input(
                "開始日", datetime.now().date(),
                help="計画の開始日を選択してください"
            )
        with col2:
            end_date = st.date_input(
                "終了日", datetime.now().date() + timedelta(days=30),
                help="計画の終了日を選択してください"
            )
        with col3:
            st.write(""); st.write("")
            calculate_clicked = st.button("🔧 計画計算", type="primary", use_container_width=True, disabled=not can_edit)

        if calculate_clicked:
            self._calculate_and_show_plan(start_date, end_date)

    def _calculate_and_show_plan(self, start_date, end_date):
        with st.spinner("生産計画を計算中..."):
            try:
                plans = self.service.calculate_production_plan(start_date, end_date)
                if plans:
                    # DataFrame 化
                    plan_df = pd.DataFrame([{
                        'date': plan.date,
                        'product_id': plan.product_id,
                        'product_code': plan.product_code,
                        'product_name': plan.product_name,
                        'demand_quantity': plan.demand_quantity,
                        'planned_quantity': plan.planned_quantity,
                        'inspection_category': plan.inspection_category,
                        'is_constrained': plan.is_constrained
                    } for plan in plans])

                    self._display_production_plan(plan_df)
                else:
                    st.warning("指定期間内に生産計画データがありません")

            except Exception as e:
                st.error(f"計画計算エラー: {e}")

    def _display_production_plan(self, plan_df: pd.DataFrame):
        # サマリー
        st.subheader("📈 計画サマリー")
        total_demand = plan_df['demand_quantity'].sum()
        total_planned = plan_df['planned_quantity'].sum()
        constrained_count = plan_df['is_constrained'].sum()

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("総需要量", f"{total_demand:,.0f}")
        with col2: st.metric("総計画生産量", f"{total_planned:,.0f}")
        with col3:
            utilization = (total_planned / total_demand * 100) if total_demand > 0 else 0
            st.metric("計画達成率", f"{utilization:.1f}%")
        with col4: st.metric("制約対象製品数", int(constrained_count))

        # グラフ
        st.subheader("📊 生産計画チャート")
        fig = self.charts.create_production_plan_chart(plan_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("グラフデータがありません")

        # 日次サマリー
        st.subheader("📋 詳細生産計画")
        st.write("**日次計画サマリー**")
        daily_summary = plan_df.groupby('date').agg({
            'demand_quantity': 'sum',
            'planned_quantity': 'sum'
        }).reset_index()
        daily_summary['達成率'] = (daily_summary['planned_quantity'] / daily_summary['demand_quantity'] * 100).round(1)

        st.dataframe(
            daily_summary,
            column_config={
                "date": "日付",
                "demand_quantity": st.column_config.NumberColumn("需要量", format="%d"),
                "planned_quantity": st.column_config.NumberColumn("計画生産量", format="%d"),
                "達成率": st.column_config.NumberColumn("達成率", format="%.1f%%"),
            },
            use_container_width=True,
        )

        # 製品別詳細
        st.write("**製品別詳細計画**")
        st.dataframe(
            plan_df,
            column_config={
                "date": "日付",
                "product_code": "製品コード",
                "product_name": "製品名",
                "demand_quantity": st.column_config.NumberColumn("需要量", format="%d"),
                "planned_quantity": st.column_config.NumberColumn("計画生産量", format="%d"),
                "inspection_category": "検査区分",
                "is_constrained": st.column_config.CheckboxColumn("制約対象"),
            },
            use_container_width=True,
        )

        # CSV 出力
        st.subheader("💾 データ出力")
        csv = plan_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 生産計画をCSVダウンロード",
            data=csv,
            file_name=f"production_plan_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            type="primary",
        )

    # -----------------------------
    # 新規：CRUD 管理タブ
    # -----------------------------
    def _show_plan_management(self, can_edit):
        st.subheader("📝 生産計画管理（登録・更新・削除）")

        # --- 新規登録フォーム（最低限の項目をインライン実装） ---
        with st.form("create_production_form"):
            st.write("新しい計画を登録")
            product_id = st.number_input("製品ID", min_value=1, step=1)
            quantity = st.number_input("数量", min_value=1, step=1)
            scheduled_date = st.date_input("日付", value=date.today())
            submitted = st.form_submit_button("登録", disabled=not can_edit)

            if submitted:
                if hasattr(self.service, "create_production"):
                    payload = {
                        "product_id": int(product_id),
                        "quantity": int(quantity),
                        "scheduled_date": scheduled_date,
                    }
                    ok = self.service.create_production(payload)
                    if ok:
                        st.success("生産計画を登録しました")
                        st.rerun()
                    else:
                        st.error("生産計画の登録に失敗しました")
                else:
                    st.warning("create_production() が service に未実装です")

        # --- 一覧＆編集／削除 ---
        st.subheader("登録済み計画一覧")
        if not hasattr(self.service, "get_productions"):
            st.info("get_productions() が service に未実装です")
            return

        plans = self.service.get_productions()
        if not plans:
            st.info("登録されている生産計画はありません")
            return

        for plan in plans:
            with st.expander(f"📝 計画ID: {plan.id}"):
                st.write(f"製品ID: {plan.product_id}, 数量: {plan.quantity}, 日付: {plan.scheduled_date}")

                # 編集フォーム
                with st.form(f"edit_production_{plan.id}"):
                    new_product_id = st.number_input("製品ID", min_value=1, value=plan.product_id, key=f"p_{plan.id}")
                    new_quantity   = st.number_input("数量",    min_value=1, value=plan.quantity,    key=f"q_{plan.id}")
                    new_date       = st.date_input("日付", value=plan.scheduled_date, key=f"d_{plan.id}")

                    update_clicked = st.form_submit_button("更新", disabled=not can_edit)
                    if update_clicked:
                        if hasattr(self.service, "update_production"):
                            update_data = {
                                "product_id": int(new_product_id),
                                "quantity": int(new_quantity),
                                "scheduled_date": new_date,
                            }
                            ok = self.service.update_production(plan.id, update_data)
                            if ok:
                                st.success("計画を更新しました")
                                st.rerun()
                            else:
                                st.error("計画更新に失敗しました")
                        else:
                            st.warning("update_production() が service に未実装です")

                # 削除ボタン
                delete_clicked = st.button("🗑️ 削除", key=f"del_{plan.id}", disabled=not can_edit)
                if delete_clicked:
                    if hasattr(self.service, "delete_production"):
                        ok = self.service.delete_production(plan.id)
                        if ok:
                            st.success("計画を削除しました")
                            st.rerun()
                        else:
                            st.error("計画削除に失敗しました")
                    else:
                        st.warning("delete_production() が service に未実装です")

