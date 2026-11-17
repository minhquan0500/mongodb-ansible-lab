# Kết quả thực tế — 17/11/2026 (Asia/Ho_Chi_Minh)

## Kết quả cuối cùng

| Hạng mục | Kết quả, bằng chứng |
|---|---|
| Dependencies | Docker 29.9.2, Compose 2.40.3, Ansible Core 2.18.20, community.docker 4.8.2; 01-dependencies.log |
| Syntax deploy và verify | PASS; 19/20-syntax-*.log |
| Ansible deployment | PASS, failed=0; 11-shared-runtime-deploy.log |
| 5 containers | PASS, healthy; 12-containers-healthy.log |
| Replica Set | PASS trên cả 5 node; 13-verify.log, 14-check-cluster.log |
| Version | 6.0.26 trên 5 node |
| Members | Đúng 5 data-bearing members, mỗi member votes=1, không có arbiter |
| Trạng thái | mongo1 PRIMARY; mongo2–mongo5 SECONDARY tại thời điểm kiểm tra, health=1 |
| Chạy lại deployment | PASS, ok=10 changed=0 unreachable=0 failed=0; 16-idempotency.log |
| Không recreate/restart | PASS, ID và StartedAt của 5 node không đổi; 15/17/18-*.log |
| Auth | PASS: rs.status() không credential bị từ chối với code 13; 21-auth-enforcement.log |
| RAM/network/storage | PASS: 1 GiB/node, không published ports, internal network, 5 data volumes riêng; 22-runtime-security.log |

Script chạy trọn bộ bản cuối cũng kết thúc thành công: 23-full-runner.log và thư mục logs/run-20261117-014429/. Helper từ chối thay runtime khi container đang chạy: 24-helper-safety.log.

## Môi trường và giới hạn của kết quả

Host thực tế Debian 13, RAM khoảng 9,7 GiB, filesystem 7,9 GB, rootless Docker storage driver vfs. Không có Ubuntu host để kiểm thử trực tiếp.

Deployment mặc định với image mongo:6.0.26 ban đầu pull thành công nhưng thất bại khi Docker sao chép filesystem tạo 5 container vì hết đĩa (04-deploy.log). Đã giữ log lỗi, sửa remote_tmp chỉ đọc (04a), và gỡ đúng image vừa tải không có container sử dụng để lấy lại dung lượng. Không xóa volumes.

Sau đó kiểm thử thành công bằng profile tiết kiệm đĩa: cùng chương trình từ image MongoDB chính thức 6.0.26, chia sẻ chương trình read-only, 5 mongod độc lập, volumes Docker riêng có persistence, cùng auth và keyfile, WiredTiger journal file_max=10MB. Không tắt journal, không dùng tmpfs cho dữ liệu. Chỉ cấu hình profile này được kiểm thử end-to-end; cấu hình mặc định có syntax/config hợp lệ nhưng chưa được chạy end-to-end trên Ubuntu.

Không khởi động daemon thứ hai, không đổi daemon hiện có, không xóa volumes, không prune, không sửa container ngoài project. Key/password không nằm trong ZIP. Log 06/08 ghi FAIL trước khi có cluster; log 13 trở đi ghi kiểm thử sau khi triển khai thành công, không thay kết quả thất bại bằng PASS giả.
