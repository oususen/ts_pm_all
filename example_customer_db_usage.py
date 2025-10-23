#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顧客別データベース管理の使用例

このスクリプトは CustomerDatabaseManager の使い方を示します。
"""

from repository.database_manager import CustomerDatabaseManager

def example_basic_usage():
    """基本的な使い方"""
    print("=" * 60)
    print("例1: 基本的な使い方")
    print("=" * 60)

    # デフォルト顧客（kubota）で初期化
    db = CustomerDatabaseManager()

    print(f"現在の顧客: {db.get_current_customer()}")

    # 久保田様のデータ取得
    df = db.execute_query("SELECT * FROM products LIMIT 5")
    print(f"\n久保田様の製品データ: {len(df)}件")
    print(df.head())

    # 接続を閉じる
    db.close()
    print()


def example_customer_switching():
    """顧客切り替えの例"""
    print("=" * 60)
    print("例2: 顧客切り替え")
    print("=" * 60)

    db = CustomerDatabaseManager()

    # 久保田様のデータ取得
    print(f"現在の顧客: {db.get_current_customer()}")
    df_kubota = db.execute_query("SELECT COUNT(*) as count FROM products")
    print(f"久保田様の製品数: {df_kubota.iloc[0]['count'] if not df_kubota.empty else 0}")

    # ティエラ様に切り替え
    db.switch_customer("tiera")
    print(f"\n現在の顧客: {db.get_current_customer()}")
    df_tiera = db.execute_query("SELECT COUNT(*) as count FROM products")
    print(f"ティエラ様の製品数: {df_tiera.iloc[0]['count'] if not df_tiera.empty else 0}")

    db.close()
    print()


def example_direct_customer_query():
    """顧客を直接指定してクエリを実行"""
    print("=" * 60)
    print("例3: 顧客を直接指定")
    print("=" * 60)

    db = CustomerDatabaseManager()

    # 現在の顧客はkubotaのまま、tieraのデータを取得
    print(f"現在の顧客: {db.get_current_customer()}")

    df_kubota = db.execute_query(
        "SELECT * FROM products LIMIT 3",
        customer="kubota"
    )
    print(f"\n久保田様のデータ: {len(df_kubota)}件")

    df_tiera = db.execute_query(
        "SELECT * FROM products LIMIT 3",
        customer="tiera"
    )
    print(f"ティエラ様のデータ: {len(df_tiera)}件")

    print(f"\n現在の顧客は変わっていません: {db.get_current_customer()}")

    db.close()
    print()


def example_context_manager():
    """コンテキストマネージャーを使った安全な接続管理"""
    print("=" * 60)
    print("例4: コンテキストマネージャー（推奨）")
    print("=" * 60)

    # with文で自動的に接続が閉じられる
    with CustomerDatabaseManager() as db:
        print(f"現在の顧客: {db.get_current_customer()}")

        df = db.execute_query("SELECT * FROM products LIMIT 5")
        print(f"取得データ: {len(df)}件")

    # ここで自動的に db.close() が呼ばれる
    print("接続が自動的に閉じられました")
    print()


def example_insert_update():
    """データの挿入・更新の例"""
    print("=" * 60)
    print("例5: データの挿入・更新")
    print("=" * 60)

    with CustomerDatabaseManager(customer="tiera") as db:
        print(f"現在の顧客: {db.get_current_customer()}")

        # 例: 新しい注文を挿入（実際のテーブル構造に合わせて調整してください）
        # insert_query = """
        #     INSERT INTO orders (customer_name, product_id, quantity, order_date)
        #     VALUES (:customer_name, :product_id, :quantity, NOW())
        # """
        # params = {
        #     "customer_name": "テスト顧客",
        #     "product_id": 1,
        #     "quantity": 10
        # }
        # db.execute_non_query(insert_query, params)
        # print("データを挿入しました")

        print("※ 実際のテーブル構造に合わせてコードを調整してください")

    print()


def example_multi_customer_comparison():
    """複数顧客のデータを比較"""
    print("=" * 60)
    print("例6: 複数顧客のデータ比較")
    print("=" * 60)

    with CustomerDatabaseManager() as db:
        # 両方の顧客のデータを取得
        customers = ["kubota", "tiera"]

        for customer in customers:
            count_df = db.execute_query(
                "SELECT COUNT(*) as count FROM products",
                customer=customer
            )
            count = count_df.iloc[0]['count'] if not count_df.empty else 0
            print(f"{customer.upper()}様の製品数: {count}")

    print()


def main():
    """全ての例を実行"""
    print("\n顧客別データベース管理 - 使用例\n")

    try:
        example_basic_usage()
        example_customer_switching()
        example_direct_customer_query()
        example_context_manager()
        example_insert_update()
        example_multi_customer_comparison()

        print("=" * 60)
        print("全ての例を実行しました")
        print("=" * 60)

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
