-- UP

CREATE TABLE t_tob_oa_office_demo_employee (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);
CREATE TABLE t_tob_oa_office_demo_org (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);
CREATE TABLE t_tob_oa_office_demo_approval (
  id varchar(64) primary key,
  status varchar(32),
  created_at datetime
);

-- DOWN

DROP TABLE t_tob_oa_office_demo_approval;
DROP TABLE t_tob_oa_office_demo_org;
DROP TABLE t_tob_oa_office_demo_employee;
