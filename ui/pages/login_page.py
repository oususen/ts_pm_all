# app/ui/pages/login_page.py
import streamlit as st
from typing import Dict, Any

class LoginPage:
    """ログイン画面"""

    def __init__(self, auth_service):
        self.auth_service = auth_service

    def show(self):
        """ログイン画面表示"""

        # センタリング用のレイアウト
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            st.markdown("---")
            st.title("🔐 ログイン")
            st.write("生産管理システムへようこそ")

            # ログインフォーム
            with st.form("login_form"):
                username = st.text_input("ユーザー名", placeholder="admin")
                password = st.text_input("パスワード", type="password", placeholder="パスワードを入力")

                submitted = st.form_submit_button("ログイン", type="primary", use_container_width=True)

                if submitted:
                    if not username or not password:
                        st.error("ユーザー名とパスワードを入力してください")
                    else:
                        # 認証処理
                        user = self.auth_service.authenticate(username, password)

                        if user:
                            # セッション状態に保存
                            st.session_state['authenticated'] = True
                            st.session_state['user'] = user
                            st.session_state['user_roles'] = self.auth_service.get_user_roles(user['id'])

                            st.success(f"ようこそ、{user['full_name']}さん！")
                            st.rerun()
                        else:
                            st.error("ユーザー名またはパスワードが正しくありません")

            st.markdown("---")
            st.info("""
            **デフォルトログイン情報:**
            - ユーザー名: `atumi`
            - パスワード: '初期パスワード　123456'

            ※初回ログイン後、パスワードを変更してください
            """)

    @staticmethod
    def is_authenticated() -> bool:
        """認証状態チェック"""
        return st.session_state.get('authenticated', False)

    @staticmethod
    def get_current_user() -> Dict[str, Any]:
        """現在のユーザー情報取得"""
        return st.session_state.get('user', None)

    @staticmethod
    def logout():
        """ログアウト"""
        st.session_state['authenticated'] = False
        st.session_state['user'] = None
        st.session_state['user_roles'] = []
        st.rerun()
