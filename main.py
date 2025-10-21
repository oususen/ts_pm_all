# app/main.py
import streamlit as st
from repository.database_manager import DatabaseManager
from services.production_service import ProductionService
from services.transport_service import TransportService
from services.auth_service import AuthService
from ui.layouts.sidebar import create_sidebar
from ui.pages.dashboard_page import DashboardPage
from ui.pages.csv_import_page import CSVImportPage
from ui.pages.constraints_page import ConstraintsPage
from ui.pages.product_page import ProductPage
from ui.pages.production_page import ProductionPage
from ui.pages.transport_page import TransportPage
from ui.pages.delivery_progress_page import DeliveryProgressPage
from ui.pages.login_page import LoginPage
from ui.pages.user_management_page import UserManagementPage
from config import APP_CONFIG
from ui.pages.calendar_page import CalendarPage

class ProductionPlanningApp:
    """生産計画アプリケーション - メイン制御クラス"""
    
    def __init__(self):
        # データベース接続
        self.db = DatabaseManager()

        # サービス層初期化
        self.production_service = ProductionService(self.db)
        self.transport_service = TransportService(self.db)
        self.auth_service = AuthService(self.db)

        # 認証ページ
        self.login_page = LoginPage(self.auth_service)

        # ページ初期化
        self.pages = {
            "ダッシュボード": DashboardPage(self.production_service),
            "CSV受注取込": CSVImportPage(self.db, self.auth_service),
            "製品管理": ProductPage(self.production_service, self.transport_service, self.auth_service),
            "制限設定": ConstraintsPage(self.production_service, self.auth_service),
            "生産計画": ProductionPage(self.production_service, self.transport_service, self.auth_service),
            "配送便計画": TransportPage(self.transport_service, self.auth_service),
            "納入進度": DeliveryProgressPage(self.transport_service, self.auth_service),
            "📅 会社カレンダー": CalendarPage(self.db, self.auth_service),
            "ユーザー管理": UserManagementPage(self.auth_service),
        }
    
    def run(self):
        """アプリケーション実行"""
        # ページ設定
        st.set_page_config(
            page_title=APP_CONFIG.page_title,
            page_icon=APP_CONFIG.page_icon,
            layout=APP_CONFIG.layout
        )

        # 認証チェック
        if not st.session_state.get('authenticated', False):
            # ログイン画面を表示
            self.login_page.show()
            return

        # サイドバー表示（認証サービスを渡す）
        selected_page = create_sidebar(self.auth_service)

        # ページアクセス権限チェック
        user = st.session_state.get('user')
        if not self.auth_service.can_access_page(user['id'], selected_page):
            st.error(f"⛔ 「{selected_page}」へのアクセス権限がありません")
            return

        # 選択されたページを表示
        if selected_page in self.pages:
            try:
                self.pages[selected_page].show()
            except Exception as e:
                st.error(f"ページ表示エラー: {e}")
                st.info("データベース接続を確認してください")

                # デバッグ情報
                with st.expander("エラー詳細"):
                    import traceback
                    st.code(traceback.format_exc())
        else:
            st.error("選択されたページが見つかりません")
    
    def __del__(self):
        """リソース解放"""
        if hasattr(self, 'db'):
            self.db.close()

def main():
    """メイン関数"""
    try:
        app = ProductionPlanningApp()
        app.run()
    except Exception as e:
        st.error(f"アプリケーション起動エラー: {e}")
        st.info("設定ファイルとデータベース接続を確認してください")
        
        # デバッグ情報
        with st.expander("エラー詳細"):
            import traceback
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()