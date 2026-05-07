-- UP

CREATE TABLE PENDING_TABLE_TOB (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);
CREATE TABLE PENDING_TABLE_TOB_OA_OFFICE_DEMO (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);
CREATE TABLE PENDING_TABLE_TOB_OA_OFFICE_DEMO (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);

-- DOWN

DROP TABLE PENDING_TABLE_TOB_OA_OFFICE_DEMO;
DROP TABLE PENDING_TABLE_TOB_OA_OFFICE_DEMO;
DROP TABLE PENDING_TABLE_TOB;
