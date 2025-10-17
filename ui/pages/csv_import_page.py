# app/ui/pages/csv_import_page.py
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.csv_import_service import CSVImportService
from services.transport_service import TransportService

class CSVImportPage:
    """CSV受注インポートページ"""
    
    def __init__(self, db_manager):
        self.import_service = CSVImportService(db_manager)
        self.service = TransportService(db_manager)    
    def show(self):
        """ページ表示"""
        st.title("📥 受注CSVインポート")
        st.write("お客様からのCSVファイルを読み込み、生産指示データとして登録します。")
        
        tab1, tab2, tab3 = st.tabs(["📤 ファイルアップロード", "📊 インポート履歴", "ℹ️ 使い方"])
        
        with tab1:
            self._show_upload_form()
        with tab2:
            self._show_import_history()
        with tab3:
            self._show_instructions()
    
    def _show_upload_form(self):
        """アップロードフォーム表示"""
        st.header("📤 CSVファイルアップロード")
        
        st.info("""
        **対応フォーマット:**
        - エンコーディング: Shift-JIS
        - レコード識別: V2（日付）、V3（数量）
        - 必須カラム: データＮＯ、品番、検査区分、スタート月度など
        
        **インポート仕様:**
        - 既存データに追加されます
        - 同じ製品コード×日付のデータは数量が合算されます
        - 検査区分が違っても製品コードが同じなら納入進度では統合されます
        """)
        with st.expander("計画進度の再計算"):
            product_id = st.number_input("製品ID", min_value=1, step=1, key="recalc_product_id_upload")
            recal_start_date = st.date_input("再計算開始日", key="recalc_start_date_upload")
            recal_end_date = st.date_input("再計算終了日", key="recalc_end_date_upload")

            col_recalc_single, col_recalc_all = st.columns(2)

            with col_recalc_single:
                if st.button("選択製品のみ再計算", key="recalc_single_upload"):
                    self.service.recompute_planned_progress(product_id, recal_start_date, recal_end_date)
                    st.success("再計算が完了しました")

            with col_recalc_all:
                if st.button("全製品を再計算", key="recalc_all_upload"):
                    self.service.recompute_planned_progress_all(recal_start_date, recal_end_date)
                    st.success("全ての製品に対する再計算が完了しました")
        # ファイルアップロード
        uploaded_file = st.file_uploader(
            "CSVファイルを選択",
            type=['csv'],
            help="Shift-JIS形式のCSVファイルをアップロードしてください"
        )
        
        if uploaded_file is not None:
            # プレビュー表示
            try:
                df_preview = pd.read_csv(uploaded_file, encoding='shift_jis', nrows=10)
                uploaded_file.seek(0)
                
                st.subheader("📋 プレビュー（先頭10行）")
                st.dataframe(df_preview, use_container_width=True, height=200)
                
                # レコード識別の確認
                v2_count = len(df_preview[df_preview['レコード識別'] == 'V2'])
                v3_count = len(df_preview[df_preview['レコード識別'] == 'V3'])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総行数", len(df_preview))
                with col2:
                    st.metric("V2行（日付）", v2_count)
                with col3:
                    st.metric("V3行（数量）", v3_count)
                
                st.markdown("---")
                
                # インポートオプション
                st.subheader("⚙️ インポートオプション")
                
                create_progress = st.checkbox(
                    "納入進度も同時作成",
                    value=True,
                    help="生産指示データから納入進度データも自動生成します（製品コードで統合）"
                )
                
                st.info("""
                **📌 インポート処理の詳細:**
                - 製品マスタ: 検査区分ごとに別製品として登録
                - 生産指示: 検査区分ごとに分けて登録
                - 納入進度: 同じ製品コードなら検査区分が違っても統合（数量合計）
                """)
                
                # インポート実行ボタン
                st.markdown("---")
                
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                
                with col_btn1:
                    if st.button("🔄 インポート実行", type="primary", use_container_width=True):
                        with st.spinner("データをインポート中..."):
                            try:
                                uploaded_file.seek(0)
                                
                                success, message = self.import_service.import_csv_data(
                                    uploaded_file,
                                    create_progress=create_progress
                                )
                                
                                if success:
                                    st.success(f"✅ {message}")
                                    st.balloons()
                                    
                                    self._log_import_history(uploaded_file.name, message)
                                    
                                    # 検査対象製品を表示
                                    self._show_inspection_products_after_import()
                                    
                                    st.info("💡 「配送便計画」ページでデータを確認してください")
                                else:
                                    st.error(f"❌ {message}")
                            
                            except Exception as e:
                                st.error(f"予期しないエラー: {e}")
                                import traceback
                                st.code(traceback.format_exc())
                
                with col_btn2:
                    if st.button("🗑️ キャンセル", use_container_width=True):
                        st.rerun()
                
            except Exception as e:
                st.error(f"ファイル読み込みエラー: {e}")
                st.info("ファイルがShift-JIS形式であることを確認してください")
                
            
    def _show_inspection_products_after_import(self):
        """インポート後に検査対象製品（F/$含む）を表示"""
        from sqlalchemy import text
        
        session = self.import_service.db.get_session()
        with st.expander("計画進度の再計算"):
            product_id = st.number_input("製品ID", min_value=1, step=1, key="recalc_product_id_inspection")
            recal_start_date = st.date_input("再計算開始日", key="recalc_start_date_inspection")
            recal_end_date = st.date_input("再計算終了日", key="recalc_end_date_inspection")

            col_recalc_single, col_recalc_all = st.columns(2)

            with col_recalc_single:
                if st.button("選択製品のみ再計算", key="recalc_single_inspection"):
                    self.service.recompute_planned_progress(product_id, recal_start_date, recal_end_date)
                    st.success("再計算が完了しました")

            with col_recalc_all:
                if st.button("全製品を再計算", key="recalc_all_inspection"):
                    self.service.recompute_planned_progress_all(recal_start_date, recal_end_date)
                    st.success("全ての製品に対する再計算が完了しました")
        
        try:
            # 日付範囲を調整（当日～1ヶ月後）
            today = date.today()-timedelta(days=30)
            end_date = today + timedelta(days=30)
            
            # production_instructions_detailテーブルから直接検査区分を取得
            query = text("""
                SELECT 
                    pid.instruction_date as 日付,
                    pid.id as 指示ID,
                    pid.inspection_category as 検査区分,
                    pid.instruction_quantity as 受注数,
                    p.product_code as 製品コード,
                    p.product_name as 製品名
                FROM production_instructions_detail pid
                LEFT JOIN products p ON pid.product_id = p.id
                WHERE pid.instruction_date BETWEEN :start_date AND :end_date
                    AND (pid.inspection_category LIKE '%F%' OR pid.inspection_category LIKE '%$%')
                ORDER BY pid.instruction_date, pid.inspection_category
            """)
            
            result = session.execute(query, {
                'start_date': today.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            })
            
            rows = result.fetchall()
            
            if rows:
                st.warning("⚠️ 検査対象製品（F/$含む）が含まれています")
                
                df = pd.DataFrame(rows, columns=result.keys())
                df['日付'] = pd.to_datetime(df['日付']).dt.date
                
                # 検査区分ごとの集計
                f_products = df[df['検査区分'].str.contains('F', na=False)]
                dollar_products = df[df['検査区分'].str.contains(r'\$', regex=True, na=False)]
                
                col_sum1, col_sum2, col_sum3 = st.columns(3)
                with col_sum1:
                    f_count = len(f_products)
                    f_total = f_products['受注数'].sum()
                    st.metric("Fを含む（最終検査）", f"{f_count}件 / {f_total:,}個")
                with col_sum2:
                    s_count = len(dollar_products)
                    s_total = dollar_products['受注数'].sum()
                    st.metric("$を含む（目視検査）", f"{s_count}件 / {s_total:,}個")
                with col_sum3:
                    total_count = len(df)
                    total_quantity = df['受注数'].sum()
                    st.metric("総計", f"{total_count}件 / {total_quantity:,}個")
                
                # 検査区分ごとの詳細サマリー
                st.subheader("🔍 検査区分別サマリー")
                category_summary = df.groupby('検査区分').agg({
                    '指示ID': 'count',
                    '受注数': 'sum'
                }).rename(columns={'指示ID': '件数', '受注数': '総数量'}).reset_index()
                
                st.dataframe(
                    category_summary,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "件数": st.column_config.NumberColumn("件数", format="%d件"),
                        "総数量": st.column_config.NumberColumn("総数量", format="%d個"),
                    }
                )
                
                # 日付ごとの集計も表示
                st.subheader("📅 日付別サマリー")
                daily_summary = df.groupby('日付').agg({
                    '指示ID': 'count',
                    '受注数': 'sum'
                }).rename(columns={'指示ID': '件数', '受注数': '総数量'}).reset_index()
                
                st.dataframe(
                    daily_summary,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "日付": st.column_config.DateColumn("日付", format="YYYY-MM-DD"),
                        "件数": st.column_config.NumberColumn("件数", format="%d件"),
                        "総数量": st.column_config.NumberColumn("総数量", format="%d個"),
                    }
                )
                
                # 製品ごとの集計
                st.subheader("📦 製品別サマリー")
                product_summary = df.groupby(['製品コード', '製品名']).agg({
                    '指示ID': 'count',
                    '受注数': 'sum'
                }).rename(columns={'指示ID': '件数', '受注数': '総数量'}).reset_index()
                
                st.dataframe(
                    product_summary,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "件数": st.column_config.NumberColumn("件数", format="%d件"),
                        "総数量": st.column_config.NumberColumn("総数量", format="%d個"),
                    }
                )
                
                st.subheader("📋 詳細データ")
                st.dataframe(
                    df[['日付', '指示ID', '製品コード', '製品名', '検査区分', '受注数']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "日付": st.column_config.DateColumn("日付", format="YYYY-MM-DD"),
                        "受注数": st.column_config.NumberColumn("受注数", format="%d個"),
                    }
                )
                
                # 注意事項
                st.info("""
                **💡 注意事項:**
                - **Fを含む**: 最終検査が必要な製品
                - **$を含む**: 目視検査が必要な製品  
                - これらの製品は特別な検査プロセスが必要です
                - 生産計画時に検査工程の時間を確保してください
                """)
        
        except Exception as e:
            st.error(f"検査対象製品確認エラー: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            session.close()
    
    def _show_import_history(self):
        """インポート履歴表示"""
        st.header("📊 インポート履歴")
        
        try:
            history = self.import_service.get_import_history()
            
            if history:
                history_df = pd.DataFrame(history)
                
                st.dataframe(
                    history_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "インポート日時": st.column_config.DatetimeColumn(
                            "インポート日時",
                            format="YYYY-MM-DD HH:mm:ss"
                        ),
                    }
                )
            else:
                st.info("インポート履歴がありません")
        
        except Exception as e:
            st.error(f"履歴取得エラー: {e}")
    
    def _show_instructions(self):
        """使い方表示"""
        st.header("ℹ️ 使い方")
        
        st.markdown("""
        ## 📋 CSVファイルのフォーマット
        
        ### 必須カラム
        - **レコード識別**: V2（日付行）、V3（数量行）
        - **データＮＯ**: 製品識別番号
        - **品番**: 製品コード
        - **検査区分**: N, NS, FS, F $Sなど
        - **スタート月度**: YYYYMM形式
        
        ### データ構造
        1. **V2行**: 各日付の生産指示日
        2. **V3行**: 各日付の生産指示数量
        
        ### インポート手順
        1. CSVファイルをアップロード
        2. プレビューで内容を確認
        3. インポートオプションを選択
        4. 「インポート実行」ボタンをクリック
        
        ## 📊 データ処理の仕様
        
        ### 製品マスタ登録
        - 検査区分ごとに**別製品**として登録されます
        - 例: 同じ品番でも「N」と「F」は別レコード
        
        ### 生産指示データ
        - 検査区分ごとに**分けて**登録されます
        - `production_instructions_detail`テーブルに格納
        
        ### 納入進度データ
        - 同じ製品コード×日付なら検査区分が違っても**統合**されます
        - 数量は各検査区分の**合計値**となります
        - 例: 品番「ABC123」の「N」100個 + 「F」50個 = 150個として1レコード登録
        
        ## ⚠️ 注意事項
        
        - ファイルは **Shift-JIS** エンコーディングである必要があります
        - インポートは**追加モード**で実行されます（既存データは削除されません）
        - 同じオーダーIDが既に存在する場合は数量が加算されます
        - 大量データの場合は時間がかかることがあります
        
        ## 🔗 関連機能
        
        - インポート後は「納入進度」ページで進捗を確認できます
        - 「配送便計画」で自動的に積載計画が作成されます
        - 検査区分F/$を含む製品は自動的にハイライトされます
        """)
    
    def _log_import_history(self, filename: str, message: str):
        """インポート履歴を記録"""
        try:
            self.import_service.log_import_history(filename, message)
        except Exception as e:
            print(f"履歴記録エラー: {e}")