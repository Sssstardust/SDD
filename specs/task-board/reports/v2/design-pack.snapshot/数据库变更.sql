-- UP

ALTER TABLE t_order_pricing_relation ADD COLUMN effective_time datetime;
ALTER TABLE t_order_pricing_relation ADD COLUMN pricing_id varchar(64);
ALTER TABLE t_order_pricing_relation ADD COLUMN pricing_name varchar(128);
ALTER TABLE t_order_pricing_relation ADD COLUMN pricing_type varchar(128);
ALTER TABLE t_order_pricing_relation ADD COLUMN product_line_code varchar(128);
ALTER TABLE t_order_pricing_relation ADD COLUMN status varchar(32);
ALTER TABLE t_tob_pricing_item ADD COLUMN effective_time datetime;
ALTER TABLE t_tob_pricing_item ADD COLUMN pricing_id varchar(64);
ALTER TABLE t_tob_pricing_item ADD COLUMN pricing_name varchar(128);
ALTER TABLE t_tob_pricing_item ADD COLUMN pricing_type varchar(128);
ALTER TABLE t_tob_pricing_item ADD COLUMN product_line_code varchar(128);
ALTER TABLE t_tob_pricing_item ADD COLUMN status varchar(32);
ALTER TABLE t_tob_pricing_plan ADD COLUMN effective_time datetime;
ALTER TABLE t_tob_pricing_plan ADD COLUMN pricing_id varchar(64);
ALTER TABLE t_tob_pricing_plan ADD COLUMN pricing_name varchar(128);
ALTER TABLE t_tob_pricing_plan ADD COLUMN pricing_type varchar(128);
ALTER TABLE t_tob_pricing_plan ADD COLUMN product_line_code varchar(128);
ALTER TABLE t_tob_pricing_plan ADD COLUMN status varchar(32);
CREATE INDEX idx_ready ON t_tob_pricing_plan (pricing_name,product_line_code,status);

-- DOWN

-- ROLLBACK for t_tob_pricing_plan
ALTER TABLE t_tob_pricing_plan DROP COLUMN status;
ALTER TABLE t_tob_pricing_plan DROP COLUMN product_line_code;
ALTER TABLE t_tob_pricing_plan DROP COLUMN pricing_type;
ALTER TABLE t_tob_pricing_plan DROP COLUMN pricing_name;
ALTER TABLE t_tob_pricing_plan DROP COLUMN pricing_id;
ALTER TABLE t_tob_pricing_plan DROP COLUMN effective_time;
-- ROLLBACK for t_tob_pricing_item
ALTER TABLE t_tob_pricing_item DROP COLUMN status;
ALTER TABLE t_tob_pricing_item DROP COLUMN product_line_code;
ALTER TABLE t_tob_pricing_item DROP COLUMN pricing_type;
ALTER TABLE t_tob_pricing_item DROP COLUMN pricing_name;
ALTER TABLE t_tob_pricing_item DROP COLUMN pricing_id;
ALTER TABLE t_tob_pricing_item DROP COLUMN effective_time;
-- ROLLBACK for t_order_pricing_relation
ALTER TABLE t_order_pricing_relation DROP COLUMN status;
ALTER TABLE t_order_pricing_relation DROP COLUMN product_line_code;
ALTER TABLE t_order_pricing_relation DROP COLUMN pricing_type;
ALTER TABLE t_order_pricing_relation DROP COLUMN pricing_name;
ALTER TABLE t_order_pricing_relation DROP COLUMN pricing_id;
ALTER TABLE t_order_pricing_relation DROP COLUMN effective_time;
