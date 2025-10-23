# ui/pages/tiera_transport_page.py
"""
Tiera様専用の配送便計画ページ

【特徴】
- TransportPageの全機能を継承
- Tiera様専用の説明を追加
- シンプルなロジック（TieraTransportPlanner使用）
- 生産課形式のPDF出力（横=日付、縦=製品コード、朝便/夕便分離）
"""

import streamlit as st
from ui.pages.transport_page import TransportPage
from typing import Dict
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from collections import defaultdict


class TieraTransportPage(TransportPage):
    """Tiera様専用配送便計画ページ"""

    def __init__(self, transport_service, auth_service=None):
        # 親クラスの初期化（全機能を継承）
        super().__init__(transport_service, auth_service)

    def show(self):
        """ページ表示（Tiera様専用の説明を追加）"""
        st.title("🚛 配送便計画（Tiera様専用）")

        # ✅ Tiera様の特徴を説明
        with st.expander("📋 Tiera様の積載計画の特徴", expanded=False):
            st.info("""
            **✨ Tiera様専用の積載ルール:**

            🔹 **リードタイム**: 製品ごとに設定（通常2日）
            - 納品日の2日前に積載（例: 10/25納品 → 10/23積載）
            - 製品マスタの`lead_time_days`列で管理

            🔹 **トラック優先順位**: 夕便優先
            - `arrival_day_offset=1`（翌日着）のトラックを優先使用
            - 朝便は夕便で積めない場合のみ使用

            🔹 **シンプルなロジック**:
            - ✅ 前倒し無し（リードタイム厳守）
            - ✅ 特便無し
            - ✅ 積めるだけ積む方式

            ---

            **⚙️ 設定確認:**
            - 製品マスタ: `lead_time_days = 2`
            - トラックマスタ: 夕便は`arrival_day_offset = 1`
            """)

        # 権限チェック
        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("⚠️ この画面の編集権限がありません。閲覧のみ可能です。")

        # ✅ 親クラスのタブ表示をそのまま使用
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 積載計画作成",
            "📊 計画一覧",
            "🔍 検査対象製品",
            "📦 容器管理",
            "🚛 トラック管理"
        ])

        with tab1:
            # Tiera様専用の説明を追加してから親クラスのメソッド呼び出し
            self._show_tiera_loading_planning(can_edit)

        with tab2:
            # 親クラスのメソッドをそのまま使用
            self._show_plan_view()

        with tab3:
            # 親クラスのメソッドをそのまま使用
            self._show_inspection_products()

        with tab4:
            # 親クラスのメソッドをそのまま使用
            self._show_container_management()

        with tab5:
            # 親クラスのメソッドをそのまま使用
            self._show_truck_management()

    def _show_tiera_loading_planning(self, can_edit):
        """Tiera様用の積載計画作成（親クラスの機能を使用）"""

        # Tiera様専用のヒント表示
        st.info("""
        💡 **Tiera様の計画作成のポイント:**
        - リードタイムは各製品の設定値を使用（通常2日）
        - 夕便（arrival_day_offset=1）が優先的に選ばれます
        - 前倒しや特便は実施されません
        """)

        # 親クラスの積載計画作成メソッドを呼び出し
        self._show_loading_planning()

    def _export_plan_to_pdf(self, plan_data: Dict):
        """積載計画をPDFとしてエクスポート（Tiera様専用：生産課形式）

        横軸：日付
        縦軸：製品コード（朝便/夕便で分類）
        """
        try:
            # PDFバッファを作成
            buffer = io.BytesIO()

            # 横向きA4でドキュメント作成
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                   topMargin=8*mm, bottomMargin=8*mm,
                                   leftMargin=8*mm, rightMargin=8*mm)
            elements = []
            styles = getSampleStyleSheet()

            # ✅ 日本語フォントの設定
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.fonts import addMapping

            # 日本語フォントの登録
            try:
                pdfmetrics.registerFont(TTFont('Japanese', 'C:/Windows/Fonts/msgothic.ttc'))
                pdfmetrics.registerFont(TTFont('Japanese-Bold', 'C:/Windows/Fonts/msgothic.ttc'))
            except:
                try:
                    pdfmetrics.registerFont(TTFont('Japanese', '/System/Library/Fonts/Arial Unicode.ttf'))
                    pdfmetrics.registerFont(TTFont('Japanese-Bold', '/System/Library/Fonts/Arial Unicode.ttf'))
                except:
                    st.warning("日本語フォントが見つかりません")

            # フォントマッピング
            addMapping('Japanese', 0, 0, 'Japanese')
            addMapping('Japanese', 1, 0, 'Japanese-Bold')

            # タイトルスタイル
            japanese_title_style = styles['Heading1'].clone('JapaneseTitleStyle')
            japanese_title_style.fontName = 'Japanese-Bold'
            japanese_title_style.fontSize = 12
            japanese_title_style.alignment = 1  # 中央揃え

            # データ整理
            daily_plans = plan_data.get('daily_plans', {})
            if not daily_plans:
                title = Paragraph("積載計画データがありません", japanese_title_style)
                elements.append(title)
                doc.build(elements)
                buffer.seek(0)
                return buffer

            # 日付リストを取得（営業日のみ）
            working_dates = sorted(daily_plans.keys())

            # 期間を取得
            period_str = plan_data.get('period', '')
            if period_str and ' ~ ' in period_str:
                start_date_str, end_date_str = period_str.split(' ~ ')
            else:
                start_date_str = working_dates[0] if working_dates else ''
                end_date_str = working_dates[-1] if working_dates else ''

            # 土日を含む全日付リストを生成
            from datetime import timedelta
            try:
                start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                all_dates = []
                current_date = start_date_obj
                while current_date <= end_date_obj:
                    all_dates.append(current_date.strftime('%Y-%m-%d'))
                    current_date += timedelta(days=1)
            except:
                # フォールバック：営業日のみ
                all_dates = working_dates

            # トラック情報を取得
            trucks_info = self._get_trucks_info()

            # 製品×日付×便種別のマトリクスを作成
            morning_data, evening_data, all_products = self._build_production_matrix(
                daily_plans, all_dates, trucks_info
            )

            # 2週間（14日）ごとに分割してPDF作成
            max_dates_per_page = 14
            date_chunks = [all_dates[i:i + max_dates_per_page] for i in range(0, len(all_dates), max_dates_per_page)]

            for chunk_idx, dates_chunk in enumerate(date_chunks):
                # ページごとのタイトル
                chunk_start = dates_chunk[0]
                chunk_end = dates_chunk[-1]
                title_text = f"北進様向けフロア納入日程 {chunk_start} ～ {chunk_end}"

                if len(date_chunks) > 1:
                    title_text += f" (ページ {chunk_idx + 1}/{len(date_chunks)})"

                title = Paragraph(title_text, japanese_title_style)
                elements.append(title)
                elements.append(Spacer(1, 3))

                # PDF用テーブルデータを作成
                table_data, row_info = self._create_production_table_data(
                    dates_chunk, all_products, morning_data, evening_data
                )

                # テーブル作成（列幅を動的に計算）
                # A4横向きの有効幅 ≈ 280mm
                available_width = 280 * mm
                product_col_width = 50 * mm  # 製品コード列
                date_cols_width = available_width - product_col_width
                date_col_width = date_cols_width / len(dates_chunk)

                col_widths = [product_col_width] + [date_col_width] * len(dates_chunk)

                production_table = Table(table_data, colWidths=col_widths, repeatRows=1)

                # テーブルスタイル（土日祝日の色分け含む）
                table_style = self._create_production_table_style_with_weekends(
                    dates_chunk, len(table_data), row_info
                )
                production_table.setStyle(table_style)

                elements.append(production_table)

                # 次のページがある場合は改ページ
                if chunk_idx < len(date_chunks) - 1:
                    from reportlab.platypus import PageBreak
                    elements.append(PageBreak())

            # PDF生成
            doc.build(elements)
            buffer.seek(0)

            return buffer

        except Exception as e:
            st.error(f"PDF生成エラー: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

    def _get_trucks_info(self):
        """トラック情報を取得"""
        try:
            trucks_df = self.service.get_trucks()
            trucks_info = {}
            for _, row in trucks_df.iterrows():
                truck_id = row['id']
                trucks_info[truck_id] = {
                    'arrival_day_offset': int(row.get('arrival_day_offset', 0) or 0),
                    'name': row.get('name', '')
                }
            return trucks_info
        except:
            return {}

    def _build_production_matrix(self, daily_plans, dates, trucks_info):
        """製品×日付×便種別のマトリクスを構築"""
        morning_data = defaultdict(lambda: defaultdict(int))  # {product_code: {date: quantity}}
        evening_data = defaultdict(lambda: defaultdict(int))
        all_products = set()

        for date_str in dates:
            day_plan = daily_plans.get(date_str, {})

            for truck in day_plan.get('trucks', []):
                truck_id = truck.get('truck_id')
                truck_info = trucks_info.get(truck_id, {})
                arrival_offset = truck_info.get('arrival_day_offset', 0)

                # 朝便（arrival_day_offset=0）か夕便（arrival_day_offset=1）か判定
                is_evening = (arrival_offset == 1)

                for item in truck.get('loaded_items', []):
                    product_code = item.get('product_code', '')
                    quantity = item.get('total_quantity', 0)

                    all_products.add(product_code)

                    if is_evening:
                        evening_data[product_code][date_str] += quantity
                    else:
                        morning_data[product_code][date_str] += quantity

        # 製品コードをソート
        sorted_products = sorted(all_products)

        return morning_data, evening_data, sorted_products

    def _create_production_table_data(self, dates, products, morning_data, evening_data):
        """生産課形式のテーブルデータを作成"""
        table_data = []
        row_info = {}

        # ヘッダー行1: 日付（曜日付き）
        header_row = ['']
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                weekday = ['月', '火', '水', '木', '金', '土', '日'][date_obj.weekday()]
                date_display = f"{date_obj.month}/{date_obj.day}\n{weekday}"
            except:
                date_display = date_str
            header_row.append(date_display)
        table_data.append(header_row)

        # 朝便セクション
        row_info['morning_header_row'] = len(table_data)
        table_data.append(['午前便 AM 11:30頃'] + [''] * len(dates))

        for idx, product_code in enumerate(products, 1):
            row = [f'[{idx}]{product_code}']
            for date_str in dates:
                quantity = morning_data[product_code].get(date_str, 0)
                row.append(str(quantity) if quantity > 0 else '')
            table_data.append(row)

        # 朝便合計行
        row_info['morning_total_row'] = len(table_data)
        morning_total_row = ['午前便①合計']
        for date_str in dates:
            total = sum(morning_data[prod].get(date_str, 0) for prod in products)
            morning_total_row.append(str(total) if total > 0 else '')
        table_data.append(morning_total_row)

        # 夕便セクション
        row_info['evening_header_row'] = len(table_data)
        table_data.append(['午後便 PM 18:30頃'] + [''] * len(dates))

        for idx, product_code in enumerate(products, 1):
            row = [f'[{idx}]{product_code}']
            for date_str in dates:
                quantity = evening_data[product_code].get(date_str, 0)
                row.append(str(quantity) if quantity > 0 else '')
            table_data.append(row)

        # 夕便合計行
        row_info['evening_total_row'] = len(table_data)
        evening_total_row = ['午後便合計']
        for date_str in dates:
            total = sum(evening_data[prod].get(date_str, 0) for prod in products)
            evening_total_row.append(str(total) if total > 0 else '')
        table_data.append(evening_total_row)

        # 出荷数合計行
        row_info['grand_total_row'] = len(table_data)
        grand_total_row = ['出荷数合計']
        for date_str in dates:
            morning_total = sum(morning_data[prod].get(date_str, 0) for prod in products)
            evening_total = sum(evening_data[prod].get(date_str, 0) for prod in products)
            total = morning_total + evening_total
            grand_total_row.append(str(total) if total > 0 else '')
        table_data.append(grand_total_row)

        return table_data, row_info

    def _create_production_table_style(self, num_dates, num_rows, row_info):
        """生産課形式のテーブルスタイルを作成"""
        style = TableStyle([
            # 基本設定
            ('FONTNAME', (0, 0), (-1, -1), 'Japanese'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

            # ヘッダー行（日付）
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, 0), 6),

            # 製品コード列
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTSIZE', (0, 2), (0, -1), 6),

            # 数値列
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ])

        # 午前便ヘッダー
        morning_header = row_info.get('morning_header_row', 1)
        style.add('BACKGROUND', (0, morning_header), (-1, morning_header), colors.white)
        style.add('FONTNAME', (0, morning_header), (0, morning_header), 'Japanese-Bold')
        style.add('ALIGN', (0, morning_header), (0, morning_header), 'LEFT')

        # 午前便合計行
        morning_total = row_info.get('morning_total_row', num_rows-3)
        style.add('BACKGROUND', (0, morning_total), (-1, morning_total), colors.lightyellow)
        style.add('FONTNAME', (0, morning_total), (0, morning_total), 'Japanese-Bold')

        # 午後便ヘッダー
        evening_header = row_info.get('evening_header_row', num_rows-2)
        style.add('BACKGROUND', (0, evening_header), (-1, evening_header), colors.white)
        style.add('FONTNAME', (0, evening_header), (0, evening_header), 'Japanese-Bold')
        style.add('ALIGN', (0, evening_header), (0, evening_header), 'LEFT')

        # 午後便合計行
        evening_total = row_info.get('evening_total_row', num_rows-2)
        style.add('BACKGROUND', (0, evening_total), (-1, evening_total), colors.lightyellow)
        style.add('FONTNAME', (0, evening_total), (0, evening_total), 'Japanese-Bold')

        # 出荷数合計行
        grand_total = row_info.get('grand_total_row', num_rows-1)
        style.add('BACKGROUND', (0, grand_total), (-1, grand_total), colors.orange)
        style.add('FONTNAME', (0, grand_total), (0, grand_total), 'Japanese-Bold')

        return style

    def _create_production_table_style_with_weekends(self, dates, num_rows, row_info):
        """生産課形式のテーブルスタイルを作成（土日祝日の色分け含む）"""
        style = TableStyle([
            # 基本設定
            ('FONTNAME', (0, 0), (-1, -1), 'Japanese'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),  # 9ptに変更
            ('LEADING', (0, 0), (-1, -1), 10),  # 行間を10ポイントに
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 2),  # 上パディング2ポイント
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # 下パディング2ポイント

            # ヘッダー行（日付）
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, 0), 8),

            # 製品コード列
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTSIZE', (0, 1), (0, -1), 8),

            # 数値列
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ])

        # 午前便ヘッダー行
        morning_header = row_info.get('morning_header_row', 1)

        # 午前便合計行
        morning_total = row_info.get('morning_total_row', num_rows-3)

        # 午後便ヘッダー行
        evening_header = row_info.get('evening_header_row', num_rows-2)

        # 午後便合計行
        evening_total = row_info.get('evening_total_row', num_rows-2)

        # 出荷数合計行
        grand_total = row_info.get('grand_total_row', num_rows-1)

        # 製品行（朝便）の奇数/偶数で色分け（全列に適用）
        morning_start_row = morning_header + 1
        morning_end_row = morning_total - 1

        product_row_counter = 0
        for row_idx in range(morning_start_row, morning_end_row + 1):
            product_row_counter += 1
            if product_row_counter % 2 == 1:  # 奇数行
                style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(0.95, 0.95, 0.95))
            else:  # 偶数行
                style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.white)

        # 製品行（夕便）の奇数/偶数で色分け（朝便からの連番、全列に適用）
        evening_start_row = evening_header + 1
        evening_end_row = evening_total - 1

        for row_idx in range(evening_start_row, evening_end_row + 1):
            product_row_counter += 1
            if product_row_counter % 2 == 1:  # 奇数行
                style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(0.95, 0.95, 0.95))
            else:  # 偶数行
                style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.white)

        # 土日祝日の列を色分け（データ行のみ、ヘッダーと合計行は除く）
        from reportlab.lib import colors as reportlab_colors

        for col_idx, date_str in enumerate(dates, 1):  # 1から開始（0列目は製品コード）
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                weekday = date_obj.weekday()

                # カレンダーリポジトリで営業日チェック
                is_holiday = False
                if hasattr(self, 'service') and hasattr(self.service, 'calendar_repo'):
                    calendar_repo = self.service.calendar_repo
                    if calendar_repo:
                        try:
                            is_holiday = not calendar_repo.is_working_day(date_obj.date())
                        except:
                            pass

                # 色を決定
                bg_color = None
                if weekday == 5:  # 土曜日
                    bg_color = reportlab_colors.Color(0.68, 0.85, 0.90)  # lightblue
                elif weekday == 6:  # 日曜日
                    bg_color = reportlab_colors.Color(1.0, 0.71, 0.76)  # lightpink
                elif is_holiday:  # 平日の祝日
                    bg_color = reportlab_colors.Color(1.0, 1.0, 0.88)  # lightyellow

                # 色を適用（データ行のみ）
                if bg_color:
                    # ヘッダー行も色付け
                    style.add('BACKGROUND', (col_idx, 0), (col_idx, 0), bg_color)
                    # 朝便データ行
                    for row_idx in range(morning_header, morning_total + 1):
                        if row_idx != morning_header:  # ヘッダー行以外
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color)
                    # 夕便データ行
                    for row_idx in range(evening_header, evening_total + 1):
                        if row_idx != evening_header:  # ヘッダー行以外
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color)
                    # 合計行
                    style.add('BACKGROUND', (col_idx, grand_total), (col_idx, grand_total), bg_color)
            except Exception as e:
                pass

        # 特殊行のスタイル
        # 午前便ヘッダー
        style.add('FONTNAME', (0, morning_header), (0, morning_header), 'Japanese-Bold')
        style.add('ALIGN', (0, morning_header), (0, morning_header), 'LEFT')
        style.add('BACKGROUND', (0, morning_header), (0, morning_header), colors.white)

        # 午前便合計行
        style.add('FONTNAME', (0, morning_total), (-1, morning_total), 'Japanese-Bold')
        style.add('BACKGROUND', (0, morning_total), (0, morning_total), colors.lightyellow)

        # 午後便ヘッダー
        style.add('FONTNAME', (0, evening_header), (0, evening_header), 'Japanese-Bold')
        style.add('ALIGN', (0, evening_header), (0, evening_header), 'LEFT')
        style.add('BACKGROUND', (0, evening_header), (0, evening_header), colors.white)

        # 午後便合計行
        style.add('FONTNAME', (0, evening_total), (-1, evening_total), 'Japanese-Bold')
        style.add('BACKGROUND', (0, evening_total), (0, evening_total), colors.lightyellow)

        # 出荷数合計行
        style.add('BACKGROUND', (0, grand_total), (0, grand_total), colors.orange)
        style.add('FONTNAME', (0, grand_total), (-1, grand_total), 'Japanese-Bold')

        return style
