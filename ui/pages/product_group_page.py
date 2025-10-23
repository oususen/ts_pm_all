import math
from typing import Dict, Any

import pandas as pd
import streamlit as st


class ProductGroupPage:
    """製品群を管理するページ"""

    def __init__(self, production_service, auth_service=None):
        self.production_service = production_service
        self.auth_service = auth_service

    def _can_edit_page(self) -> bool:
        """編集権限の有無を判定"""
        if not self.auth_service:
            return True
        user = st.session_state.get("user")
        if not user:
            return False
        return self.auth_service.can_edit_page(user["id"], "製品群管理")

    def show(self):
        st.title("製品群管理")
        st.write("製品群の分類、既存データの編集、追加登録を行います。")

        can_edit = self._can_edit_page()
        if not can_edit:
            st.warning("このページの編集権限がありません。閲覧のみ可能です。")

        try:
            groups_df = self.production_service.get_all_product_groups(include_inactive=True)
        except Exception as exc:  # 安全策
            st.error(f"製品群一覧の取得に失敗しました: {exc}")
            return

        tab_list, tab_create = st.tabs(["製品群一覧", "製品群の新規登録"])

        with tab_list:
            self._show_group_overview(groups_df, can_edit)

        with tab_create:
            self._show_group_creation(can_edit)

    def _show_group_overview(self, groups_df: pd.DataFrame, can_edit: bool) -> None:
        st.header("製品群一覧")

        if groups_df is None or groups_df.empty:
            st.info("登録済みの製品群がありません。新規登録タブから追加できます。")
            return

        display_df = groups_df.copy()
        display_df = display_df.sort_values(["display_order", "group_code"], na_position="last")

        bool_columns = [
            "enable_container_management",
            "enable_transport_planning",
            "enable_progress_tracking",
            "enable_inventory_management",
            "is_active",
        ]
        for column in bool_columns:
            if column in display_df.columns:
                display_df[column] = display_df[column].map({True: "有効", False: "無効"})

        display_df = display_df.rename(columns={
            "group_code": "製品群コード",
            "group_name": "製品群名",
            "description": "説明",
            "enable_container_management": "容器管理",
            "enable_transport_planning": "輸送計画",
            "enable_progress_tracking": "進捗管理",
            "enable_inventory_management": "在庫管理",
            "default_lead_time_days": "標準リードタイム",
            "default_priority": "標準優先度",
            "is_active": "状態",
            "display_order": "表示順",
            "notes": "メモ",
            "product_count": "紐づく製品数",
        })

        st.dataframe(
            display_df[
                [
                    "製品群コード",
                    "製品群名",
                    "状態",
                    "表示順",
                    "標準リードタイム",
                    "標準優先度",
                    "容器管理",
                    "輸送計画",
                    "進捗管理",
                    "在庫管理",
                    "紐づく製品数",
                    "説明",
                    "メモ",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("製品群の編集")

        normalized_df = groups_df.where(pd.notnull(groups_df), None)

        for record in normalized_df.to_dict(orient="records"):
            header_name = record.get("group_name") or "名称未設定"
            header_code = record.get("group_code") or "コード未設定"
            with st.expander(f"{header_name} ({header_code})"):
                with st.form(f"edit_group_{record.get('id')}"):
                    col_basic, col_flags = st.columns(2)

                    with col_basic:
                        group_code = st.text_input(
                            "製品群コード",
                            value=record.get("group_code") or "",
                            max_chars=50,
                            disabled=not can_edit,
                        ).strip()
                        group_name = st.text_input(
                            "製品群名",
                            value=record.get("group_name") or "",
                            max_chars=100,
                            disabled=not can_edit,
                        ).strip()
                        display_order = st.number_input(
                            "表示順",
                            min_value=0,
                            max_value=999,
                            value=self._safe_int(record.get("display_order"), default=0),
                            step=1,
                            disabled=not can_edit,
                        )
                        is_active = st.checkbox(
                            "有効にする",
                            value=bool(record.get("is_active", True)),
                            disabled=not can_edit,
                        )
                        default_lead_time = st.number_input(
                            "標準リードタイム (日)",
                            min_value=0,
                            max_value=365,
                            value=self._safe_int(record.get("default_lead_time_days"), default=0),
                            step=1,
                            disabled=not can_edit,
                        )
                        default_priority = st.number_input(
                            "標準優先度 (1-10)",
                            min_value=0,
                            max_value=10,
                            value=self._safe_int(record.get("default_priority"), default=5),
                            step=1,
                            disabled=not can_edit,
                        )

                    with col_flags:
                        enable_container_management = st.checkbox(
                            "容器管理を有効化",
                            value=bool(record.get("enable_container_management", True)),
                            disabled=not can_edit,
                        )
                        enable_transport_planning = st.checkbox(
                            "輸送計画を有効化",
                            value=bool(record.get("enable_transport_planning", True)),
                            disabled=not can_edit,
                        )
                        enable_progress_tracking = st.checkbox(
                            "進捗管理を有効化",
                            value=bool(record.get("enable_progress_tracking", True)),
                            disabled=not can_edit,
                        )
                        enable_inventory_management = st.checkbox(
                            "在庫管理を有効化",
                            value=bool(record.get("enable_inventory_management", False)),
                            disabled=not can_edit,
                        )

                    description = st.text_area(
                        "説明",
                        value=record.get("description") or "",
                        disabled=not can_edit,
                        height=100,
                    )
                    notes = st.text_area(
                        "メモ",
                        value=record.get("notes") or "",
                        disabled=not can_edit,
                        height=100,
                    )

                    submitted = st.form_submit_button("更新", type="primary", disabled=not can_edit)

                    if submitted:
                        errors = []
                        if not group_code:
                            errors.append("製品群コードは必須です。")
                        if not group_name:
                            errors.append("製品群名は必須です。")

                        if errors:
                            for message in errors:
                                st.error(message)
                            continue

                        candidate: Dict[str, Any] = {
                            "group_code": group_code,
                            "group_name": group_name,
                            "description": description or None,
                            "display_order": int(display_order),
                            "is_active": bool(is_active),
                            "default_lead_time_days": int(default_lead_time),
                            "default_priority": int(default_priority),
                            "enable_container_management": bool(enable_container_management),
                            "enable_transport_planning": bool(enable_transport_planning),
                            "enable_progress_tracking": bool(enable_progress_tracking),
                            "enable_inventory_management": bool(enable_inventory_management),
                            "notes": notes or None,
                        }

                        update_payload = self._build_update_payload(record, candidate)

                        if not update_payload:
                            st.info("変更はありませんでした。")
                        else:
                            success = self.production_service.update_product_group(record.get("id"), update_payload)
                            if success:
                                st.success("製品群を更新しました。")
                                st.rerun()
                            else:
                                st.error("製品群の更新に失敗しました。")

    def _show_group_creation(self, can_edit: bool) -> None:
        st.header("製品群の新規登録")

        if not can_edit:
            st.info("閲覧専用のため、新規登録はできません。")
            return

        with st.form("create_product_group_form"):
            col_basic, col_flags = st.columns(2)

            with col_basic:
                group_code = st.text_input("製品群コード *", max_chars=50).strip()
                group_name = st.text_input("製品群名 *", max_chars=100).strip()
                description = st.text_area("説明", height=100)
                display_order = st.number_input("表示順", min_value=0, max_value=999, value=0, step=1)
                is_active = st.checkbox("有効にする", value=True)
                default_lead_time = st.number_input("標準リードタイム (日)", min_value=0, max_value=365, value=2, step=1)
                default_priority = st.number_input("標準優先度 (1-10)", min_value=0, max_value=10, value=5, step=1)

            with col_flags:
                enable_container_management = st.checkbox("容器管理を有効化", value=True)
                enable_transport_planning = st.checkbox("輸送計画を有効化", value=True)
                enable_progress_tracking = st.checkbox("進捗管理を有効化", value=True)
                enable_inventory_management = st.checkbox("在庫管理を有効化", value=False)
                notes = st.text_area("メモ", height=100)

            submitted = st.form_submit_button("新規製品群を登録", type="primary")

            if submitted:
                errors = []
                if not group_code:
                    errors.append("製品群コードは必須です。")
                if not group_name:
                    errors.append("製品群名は必須です。")

                if errors:
                    for message in errors:
                        st.error(message)
                else:
                    payload = {
                        "group_code": group_code,
                        "group_name": group_name,
                        "description": description or None,
                        "display_order": int(display_order),
                        "is_active": bool(is_active),
                        "default_lead_time_days": int(default_lead_time),
                        "default_priority": int(default_priority),
                        "enable_container_management": bool(enable_container_management),
                        "enable_transport_planning": bool(enable_transport_planning),
                        "enable_progress_tracking": bool(enable_progress_tracking),
                        "enable_inventory_management": bool(enable_inventory_management),
                        "notes": notes or None,
                    }

                    new_id = self.production_service.create_product_group(payload)
                    if new_id:
                        st.success(f"製品群『{group_name}』を登録しました (ID: {new_id})。")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("製品群の登録に失敗しました。")

    def _safe_int(self, value, default: int = 0) -> int:
        """NaNやNoneを扱いつつ整数に変換"""
        if value is None:
            return default
        if isinstance(value, float):
            if math.isnan(value):
                return default
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _build_update_payload(self, original: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        """差分のみを抽出して返す"""
        payload: Dict[str, Any] = {}
        for key, value in candidate.items():
            original_value = original.get(key)
            if isinstance(original_value, float) and math.isnan(original_value):
                original_value = None

            normalized_value = value
            if isinstance(value, str):
                normalized_value = value.strip() or None

            if original_value != normalized_value:
                payload[key] = normalized_value

        return payload
