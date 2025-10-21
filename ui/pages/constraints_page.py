# app/ui/pages/constraints_page.py
import streamlit as st
import pandas as pd
from ui.components.forms import FormComponents

class ConstraintsPage:
    """制限設定ページ - 生産・運送制約の設定画面"""
    
    def __init__(self, production_service, auth_service=None):
        self.service = production_service
        self.auth_service = auth_service

    def _can_edit_page(self) -> bool:
        """ページ編集権限チェック"""
        if not self.auth_service:
            return True
        user = st.session_state.get('user')
        if not user:
            return False
        return self.auth_service.can_edit_page(user['id'], "制限設定")
    
    def show(self):
        """ページ表示"""
        st.title("⚙️ 生産・運送制限設定")

        # 権限チェック
        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("⚠️ この画面の編集権限がありません。閲覧のみ可能です。")

        tab1, tab2 = st.tabs(["生産能力設定", "運送制限設定"])

        with tab1:
            self._show_production_constraints(can_edit)
        with tab2:
            self._show_transport_constraints()
    
    def _show_production_constraints(self, can_edit):
        """生産制約設定表示"""
        st.header("🏭 生産能力設定")
        st.write("製品ごとの生産能力と平均化レベルを設定します。")
        
        try:
            products = self.service.get_all_products()
            existing_constraints = self.service.get_product_constraints()
            
            if not products:
                st.warning("製品データがありません")
                return
            
            # 製品データを辞書形式に変換
            products_dict = [{
                'id': product.id,
                'product_code': product.product_code,
                'product_name': product.product_name
            } for product in products]
            
            # 既存制約を辞書形式に変換
            constraints_dict = [{
                'product_id': constraint.product_id,
                'daily_capacity': constraint.daily_capacity,
                'smoothing_level': constraint.smoothing_level,
                'volume_per_unit': constraint.volume_per_unit,
                'is_transport_constrained': constraint.is_transport_constrained
            } for constraint in existing_constraints]
            
            st.info("各製品の生産制約を設定してください")
            
            # フォーム表示
            constraints_data = FormComponents.product_constraints_form(
                products_dict, constraints_dict
            )
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 生産制約を保存", type="primary", disabled=not can_edit):
                    try:
                        self.service.save_product_constraints(constraints_data)
                        st.success("生産制約設定を保存しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存エラー: {e}")

            with col2:
                if st.button("🔄 デフォルト値にリセット", disabled=not can_edit):
                    st.info("リセットするにはページを再読み込みしてください")
            
            # 現在の設定表示
            st.subheader("現在の設定")
            if existing_constraints:
                display_df = pd.DataFrame([{
                    '製品コード': constraint.product_code,
                    '製品名': constraint.product_name,
                    '日次生産能力': constraint.daily_capacity,
                    '平均化レベル': constraint.smoothing_level,
                    '単位体積': constraint.volume_per_unit,
                    '運送制限': '✅' if constraint.is_transport_constrained else '❌'
                } for constraint in existing_constraints])
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("設定が保存されていません")
                
        except Exception as e:
            st.error(f"データ取得エラー: {e}")
    
    def _show_transport_constraints(self):
        """運送制限設定表示"""
        st.header("🚚 運送制限設定")
        st.write("トラックの積載制限と運行制約を設定します。")
        
        st.info("この機能は現在開発中です")
        st.write("以下の設定が予定されています:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**トラック制限**")
            st.write("• 最大積載重量")
            st.write("• 最大積載体積") 
            st.write("• 1日最大便数")
            st.write("• 時間帯制限")
        
        with col2:
            st.write("**運行制限**")
            st.write("• エリア制限")
            st.write("• 時間制限")
            st.write("• 車種制限")
            st.write("• 積載優先順位")