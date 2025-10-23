# app/ui/pages/product_page.py
import streamlit as st
import pandas as pd
from ui.components.forms import FormComponents

class ProductPage:
    """製品管理ページ - マトリックス編集対応"""
    
    def __init__(self, production_service, transport_service, auth_service=None):
        self.production_service = production_service
        self.transport_service = transport_service
        self.auth_service = auth_service

    def _can_edit_page(self) -> bool:
        """ページ編集権限チェック"""
        if not self.auth_service:
            return True
        user = st.session_state.get('user')
        if not user:
            return False
        return self.auth_service.can_edit_page(user['id'], "製品管理")
    
    def show(self):
        """ページ表示"""
        st.title("📦 製品管理")
        st.write("製品の登録・編集・削除、および容器との紐付けを管理します。")

        # 権限チェック
        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("⚠️ この画面の編集権限がありません。閲覧のみ可能です。")

        tab1, tab2, tab3 = st.tabs(["📊 製品一覧（マトリックス）", "➕ 製品登録", "🔗 製品×容器紐付け"])

        with tab1:
            self._show_product_matrix(can_edit)
        with tab2:
            self._show_product_registration(can_edit)
        with tab3:
            self._show_product_container_mapping()
    
    def _show_product_matrix(self, can_edit):
        """製品一覧 - マトリックス編集"""
        st.header("📊 製品一覧（編集可能）")
        
        try:
            products = self.production_service.get_all_products()
            containers = self.transport_service.get_containers()
            trucks_df = self.transport_service.get_trucks()
            product_groups_df = self.production_service.get_product_groups()

            if not products:
                st.info("登録されている製品がありません")
                return

            # 容器マップ作成
            container_map = {c.id: c.name for c in containers} if containers else {}
            container_name_to_id = {c.name: c.id for c in containers} if containers else {}

            # トラックマップ作成
            truck_map = dict(zip(trucks_df['id'], trucks_df['name'])) if not trucks_df.empty else {}
            truck_name_to_id = dict(zip(trucks_df['name'], trucks_df['id'])) if not trucks_df.empty else {}

            # 製品群マップ作成
            product_group_map = {}
            product_group_name_to_id = {}
            if not product_groups_df.empty:
                product_group_map = dict(zip(product_groups_df['id'], product_groups_df['group_name']))
                product_group_name_to_id = dict(zip(product_groups_df['group_name'], product_groups_df['id']))
            
            # DataFrame作成 - デフォルト値の設定を強化
            products_data = []
            for p in products:
                # 容器IDの取得（様々な属性名に対応）
                used_container_id = getattr(p, 'used_container_id', None) or getattr(p, 'container_id', None)
                
                # トラックIDの取得（様々な属性名に対応）
                used_truck_ids = getattr(p, 'used_truck_ids', None) or getattr(p, 'truck_ids', None)
                
                # 製品群IDの取得
                product_group_id = getattr(p, 'product_group_id', None)

                # その他の属性も同様に取得
                product_data = {
                    'ID': p.id,
                    '製品コード': getattr(p, 'product_code', '') or '',
                    '製品名': getattr(p, 'product_name', '') or '',
                    '製品群': product_group_map.get(product_group_id, '未設定') if product_group_id else '未設定',
                    '使用容器': container_map.get(used_container_id, '未設定') if used_container_id else '未設定',
                    '入り数': int(getattr(p, 'capacity', 0) or 0),
                    '検査区分': getattr(p, 'inspection_category', 'N') or 'N',
                    'リードタイム': int(getattr(p, 'lead_time_days', 0) or 0),
                    '固定日数': int(getattr(p, 'fixed_point_days', 0) or 0),
                    '前倒可': bool(getattr(p, 'can_advance', False)),
                    '使用トラック': ', '.join(self._get_truck_names_by_ids(used_truck_ids)) or '未設定'
                }
                products_data.append(product_data)
            
            products_df = pd.DataFrame(products_data)
            
            # サマリー
            st.subheader("📋 製品統計")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("登録製品数", len(products_df))
            with col2:
                can_advance_count = len(products_df[products_df['前倒可'] == True])
                st.metric("前倒可能製品", can_advance_count)
            with col3:
                n_count = len(products_df[products_df['検査区分'] == 'N'])
                st.metric("検査区分N", n_count)
            with col4:
                avg_capacity = products_df['入り数'].mean() if len(products_df) > 0 else 0
                st.metric("平均入り数", f"{avg_capacity:.0f}")
            
            st.markdown("---")
            st.subheader("✏️ 製品情報編集（セルをダブルクリックで編集）")
            
            st.info("""
            **編集方法:**
            1. セルをダブルクリックして値を変更
            2. 変更が完了したら「💾 変更を保存」をクリック
            3. 削除する場合は「🗑️ 選択製品を削除」をクリック
            """)
            
            # 編集可能なデータエディタ
            edited_df = st.data_editor(
                products_df,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                disabled=['ID', '使用トラック'],  # ID・使用トラックは編集不可（個別編集で設定）
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "製品コード": st.column_config.TextColumn("製品コード", width="medium", required=True),
                    "製品名": st.column_config.TextColumn("製品名", width="medium", required=True),
                    "製品群": st.column_config.SelectboxColumn(
                        "製品群",
                        options=['未設定'] + list(product_group_name_to_id.keys()),
                        width="medium",
                        help="この製品が属する製品群を選択"
                    ),
                    "使用容器": st.column_config.SelectboxColumn(
                        "使用容器",
                        options=['未設定'] + list(container_name_to_id.keys()),
                        width="medium"
                    ),
                    "入り数": st.column_config.NumberColumn("入り数", min_value=0, step=1),
                    "検査区分": st.column_config.SelectboxColumn(
                        "検査区分",
                        options=['N', 'NS', 'F', 'FS', '$S', ''],
                        width="small"
                    ),
                    "リードタイム": st.column_config.NumberColumn(
                        "リードタイム(日)",
                        min_value=0,
                        step=1,
                        help="納品日の何日前に積載するか（0=納品日当日、2=2日前など）"
                    ),
                    "固定日数": st.column_config.NumberColumn("固定日数(日)", min_value=0, step=1),
                    "前倒可": st.column_config.CheckboxColumn("前倒可"),
                    "使用トラック": st.column_config.TextColumn("使用トラック", width="medium", disabled=True, help="個別編集で設定してください")
                },
                key="product_matrix_editor"
            )
            
            # 保存・削除ボタン
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
            
            with col_btn1:
                if st.button("💾 変更を保存", type="primary", use_container_width=True, disabled=not can_edit):
                    changes_saved = self._save_product_changes(
                        original_df=products_df,
                        edited_df=edited_df,
                        container_name_to_id=container_name_to_id,
                        truck_name_to_id=truck_name_to_id,
                        product_group_name_to_id=product_group_name_to_id
                    )
                    
                    if changes_saved:
                        st.success("✅ 変更を保存しました")
                        st.rerun()
                    else:
                        st.info("変更はありませんでした")
            
            with col_btn2:
                if st.button("🗑️ 選択製品を削除", type="secondary", use_container_width=True, disabled=not can_edit):
                    st.warning("削除機能は個別製品選択後に実行してください")
            
            # 詳細編集エリア（トラック選択対応）
            st.markdown("---")
            st.subheader("🔍 個別製品の詳細編集・削除（トラック選択可）")
            
            st.info("💡 **使用トラックの設定**は、こちらの個別編集で行ってください（複数選択可能）")
            
            product_options = {f"{row['製品コード']} - {row['製品名']}": row['ID'] for _, row in products_df.iterrows()}
            selected_product_key = st.selectbox(
                "編集・削除する製品を選択",
                options=list(product_options.keys()),
                key="product_detail_selector"
            )
            
            if selected_product_key:
                product_id = product_options[selected_product_key]
                product = next((p for p in products if p.id == product_id), None)
                
                if product:
                    self._show_product_detail_editor_with_truck_select(product, containers, trucks_df, container_map, can_edit)
        
        except Exception as e:
            st.error(f"製品一覧エラー: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    def _save_product_changes(self, original_df, edited_df, container_name_to_id, truck_name_to_id, product_group_name_to_id=None):
        """マトリックスの変更をデータベースに保存"""

        changes_made = False

        for idx, edited_row in edited_df.iterrows():
            if idx >= len(original_df):
                # 新規行の場合（スキップまたは新規登録処理）
                continue

            original_row = original_df.iloc[idx]
            product_id = int(edited_row['ID'])

            # 変更があったか確認
            update_data = {}

            # 製品コード
            if edited_row['製品コード'] != original_row['製品コード']:
                update_data['product_code'] = edited_row['製品コード']

            # 製品名
            if edited_row['製品名'] != original_row['製品名']:
                update_data['product_name'] = edited_row['製品名']

            # 製品群
            if product_group_name_to_id and '製品群' in edited_row:
                new_group_name = edited_row['製品群']
                original_group_name = original_row['製品群']
                if new_group_name != original_group_name:
                    if new_group_name == '未設定':
                        update_data['product_group_id'] = None
                    else:
                        update_data['product_group_id'] = product_group_name_to_id.get(new_group_name)

            # 使用容器
            new_container_name = edited_row['使用容器']
            original_container_name = original_row['使用容器']
            if new_container_name != original_container_name:
                if new_container_name == '未設定':
                    update_data['used_container_id'] = None
                else:
                    update_data['used_container_id'] = container_name_to_id.get(new_container_name)
            
            # 入り数
            if int(edited_row['入り数']) != int(original_row['入り数']):
                update_data['capacity'] = int(edited_row['入り数'])
            
            # 検査区分
            if edited_row['検査区分'] != original_row['検査区分']:
                update_data['inspection_category'] = edited_row['検査区分']
            
            # リードタイム
            if int(edited_row['リードタイム']) != int(original_row['リードタイム']):
                update_data['lead_time_days'] = int(edited_row['リードタイム'])
            
            # 固定日数
            if int(edited_row['固定日数']) != int(original_row['固定日数']):
                update_data['fixed_point_days'] = int(edited_row['固定日数'])
            
            # 前倒可
            if bool(edited_row['前倒可']) != bool(original_row['前倒可']):
                update_data['can_advance'] = bool(edited_row['前倒可'])
            
            # 変更があれば保存
            if update_data:
                success = self.production_service.update_product(product_id, update_data)
                if success:
                    changes_made = True
                    st.toast(f"✅ 製品ID={product_id} を更新しました")
                else:
                    st.toast(f"❌ 製品ID={product_id} の更新に失敗")
        
        return changes_made
    
    def _show_product_detail_editor_with_truck_select(self, product, containers, trucks_df, container_map, can_edit):
        """個別製品の詳細編集・削除（トラック複数選択対応）"""
        
        with st.container(border=True):
            st.write(f"**製品詳細編集: {getattr(product, 'product_code', 'N/A')}**")
            
            # 現在の情報表示
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.write("**基本情報**")
                st.write(f"ID: {product.id}")
                st.write(f"製品コード: {getattr(product, 'product_code', '-')}")
                st.write(f"製品名: {getattr(product, 'product_name', '-')}")
                st.write(f"入り数: {getattr(product, 'capacity', 0)}")
            
            with col_info2:
                st.write("**容器情報**")
                used_container_id = getattr(product, 'used_container_id', None) or getattr(product, 'container_id', None)
                st.write(f"使用容器: {container_map.get(used_container_id, '未設定') if used_container_id else '未設定'}")
                st.write(f"検査区分: {getattr(product, 'inspection_category', 'N')}")
            
            with col_info3:
                st.write("**納期・制約**")
                st.write(f"リードタイム: {getattr(product, 'lead_time_days', 0)} 日")
                st.write(f"固定日数: {getattr(product, 'fixed_point_days', 0)} 日")
                st.write(f"前倒可: {'✅' if getattr(product, 'can_advance', False) else '❌'}")
            
            st.markdown("---")
            
            # トラック複数選択編集フォーム
            with st.form(f"edit_truck_form_{product.id}"):
                st.write("**🚛 使用トラック設定（優先順位付き）**")
                
                # 使用トラック選択（複数選択）
                if not trucks_df.empty:
                    truck_options = dict(zip(trucks_df['name'], trucks_df['id']))
                    
                    # 現在のトラックIDを取得（様々な属性名に対応）
                    current_truck_ids = []
                    used_truck_ids = getattr(product, 'used_truck_ids', None) or getattr(product, 'truck_ids', None)
                    
                    if used_truck_ids:
                        try:
                            current_truck_ids = [int(tid.strip()) for tid in str(used_truck_ids).split(',')]
                        except:
                            current_truck_ids = []
                    
                    # 現在選択中のトラック名を取得
                    truck_name_map = dict(zip(trucks_df['id'], trucks_df['name']))
                    current_truck_names = [truck_name_map.get(tid) for tid in current_truck_ids if tid in truck_name_map]
                    
                    st.info("💡 **優先順位**: 上から順に優先度が高くなります（ドラッグ&ドロップで並び替え可能）")
                    
                    new_used_trucks = st.multiselect(
                        "使用トラック（複数選択可・上から優先）",
                        options=list(truck_options.keys()),
                        default=current_truck_names,
                        key=f"trucks_{product.id}",
                        help="上にあるトラックほど優先的に使用されます"
                    )
                    
                    # 優先順位の説明
                    if new_used_trucks:
                        st.success(f"**設定される優先順位:** 1位: {new_used_trucks[0]}" + 
                                 (f" → 2位: {new_used_trucks[1]}" if len(new_used_trucks) > 1 else "") +
                                 (f" → 3位: {new_used_trucks[2]}" if len(new_used_trucks) > 2 else ""))
                else:
                    new_used_trucks = []
                    st.info("トラックが登録されていません")
                
                # 現在の設定を表示
                if current_truck_names:
                    st.info(f"現在の設定（優先順）: {' → '.join(current_truck_names)}")
                else:
                    st.warning("トラックが未設定です")
                
                submitted = st.form_submit_button("💾 トラック設定を保存", type="primary", disabled=not can_edit)
                
                if submitted:
                    # ✅ 選択された順番でトラックIDを保存（優先順位）
                    selected_truck_ids = [truck_options[name] for name in new_used_trucks] if new_used_trucks else []
                    used_truck_ids_str = ','.join(map(str, selected_truck_ids)) if selected_truck_ids else None
                    
                    update_data = {
                        "used_truck_ids": used_truck_ids_str
                    }
                    
                    success = self.production_service.update_product(product.id, update_data)
                    if success:
                        st.success(f"✅ 製品 '{getattr(product, 'product_code', 'N/A')}' のトラック設定を更新しました")
                        st.rerun()
                    else:
                        st.error("❌ トラック設定の更新に失敗しました")
            
            # 削除ボタン
            st.markdown("---")
            col_del1, col_del2 = st.columns([1, 5])
            
            with col_del1:
                if st.button("🗑️ この製品を削除", key=f"delete_product_{product.id}", type="secondary", use_container_width=True, disabled=not can_edit):
                    if st.session_state.get(f"confirm_delete_{product.id}", False):
                        success = self.production_service.delete_product(product.id)
                        if success:
                            st.success(f"製品 '{getattr(product, 'product_code', 'N/A')}' を削除しました")
                            # 確認フラグをリセット
                            st.session_state[f"confirm_delete_{product.id}"] = False
                            st.rerun()
                        else:
                            st.error("製品削除に失敗しました")
                    else:
                        st.session_state[f"confirm_delete_{product.id}"] = True
                        st.warning("⚠️ もう一度クリックすると削除されます")
            
            with col_del2:
                if st.session_state.get(f"confirm_delete_{product.id}", False):
                    st.error("⚠️ 削除確認中 - もう一度「削除」ボタンをクリックしてください")
    
    def _get_truck_names_by_ids(self, truck_ids_str):
        """トラックIDの文字列からトラック名のリストを取得"""
        if not truck_ids_str:
            return []
        try:
            trucks_df = self.transport_service.get_trucks()
            if trucks_df.empty:
                return []
            truck_map = dict(zip(trucks_df['id'], trucks_df['name']))
            truck_ids = [int(tid.strip()) for tid in str(truck_ids_str).split(',')]
            return [truck_map.get(tid, f"ID:{tid}") for tid in truck_ids]
        except:
            return []
    
    def _show_product_registration(self, can_edit):
        """新規製品登録"""
        st.header("➕ 新規製品登録")

        if not can_edit:
            st.info("編集権限がないため、新規登録はできません")
            return

        try:
            containers = self.transport_service.get_containers()
            trucks_df = self.transport_service.get_trucks()
            product_data = FormComponents.product_form(containers, trucks_df)

            if product_data:
                success = self.production_service.create_product(product_data)
                if success:
                    st.success(f"製品 '{product_data['product_name']}' を登録しました")
                    st.rerun()
                else:
                    st.error("製品登録に失敗しました")
        
        except Exception as e:
            st.error(f"製品登録エラー: {e}")
    
    def _show_product_container_mapping(self):
        """製品×容器紐付け管理"""
        st.header("🔗 製品×容器紐付け設定")
        
        st.warning("""
        **この機能は product_container_mapping テーブルが必要です**
        
        以下のSQLを実行してテーブルを作成してください:
        """)
        
        st.code("""
CREATE TABLE product_container_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    container_id INT NOT NULL,
    max_quantity INT DEFAULT 100 COMMENT '容器あたりの最大積載数',
    is_primary TINYINT(1) DEFAULT 0 COMMENT '主要容器フラグ',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (container_id) REFERENCES container_capacity(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_container (product_id, container_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='製品と容器の紐付けマスタ';
        """, language="sql")
        
        st.info("テーブル作成後、この機能を実装します。")