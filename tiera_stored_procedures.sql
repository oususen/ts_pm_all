-- ================================================================
-- Tiera DB用ストアドプロシージャ
-- 作成日: 2025-10-24
-- ================================================================
--以下の2つのストアドプロシージャをTiera DBに作成しました：
-- ✅ recompute_planned_progress_by_product
-- 計画進捗残を日別に再計算
-- 前日残 + (出荷実績 or 計画数) - 注文数
-- ✅ recompute_shipped_remaining_by_product
-- 出荷残を日別に再計算
-- 前日残 + 出荷実績 - 注文数
-- データベース選択
USE tiera_db;

-- ================================================================
-- 1. recompute_planned_progress_by_product
--    計画進捗残の再計算
-- ================================================================

DROP PROCEDURE IF EXISTS recompute_planned_progress_by_product;

DELIMITER $$

CREATE PROCEDURE `recompute_planned_progress_by_product`(
    IN p_product_id INT,
    IN p_start_date DATE,
    IN p_end_date   DATE
)
BEGIN
    DECLARE v_prev_pp INT DEFAULT 0;

    -- 前日残（p_start_dateの前日）の計画進捗残を初期値に採用。なければ0
    SELECT COALESCE(planned_progress_quantity, 0)
      INTO v_prev_pp
      FROM delivery_progress
     WHERE product_id   = p_product_id
       AND delivery_date = DATE_SUB(p_start_date, INTERVAL 1 DAY)
     ORDER BY id
     LIMIT 1
     FOR UPDATE;

    START TRANSACTION;

    -- 対象期間の行をロック（並列の取得・編集と衝突しないように）
    SELECT 1
      FROM delivery_progress
     WHERE product_id   = p_product_id
       AND delivery_date BETWEEN p_start_date AND p_end_date
     FOR UPDATE;

    -- 日別集計用の一時テーブル（セッション内のみ）
    DROP TEMPORARY TABLE IF EXISTS tmp_day_totals;
    CREATE TEMPORARY TABLE tmp_day_totals (
        delivery_date DATE PRIMARY KEY,
        order_total   INT NOT NULL DEFAULT 0,
        planned_total INT NOT NULL DEFAULT 0,
        shipped_total INT NOT NULL DEFAULT 0,
        day_pp        INT NULL  -- 当日分の計画進捗残 planned_progress_quantity
    ) ENGINE=Memory;

    -- 日ごとのオーダー集計
    INSERT INTO tmp_day_totals (delivery_date, order_total, planned_total, shipped_total)
    SELECT
        dp.delivery_date,
        COALESCE(SUM(dp.order_quantity),   0) AS order_total,
        COALESCE(SUM(dp.planned_quantity), 0) AS planned_total,
        COALESCE(SUM(dp.shipped_quantity), 0) AS shipped_total
    FROM delivery_progress dp
    WHERE dp.product_id = p_product_id
      AND dp.delivery_date BETWEEN p_start_date AND p_end_date
    GROUP BY dp.delivery_date
    ORDER BY dp.delivery_date;

    -- 連鎖計算：日付順に prev を更新
    BEGIN
        DECLARE done INT DEFAULT 0;
        DECLARE v_date DATE;
        DECLARE v_order INT;
        DECLARE v_plan  INT;
        DECLARE v_ship  INT;

        DECLARE cur CURSOR FOR
            SELECT delivery_date, order_total, planned_total, shipped_total
              FROM tmp_day_totals
             ORDER BY delivery_date;

        DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

        OPEN cur;
        day_loop: LOOP
            FETCH cur INTO v_date, v_order, v_plan, v_ship;
            IF done = 1 THEN
                LEAVE day_loop;
            END IF;

            IF v_ship IS NOT NULL AND v_ship > 0 THEN
                SET v_prev_pp = v_prev_pp + v_ship - v_order;
            ELSE
                SET v_prev_pp = v_prev_pp + v_plan - v_order;
            END IF;

            UPDATE tmp_day_totals
               SET day_pp = v_prev_pp
             WHERE delivery_date = v_date;
        END LOOP;
        CLOSE cur;
    END;

    -- 各日の day_pp を、その日の全レコードへ反映
    UPDATE delivery_progress dp
    JOIN tmp_day_totals t
      ON dp.delivery_date = t.delivery_date
     AND dp.product_id    = p_product_id
       SET dp.planned_progress_quantity = t.day_pp
    WHERE dp.delivery_date BETWEEN p_start_date AND p_end_date;

    COMMIT;
