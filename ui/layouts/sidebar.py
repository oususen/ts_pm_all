# app/ui/layouts/sidebar.py
import streamlit as st

def create_sidebar() -> str:
    """サイドバー作成"""
    with st.sidebar:
        st.title("🏭 生産計画管理")
        st.markdown("---")
        
        # ページ選択
        page = st.radio(
            "メニュー",
            [
                "ダッシュボード",
                "CSV受注取込",  # 追加
                "製品管理",
                "制限設定",
                "生産計画",
                "配送便計画",
                "納入進度",
                "📅 会社カレンダー" # ✅ 追加

            ],
            index=0
        )
        
        st.markdown("---")
        
        # 情報表示
        st.subheader("システム情報")
        st.write("**バージョン:** 1.0.1")
        st.write("**環境:** 生産環境")
        
        # ヘルプ
        with st.expander("ヘルプ"):
            st.write("""
            **各ページの説明:**
            
            - **ダッシュボード**: 全体の概要とトレンド
            - **CSV受注取込**: 受注CSVファイルのインポート
            - **製品管理**: 製品の登録・編集・削除
            - **制限設定**: 生産能力と運送制限
            - **生産計画**: 日次生産計画の作成
            - **配送便計画**: トラック積載計画
            - **納入進度**: 受注から出荷までの進捗管理
            """)
        
        return page