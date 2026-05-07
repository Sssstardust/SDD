需求：ToB 企业 OA 办公系统

背景
面向企业内部办公场景，建设统一的 OA 平台，承载基础人事信息、组织协同、审批流转、消息通知、考勤打卡与文件共享等能力，替代分散的线下或多系统协作方式。

核心功能
- 人事：员工档案、组织架构
- 审批：请假、加班、报销、流程自定义
- 公告通知、消息推送
- 日程考勤、打卡签到
- 文件网盘、在线预览

补充说明
- 面向 ToB 企业客户，需支持多角色协同使用。
- 审批流程需要具备一定可配置性。
- 文件能力至少支持上传、下载与常见办公文件在线预览。

接口草案
- GET /api/v1/hr/employees
- POST /api/v1/hr/employees
- GET /api/v1/hr/org-tree
- GET /api/v1/approvals
- POST /api/v1/approvals/leave
- POST /api/v1/approvals/overtime
- POST /api/v1/approvals/reimburse
- POST /api/v1/approvals/process-definitions
- GET /api/v1/notices
- POST /api/v1/notices
- POST /api/v1/messages/push
- GET /api/v1/attendance/records
- POST /api/v1/attendance/check-in
- GET /api/v1/files
- POST /api/v1/files/upload
- GET /api/v1/files/{fileId}/preview
