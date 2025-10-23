-- ================================================================
-- 製品群管理テーブル作成スクリプト
-- 作成日: 2025-10-24
-- 目的: 製品を製品群でグループ化し、管理範囲を柔軟に設定
-- ================================================================

-- ================================================================
-- 1. 製品群マスタテーブル作成
-- ================================================================

CREATE TABLE IF NOT EXISTS product_groups (
    id INT PRIMARY KEY AUTO_INCREMENT,
    group_code VARCHAR(50) NOT NULL UNIQUE COMMENT '製品群コード（英数字）',
    group_name VARCHAR(100) NOT NULL UNIQUE COMMENT '製品群名（日本語）',
    description TEXT COMMENT '説明',

    -- 機能有効フラグ
    enable_container_management BOOLEAN DEFAULT TRUE COMMENT '容器管理有効',
    enable_transport_planning BOOLEAN DEFAULT TRUE COMMENT '輸送計画有効',
    enable_progress_tracking BOOLEAN DEFAULT TRUE COMMENT '進捗管理有効',
    enable_inventory_management BOOLEAN DEFAULT FALSE COMMENT '在庫管理有効',

    -- デフォルト設定
    default_lead_time_days INT DEFAULT 2 COMMENT 'デフォルトリードタイム（日）',
    default_priority INT DEFAULT 5 COMMENT 'デフォルト優先度（1-10）',

    -- メタ情報
    is_active BOOLEAN DEFAULT TRUE COMMENT '有効/無効',
    display_order INT DEFAULT 0 COMMENT '表示順序',
    notes TEXT COMMENT '備考',

    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',

    INDEX idx_group_code (group_code),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='製品群マスタ';


-- ================================================================
-- 2. productsテーブルに製品群ID列を追加
-- ================================================================

ALTER TABLE products
ADD COLUMN product_group_id INT DEFAULT NULL COMMENT '製品群ID' AFTER product_name,
ADD INDEX idx_product_group_id (product_group_id),
ADD CONSTRAINT fk_products_product_group
    FOREIGN KEY (product_group_id)
    REFERENCES product_groups(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;


-- ================================================================
-- 3. 初期データ投入
-- ================================================================

-- フロア製品群を登録
INSERT INTO product_groups (
    group_code,
    group_name,
    description,
    enable_container_management,
    enable_transport_planning,
    enable_progress_tracking,
    default_lead_time_days,
    default_priority,
    display_order
) VALUES (
    'FLOOR',
    'フロア',
    'フロア製品群（床材関連製品）',
    TRUE,   -- 容器管理有効
    TRUE,   -- 輸送計画有効
    TRUE,   -- 進捗管理有効
    2,      -- リードタイム2日
    5,      -- 優先度5
    1       -- 表示順序1
);

-- 将来追加予定の製品群（サンプル）
INSERT INTO product_groups (
    group_code,
    group_name,
    description,
    enable_container_management,
    enable_transport_planning,
    enable_progress_tracking,
    default_lead_time_days,
    is_active,
    display_order
) VALUES
(
    'WALL',
    '壁',
    '壁材関連製品（将来追加予定）',
    FALSE,  -- まだ容器管理しない
    FALSE,  -- まだ輸送計画しない
    FALSE,  -- まだ進捗管理しない
    2,
    FALSE,  -- まだ無効
    2
),
(
    'CEILING',
    '天井',
    '天井材関連製品（将来追加予定）',
    FALSE,
    FALSE,
    FALSE,
    2,
    FALSE,
    3
);


-- ================================================================
-- 4. 既存製品を製品群に紐付け
-- ================================================================

-- ユーザーが必要に応じて手動で設定してください
-- 例:
-- UPDATE products
-- SET product_group_id = (SELECT id FROM product_groups WHERE group_code = 'FLOOR')
-- WHERE product_code LIKE 'YD%';


-- ================================================================
-- 5. 確認用クエリ
-- ================================================================

-- 製品群一覧
SELECT
    id,
    group_code,
    group_name,
    enable_container_management AS '容器管理',
    enable_transport_planning AS '輸送計画',
    enable_progress_tracking AS '進捗管理',
    is_active AS '有効',
    (SELECT COUNT(*) FROM products WHERE product_group_id = pg.id) AS '製品数'
FROM product_groups pg
ORDER BY display_order;

-- 製品群別の製品数
SELECT
    COALESCE(pg.group_name, '未分類') AS 製品群,
    COUNT(p.id) AS 製品数
FROM products p
LEFT JOIN product_groups pg ON p.product_group_id = pg.id
GROUP BY pg.group_name
ORDER BY 製品数 DESC;

-- 管理対象製品の一覧（容器管理が有効な製品群のみ）
SELECT
    p.product_code,
    p.product_name,
    pg.group_name AS 製品群
FROM products p
INNER JOIN product_groups pg ON p.product_group_id = pg.id
WHERE pg.enable_container_management = TRUE
  AND pg.is_active = TRUE
ORDER BY pg.display_order, p.product_code;


-- ================================================================
-- 6. 便利なビュー作成（オプション）
-- ================================================================

-- 管理対象製品のビュー
CREATE OR REPLACE VIEW v_managed_products AS
SELECT
    p.*,
    pg.group_code,
    pg.group_name,
    pg.enable_container_management,
    pg.enable_transport_planning,
    pg.enable_progress_tracking
FROM products p
INNER JOIN product_groups pg ON p.product_group_id = pg.id
WHERE pg.is_active = TRUE;

-- 容器管理対象製品のビュー
CREATE OR REPLACE VIEW v_container_managed_products AS
SELECT
    p.*,
    pg.group_code,
    pg.group_name
FROM products p
INNER JOIN product_groups pg ON p.product_group_id = pg.id
WHERE pg.enable_container_management = TRUE
  AND pg.is_active = TRUE;


-- ================================================================
-- 使用例
-- ================================================================

/*
-- 新しい製品群を追加
INSERT INTO product_groups (group_code, group_name, description, enable_container_management)
VALUES ('DOOR', 'ドア', 'ドア関連製品', TRUE);

-- 製品を製品群に紐付け
UPDATE products
SET product_group_id = (SELECT id FROM product_groups WHERE group_code = 'DOOR')
WHERE product_code LIKE 'DR%';

-- 製品群の設定を変更（容器管理を有効化）
UPDATE product_groups
SET enable_container_management = TRUE,
    is_active = TRUE
WHERE group_code = 'WALL';

-- 容器管理対象製品のみ取得
SELECT * FROM v_container_managed_products;
*/