END$$

DELIMITER ;


-- ================================================================
-- 2. recompute_shipped_remaining_by_product
--    出荷残の再計算
-- ================================================================

DROP PROCEDURE IF EXISTS recompute_shipped_remaining_by_product;

DELIMITER $$

CREATE PROCEDURE `recompute_shipped_remaining_by_product`(
    IN p_product_id INT,
    IN p_start_date DATE,
    IN p_end_date   DATE
)
BEGIN
    DECLARE v_prev INT DEFAULT 0;

    START TRANSACTION;

    -- 初期値：開始前日の残（無ければ0）。同日複数行があっても1件だけ参照
    SELECT COALESCE(shipped_remaining_quantity, 0)
      INTO v_prev
      FROM delivery_progress
     WHERE product_id    = p_product_id
       AND delivery_date = DATE_SUB(p_start_date, INTERVAL 1 DAY)
     ORDER BY id
     LIMIT 1
     FOR UPDATE;

    -- 対象期間の行をロック
    SELECT 1
      FROM delivery_progress
     WHERE product_id   = p_product_id
       AND delivery_date BETWEEN p_start_date AND p_end_date
     FOR UPDATE;

    -- 日合算テーブル
    DROP TEMPORARY TABLE IF EXISTS tmp_day_totals_sr;
    CREATE TEMPORARY TABLE tmp_day_totals_sr (
        delivery_date DATE PRIMARY KEY,
        order_total   INT NOT NULL DEFAULT 0,
        shipped_total INT NOT NULL DEFAULT 0,
        day_sr        INT NULL  -- 当日の shipped_remaining_quantity
    ) ENGINE=Memory;

    INSERT INTO tmp_day_totals_sr (delivery_date, order_total, shipped_total)
    SELECT
        dp.delivery_date,
        COALESCE(SUM(dp.order_quantity),   0) AS order_total,
        COALESCE(SUM(dp.shipped_quantity), 0) AS shipped_total
    FROM delivery_progress dp
    WHERE dp.product_id = p_product_id
      AND dp.delivery_date BETWEEN p_start_date AND p_end_date
    GROUP BY dp.delivery_date
    ORDER BY dp.delivery_date;

    -- 連鎖計算：前日残 + shipped − order
    BEGIN
        DECLARE done INT DEFAULT 0;
        DECLARE v_date  DATE;
        DECLARE v_order INT;
        DECLARE v_ship  INT;

        DECLARE cur CURSOR FOR
            SELECT delivery_date, order_total, shipped_total
              FROM tmp_day_totals_sr
             ORDER BY delivery_date;

        DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

        OPEN cur;
        day_loop: LOOP
            FETCH cur INTO v_date, v_order, v_ship;
            IF done = 1 THEN LEAVE day_loop; END IF;

            SET v_prev = v_prev + COALESCE(v_ship,0) - COALESCE(v_order,0);

            UPDATE tmp_day_totals_sr
               SET day_sr = v_prev
             WHERE delivery_date = v_date;
        END LOOP;
        CLOSE cur;
    END;

    -- 実テーブルへ当日値を反映（同日の全レコードに同値）
    UPDATE delivery_progress dp
    JOIN tmp_day_totals_sr t
      ON dp.delivery_date = t.delivery_date
     AND dp.product_id    = p_product_id
       SET dp.shipped_remaining_quantity = t.day_sr
    WHERE dp.delivery_date BETWEEN p_start_date AND p_end_date;

    COMMIT;
END$$

DELIMITER ;


-- ================================================================
-- 確認用クエリ
-- ================================================================

-- ストアドプロシージャの一覧を確認
SHOW PROCEDURE STATUS WHERE Db = 'tiera_db';

-- 使用例
-- CALL recompute_planned_progress_by_product(1, '2025-10-01', '2025-10-31');
-- CALL recompute_shipped_remaining_by_product(1, '2025-10-01', '2025-10-31');
