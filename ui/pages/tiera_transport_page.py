# ui/pages/tiera_transport_page.py
"""
Tiera様専用の配送便計画ページ

【特徴】
- TransportPageの全機能を継承
- Tiera様専用の説明を追加
- シンプルなロジック（TieraTransportPlanner使用）
"""

import streamlit as st
from ui.pages.transport_page import TransportPage


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
