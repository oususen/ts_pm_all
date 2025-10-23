# app/ui/layouts/sidebar.py
import streamlit as st
from typing import List

def create_sidebar(auth_service=None) -> str:
    """サイドバー作成"""
    with st.sidebar:
        st.title("🏭 生産計画管理")
        st.markdown("---")

        # ユーザー情報表示
        if st.session_state.get('authenticated'):
            user = st.session_state.get('user')
            st.write(f"👤 **{user['full_name']}**")

            user_roles = st.session_state.get('user_roles', [])
            if user_roles:
                st.caption(f"ロール: {', '.join(user_roles)}")

            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state['authenticated'] = False
                st.session_state['user'] = None
                st.session_state['user_roles'] = []
                st.rerun()

            st.markdown("---")

            # 顧客選択UI
            st.subheader("🏢 顧客選択")

            customer_options = {
                "クボタ": "kubota",
                "ティエラ": "tiera"
            }

            # session_stateから現在の顧客を取得
            current_customer = st.session_state.get('current_customer', 'kubota')
            current_display = "クボタ" if current_customer == "kubota" else "ティエラ"

            selected_display = st.selectbox(
                "顧客を選択",
                list(customer_options.keys()),
                index=list(customer_options.keys()).index(current_display),
                key="customer_selector"
            )

            # 顧客が変更されたら更新
            new_customer = customer_options[selected_display]
            if new_customer != st.session_state.get('current_customer'):
                st.session_state['current_customer'] = new_customer
                st.info(f"✅ {selected_display}様に切り替えました")
                st.rerun()

            # 現在の顧客を表示
            st.success(f"現在: **{selected_display}様**")

            st.markdown("---")

        # アクセス可能なページを取得
        available_pages = _get_available_pages(auth_service)

        # ページ選択
        page = st.radio(
            "メニュー",
            available_pages,
            index=0
        )

        st.markdown("---")

        # 情報表示
        st.subheader("システム情報")
        st.write("**バージョン:** 2.0.0")
        st.write("**環境:** 生産環境")

        # ヘルプ
        with st.expander("ヘルプ"):
            st.write("""
            **各ページの説明:**

            - **ダッシュボード**: 全体の概要とトレンド
            - **CSV受注取込**: 受注CSVファイルのインポート
            - **製品管理**: 製品の登録・編集・削除
            - **製品群管理**: 製品群の分類設定とグループ編集
            - **制限設定**: 生産能力と運送制限
            - **生産計画**: 日次生産計画の作成
            - **配送便計画**: トラック積載計画
            - **納入進度**: 受注から出荷までの進捗管理
            - **ユーザー管理**: ユーザーとロールの管理（管理者のみ）
            """)

        return page

def _get_available_pages(auth_service) -> List[str]:
    """ユーザーがアクセス可能なページ一覧を取得"""
    # 認証されていない場合は空リスト
    if not st.session_state.get('authenticated'):
        return []

    # 認証サービスがない場合は全ページ表示
    if not auth_service:
        return [
            "ダッシュボード",
            "CSV受注取込",
            "製品管理",
            "製品群管理",
            "制限設定",
            "生産計画",
            "配送便計画",
            "納入進度",
            "📅 会社カレンダー"
        ]

    # ユーザーの権限に基づいてページをフィルタリング
    user = st.session_state.get('user')
    user_pages = auth_service.get_user_pages(user['id'])

    available_pages = [p['page_name'] for p in user_pages if p['can_view']]

    return available_pages
