# app/ui/pages/user_management_page.py
import streamlit as st
import pandas as pd
from datetime import datetime
import logging

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('user_management.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UserManagementPage:
    """ユーザー管理画面"""

    def __init__(self, auth_service):
        self.auth_service = auth_service

    def show(self):
        """ページ表示"""
        st.title("👥 ユーザー管理")
        st.write("ユーザーとロールを管理します")

        # 管理者のみアクセス可能
        current_user = st.session_state.get('user')
        if not current_user or not current_user.get('is_admin'):
            st.error("⛔ この画面は管理者のみアクセス可能です")
            return

        tab1, tab2, tab3, tab4 = st.tabs(["👤 ユーザー一覧", "➕ 新規登録", "🎭 ロール管理", "🔐 権限設定"])

        with tab1:
            self._show_user_list()

        with tab2:
            self._show_user_creation()

        with tab3:
            self._show_role_management()

        with tab4:
            self._show_permission_management()

    def _show_user_list(self):
        """ユーザー一覧表示"""
        st.subheader("👤 ユーザー一覧")

        try:
            users_df = self.auth_service.get_all_users()

            if users_df.empty:
                st.info("ユーザーが登録されていません")
                return

            # 表示用に整形
            users_df['is_active'] = users_df['is_active'].map({1: '有効', 0: '無効'})
            users_df['is_admin'] = users_df['is_admin'].map({1: '管理者', 0: '一般'})

            # 日時を見やすく整形
            if 'last_login' in users_df.columns:
                users_df['last_login'] = pd.to_datetime(users_df['last_login']).dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                users_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": "ID",
                    "username": "ユーザー名",
                    "full_name": "氏名",
                    "email": "メールアドレス",
                    "is_active": "状態",
                    "is_admin": "種別",
                    "created_at": "作成日時",
                    "last_login": "最終ログイン"
                }
            )

            # ユーザー編集セクション
            st.markdown("---")
            st.subheader("📝 ユーザー編集")

            if not users_df.empty:
                user_options = {
                    f"{row['username']} ({row['full_name']})": row['id']
                    for _, row in users_df.iterrows()
                }

                selected_user = st.selectbox("編集するユーザーを選択", options=list(user_options.keys()))

                if selected_user:
                    user_id = user_options[selected_user]
                    user_data = users_df[users_df['id'] == user_id].iloc[0]

                    with st.form(f"edit_user_{user_id}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            new_full_name = st.text_input("氏名", value=user_data['full_name'])
                            new_email = st.text_input("メールアドレス", value=user_data['email'] or '')
                            new_password = st.text_input("新しいパスワード（変更する場合のみ）", type="password")

                        with col2:
                            new_is_active = st.selectbox("状態", options=['有効', '無効'],
                                                        index=0 if user_data['is_active'] == '有効' else 1)
                            new_is_admin = st.selectbox("種別", options=['一般', '管理者'],
                                                       index=1 if user_data['is_admin'] == '管理者' else 0)

                        col_update, col_delete = st.columns(2)

                        with col_update:
                            update_clicked = st.form_submit_button("💾 更新", type="primary", use_container_width=True)

                            if update_clicked:
                                update_data = {
                                    'full_name': new_full_name,
                                    'email': new_email if new_email else None,
                                    'is_active': 1 if new_is_active == '有効' else 0,
                                    'is_admin': 1 if new_is_admin == '管理者' else 0
                                }

                                if new_password:
                                    update_data['password'] = new_password

                                try:
                                    self.auth_service.update_user(user_id, update_data)
                                    st.success("✅ ユーザー情報を更新しました")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ 更新エラー: {e}")

                        with col_delete:
                            delete_clicked = st.form_submit_button("🗑️ 削除", type="secondary", use_container_width=True)

                            if delete_clicked:
                                # 自分自身は削除できない
                                current_user = st.session_state.get('user')
                                if current_user['id'] == user_id:
                                    st.error("自分自身のアカウントは削除できません")
                                else:
                                    try:
                                        self.auth_service.delete_user(user_id)
                                        st.success("✅ ユーザーを削除しました")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ 削除エラー: {e}")

        except Exception as e:
            st.error(f"ユーザー一覧取得エラー: {e}")

    def _show_user_creation(self):
        """ユーザー新規登録"""
        st.subheader("➕ 新規ユーザー登録")

        with st.form("create_user_form"):
            col1, col2 = st.columns(2)

            with col1:
                username = st.text_input("ユーザー名 *", placeholder="例: yamada")
                full_name = st.text_input("氏名 *", placeholder="例: 山田太郎")
                password = st.text_input("パスワード *", type="password")

            with col2:
                email = st.text_input("メールアドレス", placeholder="例: yamada@example.com")
                is_admin = st.checkbox("管理者権限を付与")

            submitted = st.form_submit_button("✅ 登録", type="primary", use_container_width=True)

            if submitted:
                if not username or not full_name or not password:
                    st.error("必須項目を入力してください")
                elif len(password) < 6:
                    st.error("パスワードは6文字以上にしてください")
                else:
                    try:
                        user_id = self.auth_service.create_user(
                            username=username,
                            password=password,
                            full_name=full_name,
                            email=email if email else None,
                            is_admin=is_admin
                        )

                        st.success(f"✅ ユーザー「{full_name}」を登録しました（ID: {user_id}）")
                        st.balloons()

                    except Exception as e:
                        if 'UNIQUE constraint failed' in str(e):
                            st.error("❌ このユーザー名は既に使用されています")
                        else:
                            st.error(f"❌ 登録エラー: {e}")

    def _show_role_management(self):
        """ロール管理"""
        st.subheader("🎭 ロール管理")

        try:
            roles_df = self.auth_service.get_all_roles()

            if roles_df.empty:
                st.info("ロールが登録されていません")
                return

            st.write("**登録済みロール一覧**")
            st.dataframe(
                roles_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": "ID",
                    "role_name": "ロール名",
                    "description": "説明"
                }
            )

            st.markdown("---")
            st.subheader("👤 ユーザーにロールを割り当て")

            # ユーザー一覧取得
            users_df = self.auth_service.get_all_users()

            if users_df.empty:
                st.info("ユーザーが登録されていません")
                return

            col1, col2 = st.columns(2)

            with col1:
                user_options = {
                    f"{row['username']} ({row['full_name']})": row['id']
                    for _, row in users_df.iterrows()
                }
                selected_user = st.selectbox("ユーザー", options=list(user_options.keys()))

            with col2:
                role_options = {row['role_name']: row['id'] for _, row in roles_df.iterrows()}
                selected_role = st.selectbox("ロール", options=list(role_options.keys()))

            col_assign, col_remove = st.columns(2)

            with col_assign:
                if st.button("➕ ロール割り当て", type="primary", use_container_width=True):
                    user_id = user_options[selected_user]
                    role_id = role_options[selected_role]

                    try:
                        self.auth_service.assign_role(user_id, role_id)
                        st.success(f"✅ {selected_user} に {selected_role} を割り当てました")
                    except Exception as e:
                        st.error(f"❌ 割り当てエラー: {e}")

            with col_remove:
                if st.button("➖ ロール削除", type="secondary", use_container_width=True):
                    user_id = user_options[selected_user]
                    role_id = role_options[selected_role]

                    try:
                        self.auth_service.remove_role(user_id, role_id)
                        st.success(f"✅ {selected_user} から {selected_role} を削除しました")
                    except Exception as e:
                        st.error(f"❌ 削除エラー: {e}")

            # 現在のロール割り当て状況を表示
            if selected_user:
                user_id = user_options[selected_user]
                user_roles = self.auth_service.get_user_roles(user_id)

                st.markdown("---")
                st.write(f"**{selected_user} の現在のロール:**")
                if user_roles:
                    for role in user_roles:
                        st.write(f"- {role}")
                else:
                    st.info("ロールが割り当てられていません")

        except Exception as e:
            st.error(f"ロール管理エラー: {e}")

    def _show_permission_management(self):
        """権限設定管理"""
        st.subheader("🔐 権限設定")
        st.write("ロールごとにページとタブのアクセス権限を設定します")

        try:
            # ロール一覧取得
            roles_df = self.auth_service.get_all_roles()

            if roles_df.empty:
                st.info("ロールが登録されていません")
                return

            # ロール選択
            role_options = {row['role_name']: row['id'] for _, row in roles_df.iterrows()}
            selected_role_name = st.selectbox("設定するロール", options=list(role_options.keys()))
            selected_role_id = role_options[selected_role_name]

            st.markdown("---")

            # ページ権限設定
            st.subheader("📄 ページ権限")
            st.write("各ページへのアクセス権限を設定します")

            # 利用可能なページ一覧
            available_pages = [
                "ダッシュボード",
                "CSV受注取込",
                "製品管理",
                "製品群管理",
                "制限設定",
                "生産計画",
                "配送便計画",
                "納入進度",
                "📅 会社カレンダー",
                "ユーザー管理"
            ]

            # 現在の権限を取得
            current_page_perms = self.auth_service.get_page_permissions(selected_role_id)
            perm_dict = {
                row['page_name']: {'can_view': bool(row['can_view']), 'can_edit': bool(row['can_edit'])}
                for _, row in current_page_perms.iterrows()
            } if not current_page_perms.empty else {}

            # ページ権限設定フォーム
            with st.form(f"page_permissions_{selected_role_id}"):
                st.write("**ページ権限設定:**")

                page_settings = {}
                for page in available_pages:
                    col1, col2, col3 = st.columns([3, 1, 1])

                    with col1:
                        st.write(f"**{page}**")

                    with col2:
                        current_view = perm_dict.get(page, {}).get('can_view', False)
                        can_view = st.checkbox("閲覧", value=current_view, key=f"view_{selected_role_id}_{page}")

                    with col3:
                        current_edit = perm_dict.get(page, {}).get('can_edit', False)
                        can_edit = st.checkbox("編集", value=current_edit, key=f"edit_{selected_role_id}_{page}")

                    page_settings[page] = {'can_view': can_view, 'can_edit': can_edit}

                if st.form_submit_button("💾 ページ権限を保存", type="primary", use_container_width=True):
                    try:
                        logger.info(f"=== ページ権限保存開始 ===")
                        logger.info(f"ロール: {selected_role_name} (ID: {selected_role_id})")

                        # デバッグ：保存しようとしている内容をログに出力
                        save_count = 0
                        for page, perms in page_settings.items():
                            logger.info(f"設定内容: {page} - 閲覧={perms['can_view']}, 編集={perms['can_edit']}")
                            if perms['can_view'] or perms['can_edit']:
                                save_count += 1

                        if save_count == 0:
                            logger.warning("チェックが入っているページがありません")
                            st.warning("⚠️ チェックが入っているページがありません")

                        logger.info(f"合計: {save_count}件のページ権限を設定します")

                        # 既存の権限をすべて削除
                        logger.info("既存の権限を削除中...")
                        for page in available_pages:
                            self.auth_service.delete_page_permission(selected_role_id, page)
                            logger.debug(f"削除: {page}")

                        # 新しい権限を設定
                        logger.info("新しい権限を設定中...")
                        success_count = 0
                        for page, perms in page_settings.items():
                            if perms['can_view'] or perms['can_edit']:
                                logger.info(f"保存開始: role_id={selected_role_id}, page={page}, can_view={perms['can_view']}, can_edit={perms['can_edit']}")
                                self.auth_service.set_page_permission(
                                    selected_role_id,
                                    page,
                                    perms['can_view'],
                                    perms['can_edit']
                                )
                                success_count += 1
                                logger.info(f"✓ {page} を設定しました")

                        logger.info(f"=== ページ権限保存完了: {success_count}件 ===")
                        st.success(f"✅ {selected_role_name} のページ権限を保存しました（{success_count}件）")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        logger.error(f"保存エラー: {e}")
                        logger.error(f"詳細: {error_detail}")
                        st.error(f"❌ 保存エラー: {e}")
                        st.error(f"詳細: {error_detail}")

            st.markdown("---")

            # タブ権限設定
            st.subheader("📑 タブ権限")
            st.write("ロール → ページを選択して、タブごとの閲覧・編集権限を設定します")

            # ページとタブの定義
            page_tabs = {
                "生産計画": [
                    "📊 計画シミュレーション",
                    "📝 生産計画管理",
                    "🔧 製造工程（加工対象）"
                ],
                "配送便計画": [
                    "🚛 積載計画",
                    "📦 出荷管理"
                ]
            }

            # ページ選択
            selected_page = st.selectbox(
                "タブ権限を設定するページ",
                options=list(page_tabs.keys()),
                key=f"tab_page_select_{selected_role_id}"
            )

            if selected_page and selected_page in page_tabs:
                tabs_in_page = page_tabs[selected_page]

                # 現在のタブ権限を取得
                current_tab_perms = self.auth_service.get_tab_permissions(selected_role_id, selected_page)
                tab_perm_dict = {
                    row['tab_name']: {'can_view': bool(row['can_view']), 'can_edit': bool(row['can_edit'])}
                    for _, row in current_tab_perms.iterrows()
                } if not current_tab_perms.empty else {}

                # タブ権限設定フォーム
                with st.form(f"tab_permissions_{selected_role_id}_{selected_page}"):
                    st.write(f"**{selected_page} のタブ権限設定:**")

                    tab_settings = {}
                    for tab in tabs_in_page:
                        col1, col2, col3 = st.columns([3, 1, 1])

                        with col1:
                            st.write(f"**{tab}**")

                        with col2:
                            current_view = tab_perm_dict.get(tab, {}).get('can_view', False)
                            can_view = st.checkbox("閲覧", value=current_view, key=f"tab_view_{selected_role_id}_{selected_page}_{tab}")

                        with col3:
                            current_edit = tab_perm_dict.get(tab, {}).get('can_edit', False)
                            can_edit = st.checkbox("編集", value=current_edit, key=f"tab_edit_{selected_role_id}_{selected_page}_{tab}")

                        tab_settings[tab] = {'can_view': can_view, 'can_edit': can_edit}

                    if st.form_submit_button("💾 タブ権限を保存", type="primary", use_container_width=True):
                        try:
                            logger.info(f"=== タブ権限保存開始 ===")
                            logger.info(f"ロール: {selected_role_name} (ID: {selected_role_id}), ページ: {selected_page}")

                            # デバッグ：保存しようとしている内容をログに出力
                            save_count = 0
                            for tab, perms in tab_settings.items():
                                logger.info(f"設定内容: {selected_page} / {tab} - 閲覧={perms['can_view']}, 編集={perms['can_edit']}")
                                if perms['can_view'] or perms['can_edit']:
                                    save_count += 1

                            if save_count == 0:
                                logger.warning("チェックが入っているタブがありません")
                                st.warning("⚠️ チェックが入っているタブがありません")

                            logger.info(f"合計: {save_count}件のタブ権限を設定します")

                            # 既存のタブ権限を削除
                            logger.info(f"{selected_page}の既存タブ権限を削除中...")
                            for tab in tabs_in_page:
                                self.auth_service.delete_tab_permission(selected_role_id, selected_page, tab)
                                logger.debug(f"削除: {selected_page} / {tab}")

                            # 新しいタブ権限を設定
                            logger.info("新しいタブ権限を設定中...")
                            success_count = 0
                            for tab, perms in tab_settings.items():
                                if perms['can_view'] or perms['can_edit']:
                                    logger.info(f"保存開始: role_id={selected_role_id}, page={selected_page}, tab={tab}, can_view={perms['can_view']}, can_edit={perms['can_edit']}")
                                    self.auth_service.set_tab_permission(
                                        selected_role_id,
                                        selected_page,
                                        tab,
                                        perms['can_view'],
                                        perms['can_edit']
                                    )
                                    success_count += 1
                                    logger.info(f"✓ {selected_page} / {tab} を設定しました")

                            logger.info(f"=== タブ権限保存完了: {success_count}件 ===")
                            st.success(f"✅ {selected_role_name} の {selected_page} タブ権限を保存しました（{success_count}件）")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            import traceback
                            error_detail = traceback.format_exc()
                            logger.error(f"保存エラー: {e}")
                            logger.error(f"詳細: {error_detail}")
                            st.error(f"❌ 保存エラー: {e}")
                            st.error(f"詳細: {error_detail}")

        except Exception as e:
            st.error(f"権限設定エラー: {e}")
