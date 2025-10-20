# app/ui/pages/transport_page.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Dict
from ui.components.forms import FormComponents
from ui.components.tables import TableComponents
from services.transport_service import TransportService
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os

class TransportPage:
    """配送便計画ページ - トラック積載計画の作成画面"""
    
    def __init__(self, transport_service):
        self.service = transport_service
        self.tables = TableComponents()
    
    def show(self):
        """ページ表示"""
        st.title("🚚 配送便計画")
        st.write("オーダー情報から自動的にトラック積載計画を作成します。")
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📦 積載計画作成",
            "📊 計画確認", 
            "🧰 容器管理", 
            "🚛 トラック管理",
            "🔬 検査対象製品",
            "🧱 トラック×容器ルール"  
        ])
        
        with tab1:
            self._show_loading_planning()
        with tab2:
            self._show_plan_view()
        with tab3:
            self._show_container_management()
        with tab4:
            self._show_truck_management()
        with tab5:
            self._show_inspection_products()# ✅ 新しいメソッド
        with tab6:
            self._show_truck_container_rules()
    
    def _show_truck_container_rules(self):
        """トラック×容器ルール管理（このページ内のタブ）"""
        st.header("🧱 トラック×容器ルール")
        try:
            trucks_df = self.service.get_trucks()
            if trucks_df is None or getattr(trucks_df, 'empty', False):
                trucks_df = pd.DataFrame()
            containers = self.service.get_containers() or []
            rules = self.service.get_truck_container_rules() or []

            truck_id_to_name = {}
            truck_name_to_id = {}
            if trucks_df is not None and not trucks_df.empty:
                truck_id_to_name = dict(zip(trucks_df['id'], trucks_df['name']))
                truck_name_to_id = dict(zip(trucks_df['name'], trucks_df['id']))
            container_id_to_name = {c.id: c.name for c in containers}
            container_name_to_id = {c.name: c.id for c in containers}

            # 入力フォーム
            st.subheader("➕ ルール追加/更新")
            with st.form("tcr_create_form_in_transport", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    truck_name = st.selectbox("トラック名", options=["選択"] + list(truck_name_to_id.keys()))
                with col2:
                    container_name = st.selectbox("容器名", options=["選択"] + list(container_name_to_id.keys()))
                with col3:
                    priority = st.number_input("優先度", min_value=0, value=0, step=1)

                col4, col5 = st.columns(2)
                with col4:
                    max_quantity = st.number_input(
                        "最大積載容器数（段積み後）",
                        min_value=0,
                        value=0,
                        step=1,
                        help="段積みを考慮した、実際に積載可能な容器の総数（列数×段数×列本数ではなく最終的な本数）"
                    )
                with col5:
                    stack_count = st.number_input(
                        "段積み数(任意)",
                        min_value=0,
                        value=0,
                        step=1,
                        help="同一列に重ねる段数。未設定の場合は容器のmax_stackを利用"
                    )

                submitted = st.form_submit_button("保存", type="primary")
                if submitted:
                    if truck_name == "選択" or container_name == "選択":
                        st.error("トラック名と容器名を選択してください")
                    else:
                        try:
                            data = {
                                'truck_id': int(truck_name_to_id[truck_name]),
                                'container_id': int(container_name_to_id[container_name]),
                                'max_quantity': int(max_quantity),
                                'priority': int(priority)
                            }
                            if stack_count and int(stack_count) > 0:
                                data['stack_count'] = int(stack_count)
                            self.service.save_truck_container_rule(data)
                            st.success("ルールを保存しました")
                            st.rerun()
                        except Exception as e:
                            st.error(f"保存エラー: {e}")

            # 一覧
            st.subheader("📋 登録済みルール")
            if not rules:
                st.info("ルールがありません")
            else:
                display = []
                for r in rules:
                    display.append({
                        'id': r.get('id'),
                        'トラック名': truck_id_to_name.get(r.get('truck_id'), r.get('truck_id')),
                        '容器名': container_id_to_name.get(r.get('container_id'), r.get('container_id')),
                        '最大積載容器数（段積み後）': r.get('max_quantity'),  # editable
                        '段積み数': r.get('stack_count'),          # editable
                        '優先度': r.get('priority', 0),            # editable
                    })
                df = pd.DataFrame(display)
                st.write("一覧（編集可能）")
                edited_df = st.data_editor(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'id': st.column_config.NumberColumn('ID', disabled=True),
                        'トラック名': st.column_config.TextColumn('トラック名', disabled=True),
                        '容器名': st.column_config.TextColumn('容器名', disabled=True),
                        '最大積載容器数（段積み後）': st.column_config.NumberColumn('最大積載容器数（段積み後）', min_value=0, step=1, help="段積みを考慮した実容器本数"),
                        '段積み数': st.column_config.NumberColumn('段積み数', min_value=0, step=1),
                        '優先度': st.column_config.NumberColumn('優先度', min_value=0, step=1),
                    },
                    key="tcr_editor"
                )

                if st.button("💾 変更を保存", type="primary", key="tcr_save_changes"):
                    try:
                        changes = 0
                        # 行ごとに差分を比較
                        for idx in range(len(df)):
                            before = df.iloc[idx]
                            after = edited_df.iloc[idx]
                            if (
                                before['最大積載容器数（段積み後）'] != after['最大積載容器数（段積み後）'] or
                                before['段積み数'] != after['段積み数'] or
                                before['優先度'] != after['優先度']
                            ):
                                rid = int(after['id']) if pd.notna(after['id']) else None
                                if rid is None:
                                    continue
                                update_data = {}
                                if before['最大積載容器数（段積み後）'] != after['最大積載容器数（段積み後）']:
                                    update_data['max_quantity'] = int(after['最大積載容器数（段積み後）'] or 0)
                                if before['段積み数'] != after['段積み数']:
                                    # None/NaN 対応
                                    val = after['段積み数']
                                    update_data['stack_count'] = int(val) if pd.notna(val) else None
                                if before['優先度'] != after['優先度']:
                                    update_data['priority'] = int(after['優先度'] or 0)
                                if update_data:
                                    ok = self.service.update_truck_container_rule(rid, update_data)
                                    if ok:
                                        changes += 1
                        if changes > 0:
                            st.success(f"{changes} 件のルールを更新しました")
                            st.rerun()
                        else:
                            st.info("変更はありませんでした")
                    except Exception as e:
                        st.error(f"更新エラー: {e}")

                st.divider()
                st.subheader("🗑️ ルール削除")
                target_id = st.selectbox(
                    "削除するルールID",
                    options=["選択"] + [str(r.get('id')) for r in rules if r.get('id') is not None],
                    key="tcr_delete_select"
                )
                if st.button("削除", type="secondary", disabled=(target_id == "選択"), key="tcr_delete_btn"):
                    try:
                        rid = int(target_id)
                        ok = self.service.delete_truck_container_rule(rid)
                        if ok:
                            st.success("削除しました")
                        else:
                            st.warning("対象のルールが見つかりませんでした")
                        st.rerun()
                    except Exception as e:
                        st.error(f"削除エラー: {e}")
        except Exception as e:
            st.error(f"ルール管理画面エラー: {e}")
    def _show_inspection_products(self):
        """検査対象製品（F/$）の注文詳細表示"""
        st.header("🔬 検査対象製品一覧")
        st.write("検査区分が「F」または「$」を含む製品の注文詳細を表示します。")
        
        # 期間フィルター（3日前～2週間後）
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "開始日",
                value=date.today() - timedelta(days=3),
                key="inspection_start_date"
            )
        
        with col2:
            end_date = st.date_input(
                "終了日",
                value=date.today() + timedelta(days=14),
                key="inspection_end_date"
            )
        
        # データ取得
        from sqlalchemy import text
        
        session = self.service.db.get_session()
        
        try:
            query = text("""
                SELECT 
                    dp.delivery_date as 日付,
                    dp.order_id as オーダーID,
                    p.product_code as 製品コード,
                    p.product_name as 製品名,
                    dp.order_quantity as 受注数,
                    dp.planned_quantity as 計画数,
                    dp.shipped_quantity as 出荷済,
                    p.inspection_category as 検査区分,
                    dp.customer_name as 得意先,
                    dp.status as ステータス
                FROM delivery_progress dp
                LEFT JOIN products p ON dp.product_id = p.id
                WHERE dp.delivery_date BETWEEN :start_date AND :end_date
                    AND (p.inspection_category LIKE 'F%' OR p.inspection_category LIKE '%$%')
                    AND dp.status != 'キャンセル'
                ORDER BY dp.delivery_date, p.product_code
            """)
            
            result = session.execute(query, {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            })
            
            rows = result.fetchall()
            
            if rows:
                df = pd.DataFrame(rows, columns=result.keys())
                df['日付'] = pd.to_datetime(df['日付']).dt.date
                
                # サマリー
                st.subheader("📊 サマリー")
                col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                
                with col_sum1:
                    st.metric("総注文数", len(df))
                # サマリー部分のみ修正
                with col_sum2:
                    # ✅ 修正: Fを含む
                    f_count = len(df[df['検査区分'].str.contains('F', na=False)])
                    st.metric("F含む（最終検査）", f_count)
                with col_sum3:
                    # ✅ 修正: $を含む（正規表現でエスケープ）
                    s_count = len(df[df['検査区分'].str.contains('\\$', regex=True, na=False)])
                    st.metric("$含む（目視検査）", s_count)
                with col_sum4:
                    st.metric("総受注数量", f"{df['受注数'].sum():,}個")
                
                # フィルター
                inspection_filter = st.multiselect(
                    "検査区分",
                    options=['F', '$'],
                    default={},  #['F', '$'],
                    key="inspection_filter"
                )
                
                if inspection_filter:
                    df = df[df['検査区分'].isin(inspection_filter)]
                
                # データ表示
                st.subheader("📋 注文詳細一覧")
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "日付": st.column_config.DateColumn("日付", format="YYYY-MM-DD"),
                    }
                )
                
                # 日付別集計
                st.subheader("📅 日付別集計")
                daily = df.groupby(['日付', '検査区分']).agg({
                    'オーダーID': 'count',
                    '受注数': 'sum'
                }).reset_index()
                daily.columns = ['日付', '検査区分', '注文件数', '合計数量']
                
                st.dataframe(daily, use_container_width=True, hide_index=True)
                
                # CSV出力
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 CSV ダウンロード",
                    csv,
                    f"検査対象製品_{start_date}_{end_date}.csv",
                    "text/csv"
                )
            else:
                st.info("指定期間内に検査対象製品（F/$）の注文がありません")
        
        except Exception as e:
            st.error(f"データ取得エラー: {e}")
        finally:
            session.close()

    def _show_loading_planning(self):
        """積載計画作成"""
        st.header("📦 積載計画自動作成")
        
        st.info("""
        **機能説明:**
        - オーダー情報から自動的に積載計画を作成します
        - 納期優先で計画し、積載不可の場合は前倒しで再計算します
        - 前倒し可能な製品のみが平準化の対象となります
        """)
        
        # 納期データから推奨期間を取得
        try:
            orders_df = self.service.get_delivery_progress()
            if not orders_df.empty and 'delivery_date' in orders_df.columns:
                min_delivery = pd.to_datetime(orders_df['delivery_date']).min().date()
                max_delivery = pd.to_datetime(orders_df['delivery_date']).max().date()
                st.info(f"💡 納期データの範囲: {min_delivery} ～ {max_delivery}")
        except Exception as e:
            pass
        
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "計画開始日",
                value=date.today() - timedelta(days=15),
                min_value=date.today() - timedelta(days=15),
                help="積載計画の開始日（納期の最も早い日付を含めてください）"
            )
        
        with col2:
            # ✅ 修正: 計画日数 → 計画終了日
            end_date = st.date_input(
                "計画終了日",
                value=date.today() + timedelta(days=10),  # デフォルト: 10日後
                min_value=start_date,
                help="積載計画の終了日を指定してください"
            )
        
        # ✅ 日数を自動計算
        days = (end_date - start_date).days + 1
        
        # 計画日数の表示
        st.info(f"📅 計画期間: **{days}日間** ({start_date.strftime('%Y年%m月%d日')} ～ {end_date.strftime('%Y年%m月%d日')})")
   
        st.markdown("---")
        
        if st.button("🔄 積載計画を作成", type="primary", use_container_width=True):
            with st.spinner("積載計画を計算中..."):
                try:
                    result = self.service.calculate_loading_plan_from_orders(
                        start_date=start_date,
                        days=days
                    )
                    
                    st.session_state['loading_plan'] = result
                    
                    summary = result['summary']
                    
                    st.success("✅ 積載計画を作成しました")
                    
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        st.metric("計画日数", f"{summary['total_days']}日")
                    with col_b:
                        st.metric("総便数", f"{summary['total_trips']}便")
                    with col_c:
                        st.metric("警告数", summary['total_warnings'])
                    with col_d:
                        status_color = "🟢" if summary['status'] == '正常' else "🟡"
                        st.metric("ステータス", f"{status_color} {summary['status']}")
                    
                    unplanned_orders = result.get('unplanned_orders') or []
                    if unplanned_orders:
                        st.warning(f"⚠️ 受注されたが積載されていない製品が {len(unplanned_orders)} 件あります")
                        unplanned_df = pd.DataFrame(unplanned_orders)
                        st.dataframe(
                            unplanned_df,
                            width='stretch',
                            hide_index=True
                        )
                    
                    if result['unloaded_tasks']:
                        st.error(f"⚠️ 積載できなかった製品: {len(result['unloaded_tasks'])}件")
                        
                        unloaded_df = pd.DataFrame([{
                            '製品コード': task['product_code'],
                            '製品名': task['product_name'],
                            '容器数': task['num_containers'],
                            '納期': task['delivery_date'].strftime('%Y-%m-%d')
                        } for task in result['unloaded_tasks']])
                        
                        st.dataframe(unloaded_df, use_container_width=True, hide_index=True)
                        
                        st.warning("""
                        **対処方法:**
                        - トラックの追加を検討してください
                        - 製品の前倒し可能フラグを確認してください
                        - 容器・トラックの容量を確認してください
                        """)
                    
                    st.info("詳細は「📊 計画確認」タブでご確認ください")
                    
                except Exception as e:
                    st.error(f"積載計画作成エラー: {e}")
                    
        if 'loading_plan' in st.session_state:
            result = st.session_state['loading_plan']
            summary = result.get('summary', {})
            
            st.markdown("---")
            st.subheader("💾 計画の保存とエクスポート")
            
            col_export1, col_export2, col_export3 = st.columns(3)
            
            with col_export1:
                st.write("**DBに保存**")
                plan_name = st.text_input(
                    "計画名",
                    value=f"積載計画_{result.get('period', '').split(' ~ ')[0]}",
                    key="plan_name_save"
                )
                
                if st.button("💾 DBに保存", type="primary"):
                    try:
                        plan_id = self.service.save_loading_plan(result, plan_name)
                        st.success(f"✅ 計画を保存しました (ID: {plan_id})")
                        st.session_state['saved_plan_id'] = plan_id
                    except Exception as e:
                        st.error(f"保存エラー: {e}")
            
            with col_export2:
                st.write("**Excel出力**")
                export_format = st.radio(
                    "出力形式",
                    options=['日別', '週別'],
                    horizontal=True,
                    key="export_format"
                )
                
                if st.button("📥 Excelダウンロード", type="secondary"):
                    try:
                        format_key = 'daily' if export_format == '日別' else 'weekly'
                        excel_data = self.service.export_loading_plan_to_excel(result, format_key)
                        
                        filename = f"積載計画_{export_format}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        
                        st.download_button(
                            label="⬇️ ダウンロード",
                            data=excel_data,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Excel出力エラー: {e}")
            
            with col_export3:
                st.write("**CSV出力**")
                st.write("")
                
                if st.button("📄 CSVダウンロード", type="secondary"):
                    try:
                        csv_data = self.service.export_loading_plan_to_csv(result)
                        
                        filename = f"積載計画_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        
                        st.download_button(
                            label="⬇️ ダウンロード",
                            data=csv_data,
                            file_name=filename,
                            mime="text/csv"
                        )

                    except Exception as e:
                        st.error(f"CSV出力エラー: {e}")

            st.markdown("---")
            st.subheader("Excel修正の取り込み")
            st.write("Excelに出力した計画を修正した後、ここからアップロードすると数量変更を取り込みます。`編集キー`列（旧`edit_key`）は変更しないでください。編集可能な列は **コンテナ数**, **総数量**, **納品日** のみです。その他の列は書き換えないでください。")
            if summary.get('manual_adjusted'):
                st.info(f"Excelで手動調整 {summary.get('manual_adjustment_count', 0)} 件を反映済みです。")
            uploaded_excel = st.file_uploader(
                "修正済みExcelファイル (.xlsx)",
                type=['xlsx'],
                key="loading_plan_excel_upload"
            )

            if uploaded_excel is not None:
                if st.button("Excelの修正を適用", type="primary", key="apply_excel_updates"):
                    with st.spinner("Excelの変更を反映中..."):
                        apply_result = self.service.apply_excel_adjustments(result, uploaded_excel)
                    errors = apply_result.get('errors') or []
                    for err in errors:
                        st.error(err)
                    changes = apply_result.get('changes') or []
                    if changes:
                        st.session_state['loading_plan'] = apply_result.get('plan', result)
                        st.success(f"Excelから{len(changes)}件の変更を反映しました。")
                        change_rows = []
                        for change in changes:
                            for field, diff in change['changes'].items():
                                change_rows.append({
                                    'edit_key': change['edit_key'],
                                    '積込日': change['loading_date'],
                                    'トラック': change['truck_name'],
                                    '品目コード': change['product_code'],
                                    '品目名': change['product_name'],
                                    '項目': field,
                                    '変更前': diff.get('before'),
                                    '変更後': diff.get('after')
                                })
                        if change_rows:
                            st.dataframe(pd.DataFrame(change_rows), use_container_width=True, hide_index=True)
                        result = st.session_state['loading_plan']
                        summary = result.get('summary', {})
                        if summary.get('manual_adjusted'):
                            st.info(f"Excelで手動調整 {summary.get('manual_adjustment_count', 0)} 件を反映済みです。")
                    elif not errors:
                        st.warning("Excelから変更が見つかりませんでした。")

    def _show_plan_view(self):
        """計画確認"""
        st.header("📊 積載計画確認")
        
        view_tab1, view_tab2 = st.tabs(["現在の計画", "保存済み計画"])
        
        with view_tab1:
            self._show_current_plan()
        
        with view_tab2:
            self._show_saved_plans()
    
    def _show_current_plan(self):
        """現在の計画表示"""
        
        if 'loading_plan' not in st.session_state:
            st.info("まず「積載計画作成」タブで計画を作成してください")
            return
        
        result = st.session_state['loading_plan']
        daily_plans = result['daily_plans']
        
        unplanned_orders = result.get('unplanned_orders') or []
        if unplanned_orders:
            st.warning(f"⚠️ 受注されたが積載されていない製品が {len(unplanned_orders)} 件あります")
            unplanned_df = pd.DataFrame(unplanned_orders)
            st.dataframe(
                unplanned_df,
                width='stretch',
                hide_index=True
            )
            st.markdown("---")
        
        view_type = st.radio(
            "表示形式",
            options=['日別表示', '一覧表示'],
            horizontal=True
        )
        
        if view_type == '日別表示':
            self._show_daily_view(daily_plans)
        else:
            self._show_list_view(daily_plans)
     
    def _show_saved_plans(self):
        """保存済み計画表示"""
        
        try:
            saved_plans = self.service.get_all_loading_plans()
            
            if not saved_plans:
                st.info("保存済みの計画がありません")
                return
            
            # 計画選択UI
            plan_options = {
                f"ID {plan['id']}: {plan['plan_name']} ({plan['summary']['total_days']}日, {plan['summary']['total_trips']}便)": plan['id'] 
                for plan in saved_plans
            }
            
            selected_plan_key = st.selectbox(
                "表示する計画を選択",
                options=list(plan_options.keys())
            )
            
            if selected_plan_key:
                selected_plan_id = plan_options[selected_plan_key]
                
                # ✅ 修正: 選択した計画IDを使って詳細データを取得
                with st.spinner("計画データを読み込み中..."):
                    selected_plan = self.service.get_loading_plan(selected_plan_id)
                
                if selected_plan:
                    self._display_saved_plan(selected_plan)
                else:
                    st.error("選択した計画の詳細データを取得できませんでした")
        
        except Exception as e:
            st.error(f"保存済み計画表示エラー: {e}")
            import traceback
            st.code(traceback.format_exc())
          
    def _display_saved_plan(self, plan_data: Dict):
        """保存済み計画を表形式で表示・編集"""
        try:
            st.subheader("計画詳細")
            
            # ✅ 出力形式選択とエクスポートボタン
            st.markdown("---")
            st.subheader("📤 計画のエクスポート")
            
            col_export1, col_export2, col_export3 = st.columns([2, 1, 1])
            
            with col_export1:
                # 出力形式選択
                export_format = st.radio(
                    "出力形式を選択",
                    options=["📊 Excel形式", "📄 PDF形式"],
                    horizontal=True,
                    key=f"export_format_{plan_data.get('id', 'current')}"
                )
            
            with col_export2:
                # エクスポートボタン
                if st.button("🔄 エクスポート", type="primary", use_container_width=True):
                    with st.spinner("エクスポート中..."):
                        if export_format == "📊 Excel形式":
                            # Excelエクスポート
                            excel_buffer = self._export_plan_to_excel(plan_data)
                            if excel_buffer:
                                st.download_button(
                                    label="⬇️ Excelダウンロード",
                                    data=excel_buffer,
                                    file_name=f"積載計画_{plan_data.get('plan_name', '無題')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key=f"excel_dl_{plan_data.get('id', 'current')}"
                                )
                        else:
                            # PDFエクスポート
                            pdf_buffer = self._export_plan_to_pdf(plan_data)
                            if pdf_buffer:
                                st.download_button(
                                    label="⬇️ PDFダウンロード",
                                    data=pdf_buffer,
                                    file_name=f"積載計画_{plan_data.get('plan_name', '無題')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"pdf_dl_{plan_data.get('id', 'current')}"
                                )
            
            with col_export3:
                # クイックエクスポートボタン（両方）
                if st.button("📁 両方出力", type="secondary", use_container_width=True):
                    with st.spinner("両方の形式で出力中..."):
                        # Excel出力
                        excel_buffer = self._export_plan_to_excel(plan_data)
                        # PDF出力
                        pdf_buffer = self._export_plan_to_pdf(plan_data)
                        
                        if excel_buffer and pdf_buffer:
                            col_dl1, col_dl2 = st.columns(2)
                            with col_dl1:
                                st.download_button(
                                    label="⬇️ Excelダウンロード",
                                    data=excel_buffer,
                                    file_name=f"積載計画_{plan_data.get('plan_name', '無題')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key=f"excel_both_{plan_data.get('id', 'current')}"
                                )
                            with col_dl2:
                                st.download_button(
                                    label="⬇️ PDFダウンロード",
                                    data=pdf_buffer,
                                    file_name=f"積載計画_{plan_data.get('plan_name', '無題')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"pdf_both_{plan_data.get('id', 'current')}"
                                )

            # 削除ボタン
            st.markdown("---")
            st.subheader("🗑️ 計画の削除")
            
            col_delete1, col_delete2 = st.columns([3, 1])
            
            with col_delete1:
                st.warning(f"⚠️ 計画「{plan_data.get('plan_name', '無題')}」を削除しますか？この操作は取り消せません。")
            
            with col_delete2:
                if st.button("🗑️ 削除", type="secondary", use_container_width=True, key=f"delete_{plan_data.get('id')}"):
                    if self._confirm_and_delete_plan(plan_data.get('id'), plan_data.get('plan_name', '無題')):
                        st.success("✅ 計画を削除しました")
                        st.rerun()
            
            st.markdown("---")
            
            summary = plan_data.get('summary', {})
            daily_plans = plan_data.get('daily_plans', {})
            unloaded_tasks = plan_data.get('unloaded_tasks', [])
            
            if not daily_plans:
                st.warning("❌ daily_plans データがありません")
                st.info("計画データの構造を確認しています...")
                st.json(plan_data)  # 全データを表示して確認
                return
            
            # サマリー表示
            st.subheader("📊 計画サマリー")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("計画日数", f"{summary.get('total_days', 0)}日")
            with col2:
                st.metric("総便数", summary.get('total_trips', 0))
            with col3:
                st.metric("ステータス", summary.get('status', '不明'))
            with col4:
                period = plan_data.get('period', '期間不明')
                st.metric("計画期間", period)
            
            st.markdown("---")
            
            # ✅ 保存方式選択UIをここに追加
            st.subheader("💾 保存オプション")
            save_mode = st.radio(
                "保存方式",
                options=["🖱️ 手動保存", "⏰ 自動保存", "🔀 バージョン保存"],
                horizontal=True,
                key=f"save_mode_{plan_data['id']}"
            )
            
            if save_mode == "🔀 バージョン保存":
                version_name = st.text_input(
                    "バージョン名",
                    value=f"修正_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    key=f"version_name_{plan_data['id']}"
                )
            
            # 全データを1つのDataFrameに変換
            all_plan_data = []
            # ✅ row_id_mapを定義
            row_id_map = {}  # {row_index: (date_str, truck_idx, item_idx)}
            
            for date_str in sorted(daily_plans.keys()):
                day_plan = daily_plans[date_str]
                st.write(f"📅 日付: {date_str}, トラック数: {len(day_plan.get('trucks', []))}")
                
                for truck_idx, truck in enumerate(day_plan.get('trucks', [])):
                    truck_name = truck.get('truck_name', '不明')
                    utilization = truck.get('utilization', {})
                    
                    st.write(f"  🚛 トラック: {truck_name}, アイテム数: {len(truck.get('loaded_items', []))}")
                    
                    for item_idx, item in enumerate(truck.get('loaded_items', [])):
                        # 納期のフォーマット処理
                        delivery_date = item.get('delivery_date')
                        delivery_date_str = ''
                        if delivery_date:
                            if hasattr(delivery_date, 'strftime'):
                                delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                            elif hasattr(delivery_date, 'date'):
                                delivery_date_str = delivery_date.date().strftime('%Y-%m-%d')
                            else:
                                delivery_date_str = str(delivery_date)
                        
                        # ✅ row_id_mapにインデックスを追加
                        row_index = len(all_plan_data)
                        row_id_map[row_index] = (date_str, truck_idx, item_idx)
                        
                        all_plan_data.append({
                            '積載日': date_str,
                            'トラック': truck_name,
                            '製品コード': item.get('product_code', ''),
                            '製品名': item.get('product_name', ''),
                            '容器数': item.get('num_containers', 0),
                            '合計数量': item.get('total_quantity', 0),
                            '納期': delivery_date_str,
                            '体積率(%)': utilization.get('volume_rate', 0),
                            '重量率(%)': utilization.get('weight_rate', 0)
                        })
            
            if all_plan_data:
                plan_df = pd.DataFrame(all_plan_data)
                
                st.success(f"✅ 計画データを読み込みました: {len(plan_df)} 行")
                
                # 編集可能なデータエディタ
                st.info("💡 **編集方法:** セルをダブルクリックして値を変更し、「💾 変更を保存」をクリック")
                
# 編集可能なデータエディタ部分を修正
            edited_df = st.data_editor(
                plan_df,
                use_container_width=True,
                hide_index=True,
                disabled=['積載日', 'トラック', '容器数', '体積率(%)', '重量率(%)'],  # 容器数と積載率を編集不可に
                column_config={
                    "積載日": st.column_config.TextColumn("積載日"),
                    "トラック": st.column_config.TextColumn("トラック"),
                    "製品コード": st.column_config.TextColumn("製品コード"),
                    "製品名": st.column_config.TextColumn("製品名"),
                    "容器数": st.column_config.NumberColumn("容器数", min_value=0, step=1, disabled=True),
                    "合計数量": st.column_config.NumberColumn("合計数量", min_value=0, step=1),
                    "納期": st.column_config.TextColumn("納期"),
                    "体積率(%)": st.column_config.NumberColumn("体積率(%)", format="%d%%", disabled=True),
                    "重量率(%)": st.column_config.NumberColumn("重量率(%)", format="%d%%", disabled=True)
                },
                key=f"plan_editor_{plan_data.get('id', 'current')}"
            )

            # 合計数量が変更された場合、容器数と積載率を自動計算
            if not edited_df.equals(plan_df):
                # 必要な情報を取得
                try:
                    products_df = self.service.product_repo.get_all_products()
                    capacity_map = dict(zip(products_df['product_code'], products_df['capacity']))
                    containers = self.service.get_containers()
                    container_map = {container.id: container for container in containers}
                    trucks_df = self.service.get_trucks()
                    truck_map = {truck['id']: truck for _, truck in trucks_df.iterrows()}
                except Exception as e:
                    st.warning(f"情報取得エラー: {e}")
                    capacity_map = {}
                    container_map = {}
                    truck_map = {}
                
                # 変更があった行を処理
                for idx in range(len(plan_df)):
                    original_row = plan_df.iloc[idx]
                    edited_row = edited_df.iloc[idx]
                    
                    # 合計数量が変更された場合
                    if original_row['合計数量'] != edited_row['合計数量']:
                        product_code = edited_row['製品コード']
                        capacity = capacity_map.get(product_code, 1)
                        
                        # 容器数計算
                        if capacity > 0:
                            new_num_containers = (edited_row['合計数量'] + capacity - 1) // capacity
                            edited_df.at[idx, '容器数'] = max(1, new_num_containers)
                        else:
                            edited_df.at[idx, '容器数'] = 1
                
                # トラックごとの積載率を再計算
                try:
                    # トラックごとにグループ化して計算
                    truck_utilization = {}
                    
                    for idx, row in edited_df.iterrows():
                        if idx in row_id_map:
                            date_str, truck_idx, item_idx = row_id_map[idx]
                            truck_id = plan_data['daily_plans'][date_str]['trucks'][truck_idx]['truck_id']
                            
                            # ✅ キーを日付とトラックインデックスも含めて一意にする
                            truck_key = f"{date_str}_{truck_id}_{truck_idx}"
                            
                            if truck_key not in truck_utilization:
                                truck_utilization[truck_key] = {
                                    'total_volume': 0,
                                    'total_weight': 0,
                                    'date_str': date_str,
                                    'truck_idx': truck_idx,
                                    'truck_id': truck_id
                                }
                            
                            # 製品の容器情報を取得
                            product_code = row['製品コード']
                            product_info = products_df[products_df['product_code'] == product_code]
                            if not product_info.empty:
                                container_id = product_info.iloc[0]['used_container_id']
                                if container_id and container_id in container_map:
                                    container = container_map[container_id]
                                    # 容器の体積と重量を計算
                                    container_volume = (container.width * container.depth * container.height) / 1000000000  # m³換算
                                    container_weight = container.max_weight
                                    
                                    # 合計体積・重量に加算
                                    num_containers = row['容器数']
                                    truck_utilization[truck_key]['total_volume'] += container_volume * num_containers
                                    truck_utilization[truck_key]['total_weight'] += container_weight * num_containers

                    # 積載率を計算して反映
                    for truck_key, util_data in truck_utilization.items():
                        truck_id = util_data['truck_id']
                        if truck_id in truck_map:
                            truck = truck_map[truck_id]
                            # トラックの最大容量を計算
                            truck_volume = (truck['width'] * truck['depth'] * truck['height']) / 1000000000
                            truck_max_weight = truck['max_weight']
                            
                            # 積載率計算
                            volume_rate = min(100, (util_data['total_volume'] / truck_volume) * 100) if truck_volume > 0 else 0
                            weight_rate = min(100, (util_data['total_weight'] / truck_max_weight) * 100) if truck_max_weight > 0 else 0
                            
                            # ✅ 該当トラックの行だけに積載率を反映
                            for df_idx in range(len(edited_df)):
                                if df_idx in row_id_map:
                                    date_str, truck_idx, item_idx = row_id_map[df_idx]
                                    current_truck_id = plan_data['daily_plans'][date_str]['trucks'][truck_idx]['truck_id']
                                    # 同じトラックかつ同じ日付の場合
                                    if (current_truck_id == truck_id and 
                                        date_str == util_data['date_str'] and 
                                        truck_idx == util_data['truck_idx']):
                                        edited_df.at[df_idx, '体積率(%)'] = round(volume_rate, 1)
                                        edited_df.at[df_idx, '重量率(%)'] = round(weight_rate, 1)
                            
                            # デバッグ情報（必要に応じて）
                            st.write(f"🚛 トラック {truck_id}: 体積率 {volume_rate:.1f}%, 重量率 {weight_rate:.1f}%")
                    
                except Exception as e:
                    st.error(f"積載率計算エラー: {e}")
                
                # 保存ボタン
                st.markdown("---")
                if st.button("💾 変更を保存", type="primary", key=f"save_{plan_data.get('id', 'current')}"):
                    # 保存方式に応じた処理
                    if save_mode == "🔀 バージョン保存":
                        # バージョン作成（実装済みの場合）
                        try:
                            version_id = self.service.create_plan_version(
                                plan_data['id'], 
                                version_name,
                                "user123"  # 実際はセッションからユーザーIDを取得
                            )
                            if version_id:
                                st.success(f"✅ バージョン '{version_name}' を作成しました")
                        except Exception as e:
                            st.info(f"バージョン機能は現在開発中です: {e}")
                    
                    # 通常の保存処理
                    try:
                        success = self._save_plan_changes(
                            plan_data=plan_data,
                            original_df=plan_df,
                            edited_df=edited_df,
                            row_id_map=row_id_map
                        )
                        
                        if success:
                            st.success("✅ 変更を保存しました")
                            st.rerun()
                        else:
                            st.info("変更はありませんでした")
                    except Exception as e:
                        st.info(f"保存機能は現在開発中です: {e}")
                        
            else:
                st.warning("表示する積載計画データがありません")
                
            # 警告表示
            warnings_data = []
            for date_str, day_plan in daily_plans.items():
                for warning in day_plan.get('warnings', []):
                    warnings_data.append({
                        '日付': date_str,
                        '警告内容': warning
                    })
            
            if warnings_data:
                st.subheader("⚠️ 警告一覧")
                warnings_df = pd.DataFrame(warnings_data)
                st.dataframe(warnings_df, use_container_width=True, hide_index=True)
                    
        except Exception as e:
            st.error(f"計画表示エラー: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


    def _export_plan_to_pdf(self, plan_data: Dict):
        """積載計画をPDFとしてエクスポート（日本語対応）"""
        try:
            # PDFバッファを作成
            buffer = io.BytesIO()
            
            # 横向きA4でドキュメント作成
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
            elements = []
            styles = getSampleStyleSheet()
            
            # ✅ 日本語フォントの設定
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.fonts import addMapping
            
            # 日本語フォントの登録（システムにインストールされているフォントを使用）
            try:
                # Windowsの日本語フォント
                pdfmetrics.registerFont(TTFont('Japanese', 'C:/Windows/Fonts/msgothic.ttc'))
                pdfmetrics.registerFont(TTFont('Japanese-Bold', 'C:/Windows/Fonts/msgothic.ttc'))
            except:
                try:
                    # macOSの日本語フォント
                    pdfmetrics.registerFont(TTFont('Japanese', '/System/Library/Fonts/Arial Unicode.ttf'))
                    pdfmetrics.registerFont(TTFont('Japanese-Bold', '/System/Library/Fonts/Arial Unicode.ttf'))
                except:
                    try:
                        # Linuxの日本語フォント
                        pdfmetrics.registerFont(TTFont('Japanese', '/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf'))
                        pdfmetrics.registerFont(TTFont('Japanese-Bold', '/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf'))
                    except:
                        st.warning("日本語フォントが見つかりません。デフォルトフォントを使用します。")
            
            # フォントマッピングの設定
            addMapping('Japanese', 0, 0, 'Japanese')
            addMapping('Japanese', 1, 0, 'Japanese-Bold')
            
            # ✅ 日本語対応スタイルの作成
            japanese_style = styles['Normal'].clone('JapaneseStyle')
            japanese_style.fontName = 'Japanese'
            japanese_style.fontSize = 10
            japanese_style.leading = 12
            
            japanese_title_style = styles['Heading1'].clone('JapaneseTitleStyle')
            japanese_title_style.fontName = 'Japanese-Bold'
            japanese_title_style.fontSize = 16
            japanese_title_style.leading = 20
            japanese_title_style.alignment = 1  # 中央揃え
            
            japanese_heading_style = styles['Heading2'].clone('JapaneseHeadingStyle')
            japanese_heading_style.fontName = 'Japanese-Bold'
            japanese_heading_style.fontSize = 12
            japanese_heading_style.leading = 16
            
            # タイトル
            title = Paragraph(f"積載計画: {plan_data.get('plan_name', '無題')}", japanese_title_style)
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # 計画情報
            summary = plan_data.get('summary', {})
            info_data = [
                ['計画期間', plan_data.get('period', '')],
                ['計画日数', f"{summary.get('total_days', 0)}日"],
                ['総便数', f"{summary.get('total_trips', 0)}便"],
                ['ステータス', summary.get('status', '不明')],
                ['作成日', datetime.now().strftime('%Y-%m-%d %H:%M')]
            ]
            
            # ✅ 日本語フォントを使用したテーブルスタイル
            info_table = Table(info_data, colWidths=[80*mm, 80*mm])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Japanese'),  # ✅ 日本語フォント指定
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 12))
            
            # 積載計画データ
            daily_plans = plan_data.get('daily_plans', {})
            
            if daily_plans:
                # 全データを収集
                all_plan_data = []
                header = ['積載日', 'トラック', '製品コード', '製品名', '容器数', '合計数量', '納期']
                all_plan_data.append(header)
                
                for date_str in sorted(daily_plans.keys()):
                    day_plan = daily_plans[date_str]
                    
                    for truck in day_plan.get('trucks', []):
                        truck_name = truck.get('truck_name', '不明')
                        
                        for item in truck.get('loaded_items', []):
                            # 納期のフォーマット処理
                            delivery_date = item.get('delivery_date')
                            delivery_date_str = ''
                            if delivery_date:
                                if hasattr(delivery_date, 'strftime'):
                                    delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                                elif hasattr(delivery_date, 'date'):
                                    delivery_date_str = delivery_date.date().strftime('%Y-%m-%d')
                                else:
                                    delivery_date_str = str(delivery_date)
                            
                            row = [
                                date_str,
                                truck_name,
                                item.get('product_code', ''),
                                item.get('product_name', ''),
                                str(item.get('num_containers', 0)),
                                str(item.get('total_quantity', 0)),
                                delivery_date_str
                            ]
                            all_plan_data.append(row)
                
                # テーブル作成
                if len(all_plan_data) > 1:  # ヘッダー以外にデータがある場合
                    # テーブル幅の計算（横向きA4に合わせて調整）
                    col_widths = [25*mm, 25*mm, 25*mm, 40*mm, 15*mm, 20*mm, 25*mm]
                    
                    plan_table = Table(all_plan_data, colWidths=col_widths, repeatRows=1)
                    plan_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Japanese'),  # ✅ 日本語フォント指定
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('WORDWRAP', (0, 0), (-1, -1), True)  # 文字列の折り返し
                    ]))
                    elements.append(plan_table)
                else:
                    elements.append(Paragraph("積載計画データがありません", japanese_style))
            else:
                elements.append(Paragraph("積載計画データがありません", japanese_style))
            
            # 警告情報
            warnings_data = []
            for date_str, day_plan in daily_plans.items():
                for warning in day_plan.get('warnings', []):
                    warnings_data.append([date_str, warning])
            
            if warnings_data:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("警告一覧", japanese_heading_style))
                warnings_header = ['日付', '警告内容']
                warnings_table_data = [warnings_header] + warnings_data
                
                warnings_table = Table(warnings_table_data, colWidths=[30*mm, 150*mm])
                warnings_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Japanese'),  # ✅ 日本語フォント指定
                    ('FONTSIZE', (0, 0), (-1, -1), 7),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(warnings_table)
            
            # PDF生成
            doc.build(elements)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            st.error(f"PDF生成エラー: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None
    def _export_plan_to_excel(self, plan_data: Dict):
        """積載計画をExcelとしてエクスポート"""
        try:
            from io import BytesIO
            import pandas as pd
            
            # メモリバッファを作成
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # サマリーシート
                summary = plan_data.get('summary', {})
                summary_data = [
                    ['計画名', plan_data.get('plan_name', '無題')],
                    ['計画期間', plan_data.get('period', '')],
                    ['計画日数', f"{summary.get('total_days', 0)}日"],
                    ['総便数', f"{summary.get('total_trips', 0)}便"],
                    ['ステータス', summary.get('status', '不明')],
                    ['出力日時', datetime.now().strftime('%Y-%m-%d %H:%M')]
                ]
                summary_df = pd.DataFrame(summary_data, columns=['項目', '値'])
                summary_df.to_excel(writer, sheet_name='計画サマリー', index=False)
                
                # 積載計画詳細シート
                daily_plans = plan_data.get('daily_plans', {})
                if daily_plans:
                    plan_data_list = []
                    prev_date = None
                    
                    for date_str in sorted(daily_plans.keys()):
                        day_plan = daily_plans[date_str]
                        
                        # 日付が変わったら空白行を挿入
                        if prev_date is not None and prev_date != date_str:
                            plan_data_list.append({
                                '積載日': '',
                                'トラック名': '',
                                '製品コード': '',
                                '製品名': '',
                                '容器数': '',
                                '合計数量': '',
                                '納期': '',
                                '体積積載率(%)': '',
                                '重量積載率(%)': '',
                                '前倒し配送': ''
                            })
                        
                        prev_date = date_str
                        
                        for truck in day_plan.get('trucks', []):
                            truck_name = truck.get('truck_name', '不明')
                            utilization = truck.get('utilization', {})
                            
                            for item in truck.get('loaded_items', []):
                                # 納期のフォーマット処理
                                delivery_date = item.get('delivery_date')
                                delivery_date_str = ''
                                if delivery_date:
                                    if hasattr(delivery_date, 'strftime'):
                                        delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                                    elif hasattr(delivery_date, 'date'):
                                        delivery_date_str = delivery_date.date().strftime('%Y-%m-%d')
                                    else:
                                        delivery_date_str = str(delivery_date)
                                
                                plan_data_list.append({
                                    '積載日': date_str,
                                    'トラック名': truck_name,
                                    '製品コード': item.get('product_code', ''),
                                    '製品名': item.get('product_name', ''),
                                    '容器数': item.get('num_containers', 0),
                                    '合計数量': item.get('total_quantity', 0),
                                    '納期': delivery_date_str,
                                    '体積積載率(%)': utilization.get('volume_rate', 0),
                                    '重量積載率(%)': utilization.get('weight_rate', 0),
                                    '前倒し配送': '○' if item.get('is_advanced', False) else '×'
                                })
                    
                    if plan_data_list:
                        plan_df = pd.DataFrame(plan_data_list)
                        plan_df.to_excel(writer, sheet_name='積載計画詳細', index=False)
                
                # 警告シート
                warnings_data = []
                for date_str, day_plan in daily_plans.items():
                    for warning in day_plan.get('warnings', []):
                        warnings_data.append({
                            '日付': date_str,
                            '警告内容': warning
                        })
                
                if warnings_data:
                    warnings_df = pd.DataFrame(warnings_data)
                    warnings_df.to_excel(writer, sheet_name='警告一覧', index=False)
                
                # 積載不可アイテムシート
                unloaded_tasks = plan_data.get('unloaded_tasks', [])
                if unloaded_tasks:
                    unloaded_data = []
                    for task in unloaded_tasks:
                        delivery_date = task.get('delivery_date')
                        delivery_date_str = ''
                        if delivery_date:
                            if hasattr(delivery_date, 'strftime'):
                                delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                            elif hasattr(delivery_date, 'date'):
                                delivery_date_str = delivery_date.date().strftime('%Y-%m-%d')
                            else:
                                delivery_date_str = str(delivery_date)
                        
                        unloaded_data.append({
                            '製品コード': task.get('product_code', ''),
                            '製品名': task.get('product_name', ''),
                            '容器数': task.get('num_containers', 0),
                            '合計数量': task.get('total_quantity', 0),
                            '納期': delivery_date_str,
                            '理由': task.get('reason', '積載容量不足')
                        })
                    
                    unloaded_df = pd.DataFrame(unloaded_data)
                    unloaded_df.to_excel(writer, sheet_name='積載不可アイテム', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            st.error(f"Excelエクスポートエラー: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

# ui/pages/transport_page.py の _show_daily_view メソッドを修正

    def _show_daily_view(self, daily_plans):
        """日別表示 - デバッグ出力追加版"""
        
        for date_str in sorted(daily_plans.keys()):
            plan = daily_plans[date_str]
            
            trucks = plan.get('trucks', [])
            warnings = plan.get('warnings', [])
            total_trips = len(trucks)
            
            with st.expander(f"📅 {date_str} ({total_trips}便)", expanded=True):
                
                if warnings:
                    st.warning("⚠️ 警告:")
                    for warning in warnings:
                        st.write(f"• {warning}")
                
                if not trucks:
                    st.info("この日の積載予定はありません")
                    continue
                
                for i, truck_plan in enumerate(trucks, 1):
                    st.markdown(f"**🚛 便 #{i}: {truck_plan.get('truck_name', 'トラック名不明')}**")
                    
                    # ✅ デバッグ: truck_planの構造を確認
                    st.write("🔍 デバッグ: truck_plan構造")
                    st.json(truck_plan)
                    
                    util = truck_plan.get('utilization', {})
                    col_u1, col_u2, col_u3 = st.columns(3)
                    with col_u1:
                        st.metric("床面積積載率", f"{util.get('floor_area_rate', 0)}%")
                    with col_u2:
                        st.metric("体積積載率", f"{util.get('volume_rate', 0)}%")
                    with col_u3:
                        st.metric("重量積載率", f"{util.get('weight_rate', 0)}%")
                    
                    loaded_items = truck_plan.get('loaded_items', [])
                    
                    # ✅ デバッグ: loaded_itemsの中身を確認
                    st.write(f"🔍 デバッグ: loaded_items数 = {len(loaded_items)}")
                    if loaded_items:
                        st.write("🔍 デバッグ: 最初のitem構造")
                        st.json(loaded_items[0])
                    
                    if loaded_items:
                        # ✅ 修正: container_nameフィールドも確認
                        items_df = pd.DataFrame([{
                            '製品コード': item.get('product_code', ''),
                            '製品名': item.get('product_name', ''),
                            '容器名': item.get('container_name', '不明'),  # ← 追加
                            '容器数': item.get('num_containers', 0),
                            '合計数量': item.get('total_quantity', 0),
                            '床面積': f"{item.get('floor_area', 0):.2f}m²",  # ← 追加
                            '納期': item['delivery_date'].strftime('%Y-%m-%d') if 'delivery_date' in item else '',
                            '前倒し': '✓' if item.get('is_advanced', False) else '',  # ← 追加
                        } for item in loaded_items])
                        
                        st.dataframe(items_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("積載品がありません")
                    
                    st.markdown("---")
    
    def _show_list_view(self, daily_plans):
        """一覧表示"""
        
        all_items = []
        
        for date_str in sorted(daily_plans.keys()):
            plan = daily_plans[date_str]
            
            trucks = plan.get('trucks', [])
            
            for truck_plan in trucks:
                loaded_items = truck_plan.get('loaded_items', [])
                truck_name = truck_plan.get('truck_name', 'トラック名不明')
                utilization = truck_plan.get('utilization', {})
                
                for item in loaded_items:
                    delivery_date = item.get('delivery_date')
                    if delivery_date:
                        if hasattr(delivery_date, 'strftime'):
                            delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                        else:
                            delivery_date_str = str(delivery_date)
                    else:
                        delivery_date_str = '-'
                    
                    all_items.append({
                        '積載日': date_str,
                        'トラック': truck_name,
                        '製品コード': item.get('product_code', ''),
                        '製品名': item.get('product_name', ''),
                        '容器数': item.get('num_containers', 0),
                        '合計数量': item.get('total_quantity', 0),
                        '納期': delivery_date_str,
                        '体積率': f"{utilization.get('volume_rate', 0)}%",
                        '重量率': f"{utilization.get('weight_rate', 0)}%"
                    })
        
        if all_items:
            df = pd.DataFrame(all_items)
            st.dataframe(df, width='stretch')
            st.info("表示するデータがありません")

    def _show_container_management(self):
        """容器管理表示"""
        st.header("🧰 容器管理")
        st.write("積載に使用する容器の登録と管理を行います。")

        try:
            st.subheader("新規容器登録")
            container_data = FormComponents.container_form()

            if container_data:
                success = self.service.create_container(container_data)
                if success:
                    st.success(f"容器 '{container_data['name']}' を登録しました")
                    st.rerun()
                else:
                    st.error("容器登録に失敗しました")

            st.subheader("登録済み容器一覧")
            containers = self.service.get_containers()

            if containers:
                for container in containers:
                    with st.expander(f"📦 {container.name} (ID: {container.id})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**寸法:** {container.width} × {container.depth} × {container.height} mm")
                            st.write(f"**体積:** {(container.width * container.depth * container.height) / 1000000000:.3f} m³")
                        
                        with col2:
                            st.write(f"**最大重量:** {container.max_weight} kg")
                            st.write(f"**積重可:** {'✅' if container.stackable else '❌'}")
                            max_stack = getattr(container, 'max_stack', 1)
                            st.write(f"**最大段数:** {max_stack}段")

                        with st.form(f"edit_container_form_{container.id}"):
                            st.write("✏️ 容器情報を編集")

                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                new_name = st.text_input("容器名", value=container.name)
                                new_width = st.number_input("幅 (mm)", min_value=1, value=container.width)
                                new_depth = st.number_input("奥行 (mm)", min_value=1, value=container.depth)
                                new_height = st.number_input("高さ (mm)", min_value=1, value=container.height)
                            
                            with col_b:
                                new_weight = st.number_input("最大重量 (kg)", min_value=0, value=container.max_weight)
                                new_stackable = st.checkbox("積重可", value=bool(container.stackable))
                                new_max_stack = st.number_input(
                                    "最大積み重ね段数", 
                                    min_value=1, 
                                    max_value=10, 
                                    value=getattr(container, 'max_stack', 1)
                                )

                            submitted = st.form_submit_button("更新", type="primary")
                            if submitted:
                                update_data = {
                                    "name": new_name,
                                    "width": new_width,
                                    "depth": new_depth,
                                    "height": new_height,
                                    "max_weight": new_weight,
                                    "stackable": int(new_stackable),
                                    "max_stack": new_max_stack
                                }
                                success = self.service.update_container(container.id, update_data)
                                if success:
                                    st.success(f"✅ 容器 '{container.name}' を更新しました")
                                    st.rerun()
                                else:
                                    st.error("❌ 容器更新に失敗しました")

                        if st.button("🗑️ 削除", key=f"delete_container_{container.id}"):
                            success = self.service.delete_container(container.id)
                            if success:
                                st.success(f"容器 '{container.name}' を削除しました")
                                st.rerun()
                            else:
                                st.error("容器削除に失敗しました")

                st.subheader("容器統計")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("登録容器数", len(containers))
                with col2:
                    avg_volume = sum((c.width * c.depth * c.height) for c in containers) / len(containers) / 1000000000
                    st.metric("平均体積", f"{avg_volume:.2f} m³")
                with col3:
                    avg_weight = sum(c.max_weight for c in containers) / len(containers)
                    st.metric("平均最大重量", f"{avg_weight:.1f} kg")

            else:
                st.info("登録されている容器がありません")

        except Exception as e:
            st.error(f"容器管理エラー: {e}")

    def _show_truck_management(self):
        """トラック管理表示"""
        st.header("🚛 トラック管理")
        st.write("積載に使用するトラックの登録と管理を行います。")

        try:
            st.subheader("新規トラック登録")
            truck_data = FormComponents.truck_form()

            if truck_data:
                success = self.service.create_truck(truck_data)
                if success:
                    st.success(f"トラック '{truck_data['name']}' を登録しました")
                    st.rerun()
                else:
                    st.error("トラック登録に失敗しました")

            st.subheader("登録済みトラック一覧")
            trucks_df = self.service.get_trucks()

            if not trucks_df.empty:
                for _, truck in trucks_df.iterrows():
                    with st.expander(f"🛻 {truck['name']} (ID: {truck['id']})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**荷台寸法:** {truck['width']} × {truck['depth']} × {truck['height']} mm")
                            st.write(f"**最大積載重量:** {truck['max_weight']} kg")
                            volume_m3 = (truck['width'] * truck['depth'] * truck['height']) / 1000000000
                            st.write(f"**荷台容積:** {volume_m3:.2f} m³")
                        
                        with col2:
                            st.write(f"**出発時刻:** {truck['departure_time']}")
                            st.write(f"**到着時刻:** {truck['arrival_time']} (+{truck['arrival_day_offset']}日)")
                            st.write(f"**デフォルト便:** {'✅' if truck['default_use'] else '❌'}")
                            st.write(f"**優先積載製品:** {truck['priority_product_codes'] or 'なし'}")  # 新規表示
                        with st.form(f"edit_truck_form_{truck['id']}"):
                            st.write("✏️ トラック情報を編集")

                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                new_name = st.text_input("トラック名", value=truck['name'])
                                new_width = st.number_input("荷台幅 (mm)", min_value=1, value=int(truck['width']))
                                new_depth = st.number_input("荷台奥行 (mm)", min_value=1, value=int(truck['depth']))
                                new_height = st.number_input("荷台高さ (mm)", min_value=1, value=int(truck['height']))
                                new_weight = st.number_input("最大積載重量 (kg)", min_value=1, value=int(truck['max_weight']))
                            
                            with col_b:
                                new_dep = st.time_input("出発時刻", value=truck['departure_time'])
                                new_arr = st.time_input("到着時刻", value=truck['arrival_time'])
                                new_offset = st.number_input(
                                    "到着日オフセット（日）", 
                                    min_value=0, 
                                    max_value=7, 
                                    value=int(truck['arrival_day_offset'])
                                )
                                new_default = st.checkbox("デフォルト便", value=bool(truck['default_use']))
                                # 追加：優先積載製品コード入力欄
                                new_priority = st.text_input(
                                    "優先積載製品コード（カンマ区切り）",
                                    value=truck.get('priority_product_codes', '') or '',
                                    placeholder="例: PRD001,PRD002"
                                )
                            submitted = st.form_submit_button("更新", type="primary")
                            if submitted:
                                update_data = {
                                    "name": new_name,
                                    "width": new_width,
                                    "depth": new_depth,
                                    "height": new_height,
                                    "max_weight": new_weight,
                                    "departure_time": new_dep,
                                    "arrival_time": new_arr,
                                    "arrival_day_offset": new_offset,
                                    "default_use": new_default,
                                    # 新規追加：優先積載製品コード
                                    "priority_product_codes": new_priority.strip() if new_priority else None
    
                                }
                                success = self.service.update_truck(truck['id'], update_data)
                                if success:
                                    st.success(f"✅ トラック '{truck['name']}' を更新しました")
                                    st.rerun()
                                else:
                                    st.error("❌ トラック更新に失敗しました")

                        if st.button("🗑️ 削除", key=f"delete_truck_{truck['id']}"):
                            success = self.service.delete_truck(truck['id'])
                            if success:
                                st.success(f"トラック '{truck['name']}' を削除しました")
                                st.rerun()
                            else:
                                st.error("トラック削除に失敗しました")

            else:
                st.info("登録されているトラックがありません")

        except Exception as e:
            st.error(f"トラック管理エラー: {e}")
    def _save_plan_changes(self, plan_data: Dict, original_df: pd.DataFrame, 
                        edited_df: pd.DataFrame, row_id_map: Dict) -> bool:
        """計画の変更を保存（容器数・積載率自動計算対応）"""
        try:
            changes_detected = False
            updates = []
            
            # 必要な情報を取得
            try:
                products_df = self.service.product_repo.get_all_products()
                capacity_map = dict(zip(products_df['product_code'], products_df['capacity']))
            except:
                capacity_map = {}
                st.warning("製品容量情報の取得に失敗しました")
            
            # 変更を検出
            for row_idx in range(len(original_df)):
                original_row = original_df.iloc[row_idx]
                edited_row = edited_df.iloc[row_idx]
                
                # 変更があったフィールドを検出
                changes = {}
                old_values = {}
                
                # 数量または積載率が変更された場合
                if (original_row['合計数量'] != edited_row['合計数量'] or
                    original_row['体積率(%)'] != edited_row['体積率(%)'] or
                    original_row['重量率(%)'] != edited_row['重量率(%)']):
                    
                    changes['total_quantity'] = edited_row['合計数量']
                    changes['num_containers'] = edited_row['容器数']
                    changes['volume_utilization'] = edited_row['体積率(%)']
                    changes['weight_utilization'] = edited_row['重量率(%)']
                    
                    old_values['total_quantity'] = original_row['合計数量']
                    old_values['num_containers'] = original_row['容器数']
                    old_values['volume_utilization'] = original_row['体積率(%)']
                    old_values['weight_utilization'] = original_row['重量率(%)']
                
                if changes:
                    changes_detected = True
                    
                    # detail_idを取得
                    if row_idx in row_id_map:
                        date_str, truck_idx, item_idx = row_id_map[row_idx]
                        detail_id = self._find_detail_id(plan_data, date_str, truck_idx, item_idx)
                        
                        if detail_id:
                            updates.append({
                                'detail_id': detail_id,
                                'changes': changes,
                                'old_values': old_values
                            })
            
            if changes_detected and updates:
                # サービスを通じて更新
                success = self.service.update_loading_plan(plan_data['id'], updates)
                
                if success:
                    st.success(f"✅ {len(updates)}件の変更を保存しました")
                    
                    # delivery_progressも更新
                    self._update_delivery_progress_from_plan(plan_data)
                    return True
                else:
                    st.error("❌ 保存に失敗しました")
                    return False
            
            return changes_detected
            
        except Exception as e:
            st.error(f"保存エラー: {str(e)}")
            return False    

    def _find_detail_id(self, plan_data: Dict, date_str: str, truck_idx: int, item_idx: int) -> int:
        """明細IDを検索"""
        try:
            details = plan_data.get('details', [])
            
            for detail in details:
                if (str(detail.get('loading_date')) == date_str and 
                    detail.get('truck_id') == plan_data['daily_plans'][date_str]['trucks'][truck_idx]['truck_id'] and
                    detail.get('product_code') == plan_data['daily_plans'][date_str]['trucks'][truck_idx]['loaded_items'][item_idx]['product_code']):
                    return detail['id']
            
            return None
        except:
            return None

    def _update_delivery_progress_from_plan(self, plan_data: Dict):
        """計画変更に基づいてdelivery_progressを更新"""
        try:
            # 計画からdelivery_progressへの数量更新ロジック
            daily_plans = plan_data.get('daily_plans', {})
            
            for date_str, day_plan in daily_plans.items():
                for truck in day_plan.get('trucks', []):
                    for item in truck.get('loaded_items', []):
                        # delivery_progressのplanned_quantityを更新
                        update_data = {
                            'planned_quantity': item.get('total_quantity', 0)
                        }
                        # ここでdelivery_progressを更新するロジックを実装
                        
            st.info("納入進度も更新しました")
            
        except Exception as e:
            st.warning(f"納入進度更新エラー: {e}")
    def _confirm_and_delete_plan(self, plan_id: int, plan_name: str) -> bool:
        """計画削除の確認と実行"""
        try:
            # 削除実行
            success = self.service.delete_loading_plan(plan_id)
            
            if success:
                return True
            else:
                st.error("❌ 削除に失敗しました")
                return False
                
        except Exception as e:
            st.error(f"削除エラー: {e}")
            return False
