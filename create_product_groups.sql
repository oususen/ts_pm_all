-- ================================================================
-- 製品群管理テーブル作成スクリプト
-- 作成日: 2025-10-24
-- 目的: 製品を製品群でグループ化し、管理範囲を柔軟に設定
-- ================================================================

-- ================================================================
-- 1. 製品群マスタテーブル作成
-- ================================================================
--
-- 【カラム説明と用途】
--
-- ■ 基本情報
-- id                           : 主キー（自動採番）
-- group_code                   : 製品群コード（例: FLOOR, WALL, CEILING）
--                                用途: システム内部での識別、プログラムでの判定に使用
-- group_name                   : 製品群名（例: フロア、壁、天井）
--                                用途: UI表示用の日本語名称
-- description                  : 製品群の説明
--                                用途: この製品群が何を含むかの詳細説明
--
-- ■ 機能有効フラグ（製品群ごとに管理機能を個別にON/OFF）
-- enable_container_management  : 容器管理を有効にするか（TRUE=有効, FALSE=無効）
--                                用途: この製品群に容器を割り当てて管理する場合TRUE
--                                      容器を使わない製品群はFALSE
-- enable_transport_planning    : 輸送計画を有効にするか
--                                用途: この製品群を積載計画の対象にする場合TRUE
--                                      輸送しない製品群はFALSE
-- enable_progress_tracking     : 進捗管理を有効にするか
--                                用途: 納入実績や進度を追跡する場合TRUE
--                                      追跡不要な製品群はFALSE
-- enable_inventory_management  : 在庫管理を有効にするか
--                                用途: 将来的に在庫管理を追加する場合に備えたフラグ
--                                      現時点では全てFALSE
--
-- ■ デフォルト設定（この製品群に属する製品の初期値）
-- default_lead_time_days       : この製品群のデフォルトリードタイム（日数）
--                                用途: 新規製品登録時の初期値として使用
--                                      例: フロアは2日、壁は3日など
-- default_priority             : この製品群のデフォルト優先度（1-10）
--                                用途: 複数製品群がある場合の優先順位
--                                      数値が大きいほど優先度高
--
-- ■ メタ情報
-- is_active                    : この製品群が有効かどうか（TRUE=有効, FALSE=無効）
--                                用途: 将来追加予定の製品群をFALSEで登録しておき、
--                                      必要になったらTRUEに変更して有効化
--                                      無効な製品群は製品管理画面に表示されない
-- display_order                : 画面表示時の並び順（昇順）
--                                用途: UI上での表示順序を制御
--                                      例: フロア=1, 壁=2, 天井=3
-- notes                        : 備考・メモ
--                                用途: 管理者向けの補足情報
--
-- ■ タイムスタンプ
-- created_at                   : レコード作成日時（自動設定）
-- updated_at                   : レコード更新日時（自動更新）
--
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

-- フロア製品群を登録（現在管理中）
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
    'フロア製品群（建機のフロア部品）',
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
    'BLADE',
    'ブレード',
    'ブレード製品群（建機のブレード部品・将来追加予定）',
    TRUE,   -- 容器管理を想定
    TRUE,   -- 輸送計画を想定
    TRUE,   -- 進捗管理を想定
    2,
    FALSE,  -- まだ無効
    2
),
(
    'OIL_TANK',
    'オイルタンク',
    'オイルタンク製品群（建機のオイルタンク部品・将来追加予定）',
    TRUE,   -- 容器管理を想定
    TRUE,   -- 輸送計画を想定
    TRUE,   -- 進捗管理を想定
    2,
    FALSE,  -- まだ無効
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
