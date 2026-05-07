-- UP
CREATE TABLE t_fixture_pricing_item (
  item_id BIGINT PRIMARY KEY,
  item_name VARCHAR(64) NOT NULL
);

-- DOWN
DROP TABLE IF EXISTS t_fixture_pricing_item;
