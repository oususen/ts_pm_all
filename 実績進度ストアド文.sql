use kubota_db;
DELIMITER $$

DROP PROCEDURE IF EXISTS recompute_shipped_remaining_by_product $$
CREATE PROCEDURE recompute_shipped_remaining_by_product(
    IN p_product_id INT,
    IN p_start_date DATE,
    IN p_end_date   DATE
)
BEGIN
    DECLARE v_prev INT DEFAULT 0;

    START TRANSACTION;

    SELECT COALESCE(shipped_remaining_quantity, 0)
      INTO v_prev
      FROM delivery_progress
     WHERE product_id    = p_product_id
       AND delivery_date = DATE_SUB(p_start_date, INTERVAL 1 DAY)
     ORDER BY id
     LIMIT 1
     FOR UPDATE;

    SELECT 1
      FROM delivery_progress
     WHERE product_id   = p_product_id
       AND delivery_date BETWEEN p_start_date AND p_end_date
     FOR UPDATE;

    DROP TEMPORARY TABLE IF EXISTS tmp_day_totals_sr;
    CREATE TEMPORARY TABLE tmp_day_totals_sr (
        delivery_date DATE PRIMARY KEY,
        order_total   INT NOT NULL DEFAULT 0,
        shipped_total INT NOT NULL DEFAULT 0,
        day_sr        INT NULL
    ) ENGINE=Memory;

    INSERT INTO tmp_day_totals_sr (delivery_date, order_total, shipped_total)
    SELECT
        dp.delivery_date,
        COALESCE(SUM(dp.order_quantity),   0),
        COALESCE(SUM(dp.shipped_quantity), 0)
    FROM delivery_progress dp
    WHERE dp.product_id = p_product_id
      AND dp.delivery_date BETWEEN p_start_date AND p_end_date
    GROUP BY dp.delivery_date
    ORDER BY dp.delivery_date;

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

    UPDATE delivery_progress dp
    JOIN tmp_day_totals_sr t
      ON dp.delivery_date = t.delivery_date
     AND dp.product_id    = p_product_id
       SET dp.shipped_remaining_quantity = t.day_sr
    WHERE dp.delivery_date BETWEEN p_start_date AND p_end_date;

    COMMIT;
END $$

DELIMITER ;
show create  procedure recompute_shipped_remaining_by_product;
