CREATE TABLE t_tob_pricing_plan (
    pricing_id varchar(64) not null,
    pricing_name varchar(128) not null,
    product_line_code varchar(64) not null,
    pricing_type varchar(32) not null,
    status varchar(16) not null,
    effective_time datetime null
);

CREATE TABLE t_tob_pricing_item (
    pricing_id varchar(64) not null,
    pricing_name varchar(128) not null,
    product_line_code varchar(64) not null,
    pricing_type varchar(32) not null,
    status varchar(16) not null,
    effective_time datetime null
);

CREATE TABLE t_order_pricing_relation (
    pricing_id varchar(64) not null,
    pricing_name varchar(128) not null,
    product_line_code varchar(64) not null,
    pricing_type varchar(32) not null,
    status varchar(16) not null,
    effective_time datetime null
);

CREATE INDEX idx_pricing_product_line_status
    ON t_tob_pricing_plan (product_line_code, status);

CREATE UNIQUE INDEX uk_pricing_name_product_line
    ON t_tob_pricing_plan (pricing_name, product_line_code);
