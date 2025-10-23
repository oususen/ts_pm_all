#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kubota_db のテーブル構造を tiera_db にコピーするSQLスクリプトを自動生成
"""
import os
from dotenv import load_dotenv
import pymysql

# .env ファイルを読み込み
load_dotenv()

# データベース接続設定
db_config = {
    'host': os.getenv('DEV_DB_HOST', 'localhost'),
    'user': os.getenv('DEV_DB_USER', 'root'),
    'password': os.getenv('PRIMARY_DB_PASSWORD', ''),
    'database': 'kubota_db',
    'charset': 'utf8mb4',
    'port': int(os.getenv('DEV_DB_PORT', '3306'))
}

print("="*60)
print("kubota_db → tiera_db スキーマコピースクリプト生成")
print("="*60)

try:
    # データベースに接続
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()

    # kubota_db の全テーブルを取得
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    print(f"\n検出されたテーブル数: {len(tables)}")
    print("\nテーブル一覧:")
    for i, table in enumerate(tables, 1):
        print(f"  {i:2d}. {table}")

    # SQLスクリプトを生成
    sql_script = """-- =====================================
-- kubota_db のスキーマを tiera_db にコピー
-- 自動生成スクリプト
-- データは含まれません（構造のみ）
-- =====================================

-- ステップ1: tiera_db を作成（既に存在する場合はスキップ）
CREATE DATABASE IF NOT EXISTS tiera_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- ステップ2: tiera_db を使用
USE tiera_db;

-- =====================================
-- テーブル構造をコピー
-- =====================================

"""

    # 各テーブルの CREATE TABLE 文を追加
    for table in tables:
        # ユーザー管理系のテーブルはスキップ（オプション）
        # if table in ['users', 'roles', 'user_roles', 'user_page_permissions']:
        #     sql_script += f"-- {table} テーブル（スキップ：認証系）\n\n"
        #     continue

        sql_script += f"-- {table} テーブル\n"
        sql_script += f"DROP TABLE IF EXISTS {table};\n"
        sql_script += f"CREATE TABLE {table} LIKE kubota_db.{table};\n\n"

    # 確認用クエリを追加
    sql_script += """-- =====================================
-- 確認
-- =====================================
SHOW TABLES;

SELECT
    TABLE_NAME as 'テーブル名',
    TABLE_ROWS as '行数',
    CREATE_TIME as '作成日時'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'tiera_db'
ORDER BY TABLE_NAME;
"""

    # ファイルに保存
    output_file = "copy_schema_kubota_to_tiera_auto.sql"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_script)

    print(f"\n✅ SQLスクリプトを生成しました: {output_file}")
    print("\n実行方法:")
    print(f"  mysql -u root -p < {output_file}")
    print("\nまたは:")
    print(f"  mysql -u root -p")
    print(f"  source {output_file};")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
