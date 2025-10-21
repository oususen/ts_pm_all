# app/ui/pages/calendar_page.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from services.calendar_import_service import CalendarImportService

class CalendarPage:
    """会社カレンダー管理ページ"""
    
    def __init__(self, db_manager, auth_service=None):
        self.import_service = CalendarImportService(db_manager)
        self.calendar_repo = self.import_service.calendar_repo
        self.auth_service = auth_service

    def _can_edit_page(self) -> bool:
        """ページ編集権限チェック"""
        if not self.auth_service:
            return True
        user = st.session_state.get('user')
        if not user:
            return False
        return self.auth_service.can_edit_page(user['id'], "📅 会社カレンダー")
    
    def show(self):
        """ページ表示"""
        st.title("📅 会社カレンダー管理")
        st.write("会社のExcelカレンダーをインポートして、運送便計画に反映させます。")

        # 権限チェック
        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("⚠️ この画面の編集権限がありません。閲覧のみ可能です。")

        tab1, tab2, tab3, tab4 = st.tabs([
            "📥 Excelインポート",
            "📆 カレンダー表示",
            "➕ 手動追加",
            "📊 年間サマリー"
        ])

        with tab1:
            self._show_excel_import(can_edit)
        with tab2:
            self._show_calendar_view()
        with tab3:
            self._show_manual_add(can_edit)
        with tab4:
            self._show_yearly_summary()
    
    def _show_excel_import(self, can_edit):
        """Excelインポート"""
        st.header("📥 会社カレンダーExcelインポート")

        if not can_edit:
            st.info("編集権限がないため、インポートはできません")
            return
        
        st.info("""
        **対応フォーマット:**
        - 日付カラム: 日付
        - 状態カラム: 状態（「出」=営業日、「休」=休日）
        - オプション: 曜日、備考など
        
        **既存のSharePointカレンダーをそのままインポートできます！**
        """)
        
        # ファイルアップロード
        uploaded_file = st.file_uploader(
            "Excelファイルを選択（calendar.xlsx）",
            type=['xlsx', 'xls'],
            help="会社カレンダーのExcelファイルをアップロード"
        )
        
        if uploaded_file:
            try:
                # プレビュー表示
                df_preview = pd.read_excel(uploaded_file, nrows=10)
                uploaded_file.seek(0)
                
                st.subheader("📋 プレビュー（先頭10行）")
                st.dataframe(df_preview, use_container_width=True)
                
                # 統計情報
                df_full = pd.read_excel(uploaded_file)
                uploaded_file.seek(0)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総行数", len(df_full))
                with col2:
                    working_days = len(df_full[df_full['状態'] == '出'])
                    st.metric("営業日数", working_days)
                with col3:
                    holidays = len(df_full[df_full['状態'] == '休'])
                    st.metric("休日数", holidays)
                
                st.markdown("---")
                
                # インポートオプション
                overwrite = st.checkbox(
                    "既存データを上書き",
                    value=False,
                    help="チェックすると既存のカレンダーデータを削除して新規登録します"
                )
                
                if overwrite:
                    st.warning("⚠️ 既存のカレンダーデータがすべて削除されます")
                
                # インポート実行
                col_btn1, col_btn2 = st.columns([1, 3])
                
                with col_btn1:
                    if st.button("🔄 インポート実行", type="primary", use_container_width=True):
                        with st.spinner("カレンダーをインポート中..."):
                            uploaded_file.seek(0)
                            success, message = self.import_service.import_excel_calendar(
                                uploaded_file,
                                overwrite=overwrite
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                
                                # サマリー表示
                                self._show_import_summary(df_full)
                            else:
                                st.error(message)
            
            except Exception as e:
                st.error(f"ファイル読み込みエラー: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    def _show_import_summary(self, df: pd.DataFrame):
        """インポート後のサマリー表示"""
        st.subheader("📊 インポート結果")
        
        # 日付範囲
        dates = pd.to_datetime(df['日付'])
        start_date = dates.min().date()
        end_date = dates.max().date()
        
        st.write(f"**期間:** {start_date} ～ {end_date}")
        
        # 月別集計
        df['年月'] = pd.to_datetime(df['日付']).dt.to_period('M')
        monthly = df.groupby('年月')['状態'].apply(
            lambda x: pd.Series({
                '営業日': (x == '出').sum(),
                '休日': (x == '休').sum()
            })
        ).unstack()
        
        st.dataframe(monthly, use_container_width=True)
    
    def _show_calendar_view(self):
        """カレンダー表示"""
        st.header("📆 カレンダー表示")
        
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "開始日",
                value=date.today().replace(day=1),
                key="cal_start"
            )
        
        with col2:
            end_date = st.date_input(
                "終了日",
                value=date.today() + timedelta(days=90),
                key="cal_end"
            )
        
        if st.button("🔍 カレンダー表示", type="primary"):
            df = self.calendar_repo.get_calendar_range(start_date, end_date)
            
            if not df.empty:
                # サマリー
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1:
                    total_days = len(df)
                    st.metric("総日数", f"{total_days}日")
                with col_s2:
                    working_days = len(df[df['is_working_day'] == True])
                    st.metric("営業日数", f"{working_days}日")
                with col_s3:
                    holidays = len(df[df['is_working_day'] == False])
                    st.metric("休日数", f"{holidays}日")
                with col_s4:
                    rate = (working_days / total_days * 100) if total_days > 0 else 0
                    st.metric("稼働率", f"{rate:.1f}%")
                
                # カレンダー表示
                df['日付'] = pd.to_datetime(df['calendar_date']).dt.date
                df['曜日'] = pd.to_datetime(df['calendar_date']).dt.day_name().map({
                    'Monday': '月', 'Tuesday': '火', 'Wednesday': '水',
                    'Thursday': '木', 'Friday': '金', 'Saturday': '土', 'Sunday': '日'
                })
                df['状態'] = df['is_working_day'].apply(lambda x: '出' if x else '休')
                
                display_df = df[['日付', '曜日', '状態', 'day_type', 'day_name']]
                display_df.columns = ['日付', '曜日', '状態', '区分', '名称']
                
                # 色分け表示
                def highlight_row(row):
                    if row['状態'] == '出':
                        return ['background-color: #e8f5e9'] * len(row)
                    else:
                        return ['background-color: #ffebee'] * len(row)
                
                st.dataframe(
                    display_df.style.apply(highlight_row, axis=1),
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
                
                # Excel出力
                if st.button("📥 Excelダウンロード"):
                    export_df = self.import_service.export_calendar_to_excel(start_date, end_date)
                    
                    # Excelに変換
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        export_df.to_excel(writer, index=False, sheet_name='カレンダー')
                    output.seek(0)
                    
                    st.download_button(
                        "⬇️ ダウンロード",
                        output,
                        f"会社カレンダー_{start_date}_{end_date}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.info("指定期間のカレンダーデータがありません")
    
    def _show_manual_add(self, can_edit):
        """手動追加"""
        st.header("➕ 休日・営業日の手動追加")

        if not can_edit:
            st.info("編集権限がないため、手動追加はできません")
            return
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader("🚫 休日を追加")
            
            with st.form("add_holiday_form"):
                holiday_date = st.date_input("日付")
                day_type = st.selectbox(
                    "区分",
                    options=['祝日', '休日', '特別休業']
                )
                day_name = st.text_input("名称", placeholder="例: 創立記念日")
                notes = st.text_area("備考")
                
                if st.form_submit_button("休日を追加", type="primary"):
                    success = self.calendar_repo.add_holiday(
                        holiday_date, day_type, day_name, notes
                    )
                    if success:
                        st.success(f"✅ {holiday_date} を休日として登録しました")
                        st.rerun()
                    else:
                        st.error("休日追加に失敗しました")
        
        with col_b:
            st.subheader("✅ 営業日を追加")
            st.write("土日や祝日を営業日にする場合に使用")
            
            with st.form("add_working_day_form"):
                working_date = st.date_input("日付", key="working_date")
                working_notes = st.text_area("備考", placeholder="例: 祝日振替出勤", key="working_notes")
                
                if st.form_submit_button("営業日を追加", type="primary"):
                    success = self.calendar_repo.add_working_day(
                        working_date, working_notes
                    )
                    if success:
                        st.success(f"✅ {working_date} を営業日として登録しました")
                        st.rerun()
                    else:
                        st.error("営業日追加に失敗しました")
    
    def _show_yearly_summary(self):
        """年間サマリー"""
        st.header("📊 年間カレンダーサマリー")
        
        year = st.selectbox(
            "年を選択",
            options=list(range(2024, 2030)),
            index=1  # 2025
        )
        
        if st.button("📊 サマリー表示", type="primary"):
            summary = self.import_service.get_calendar_summary(year)
            
            if summary['total_days'] > 0:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("総日数", f"{summary['total_days']}日")
                with col2:
                    st.metric("営業日数", f"{summary['working_days']}日")
                with col3:
                    st.metric("休日数", f"{summary['holidays']}日")
                with col4:
                    st.metric("稼働率", f"{summary['working_rate']}%")
                
                # 月別グラフ表示
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
                df = self.calendar_repo.get_calendar_range(start_date, end_date)
                
                if not df.empty:
                    df['年月'] = pd.to_datetime(df['calendar_date']).dt.to_period('M')
                    monthly = df.groupby(['年月', 'is_working_day']).size().unstack(fill_value=0)
                    
                    if True in monthly.columns and False in monthly.columns:
                        monthly.columns = ['休日', '営業日']
                        st.bar_chart(monthly)
            else:
                st.info(f"{year}年のカレンダーデータがありません")