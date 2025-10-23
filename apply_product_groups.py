import pymysql
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Windows console encoding fix
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def apply_to_database(db_name):
    """指定したデータベースに製品群テーブルを作成"""
    print(f"\n{'='*80}")
    print(f"Applying to {db_name}...")
    print('='*80)

    conn = pymysql.connect(
        host='localhost',
        user='root',
        password=os.getenv('PRIMARY_DB_PASSWORD', ''),
        database=db_name,
        charset='utf8mb4'
    )

    try:
        cursor = conn.cursor()

        # SQLファイルを読み込み
        with open('create_product_groups.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # SQLをステートメントごとに分割して実行
        statements = []
        current_statement = []
        in_delimiter = False

        for line in sql_content.split('\n'):
            stripped = line.strip()

            # コメント行をスキップ
            if stripped.startswith('--') or not stripped:
                continue

            # DELIMITER制御
            if 'DELIMITER' in stripped:
                in_delimiter = not in_delimiter
                continue

            current_statement.append(line)

            # ステートメント終了判定
            if not in_delimiter and stripped.endswith(';'):
                stmt = '\n'.join(current_statement)
                if stmt.strip():
                    statements.append(stmt)
                current_statement = []

        # 最後のステートメント
        if current_statement:
            stmt = '\n'.join(current_statement)
            if stmt.strip():
                statements.append(stmt)

        # ステートメントを実行
        for i, stmt in enumerate(statements, 1):
            try:
                # CREATE VIEW や CREATE OR REPLACE VIEW は個別処理
                if 'CREATE' in stmt.upper() and 'VIEW' in stmt.upper():
                    # 既存のビューを削除してから作成
                    if 'v_managed_products' in stmt:
                        cursor.execute("DROP VIEW IF EXISTS v_managed_products")
                    elif 'v_container_managed_products' in stmt:
                        cursor.execute("DROP VIEW IF EXISTS v_container_managed_products")

                cursor.execute(stmt)
                print(f"Statement {i}: OK")
            except pymysql.err.OperationalError as e:
                if 'already exists' in str(e) or 'Duplicate' in str(e):
                    print(f"Statement {i}: SKIP (already exists)")
                else:
                    print(f"Statement {i}: ERROR - {e}")
            except Exception as e:
                print(f"Statement {i}: ERROR - {e}")

        conn.commit()

        # 確認クエリ
        print(f"\n{db_name} - 製品群一覧:")
        cursor.execute("""
            SELECT
                id,
                group_code,
                group_name,
                enable_container_management,
                enable_transport_planning,
                is_active,
                (SELECT COUNT(*) FROM products WHERE product_group_id = pg.id) AS product_count
            FROM product_groups pg
            ORDER BY display_order
        """)
        groups = cursor.fetchall()

        if groups:
            print(f"{'ID':<5} {'Code':<12} {'Name':<12} {'Container':<10} {'Transport':<10} {'Active':<8} {'Products':<10}")
            print('-' * 80)
            for g in groups:
                print(f"{g[0]:<5} {g[1]:<12} {g[2]:<12} {str(g[3]):<10} {str(g[4]):<10} {str(g[5]):<8} {g[6]:<10}")
        else:
            print("  (No product groups found)")

        print(f"\n{db_name} - 製品群別製品数:")
        cursor.execute("""
            SELECT
                COALESCE(pg.group_name, 'Unassigned') AS group_name,
                COUNT(p.id) AS product_count
            FROM products p
            LEFT JOIN product_groups pg ON p.product_group_id = pg.id
            GROUP BY pg.group_name
            ORDER BY product_count DESC
        """)
        counts = cursor.fetchall()
        for count in counts:
            print(f"  {count[0]:<20}: {count[1]} products")

        print(f"\nOK: Successfully applied to {db_name}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    # Kubota DBに適用
    apply_to_database('kubota_db')

    # Tiera DBに適用
    apply_to_database('tiera_db')

    print(f"\n{'='*80}")
    print("All databases updated successfully!")
    print('='*80)
