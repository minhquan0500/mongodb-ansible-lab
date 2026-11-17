# Câu 1 — MongoDB 6.0 với Ansible và Docker

**Kết quả thực tế:** đã triển khai và kiểm tra thành công 5 node MongoDB 6.0.26, 1 PRIMARY + 4 SECONDARY; chạy lại deployment changed=0, không recreate/restart container. Kiểm thử dùng profile tiết kiệm đĩa trên Debian 13 vì host Docker vfs chỉ có 7,9 GB. Cấu hình mặc định dùng image chính thức trên Ubuntu chưa được chạy end-to-end ở đây. Xem TEST_RESULTS.md và logs/. Chỉ thực hiện Câu 1.

## Kiến trúc

```text
Ubuntu host 8 GB → Ansible localhost → Docker Compose mongodb-ansible-lab
 └─ rsnet (internal, không publish port)
     ├─ mongo1:27017 → data1 + config1
     ├─ mongo2:27017 → data2 + config2
     ├─ mongo3:27017 → data3 + config3
     ├─ mongo4:27017 → data4 + config4
     └─ mongo5:27017 → data5 + config5
           rs0: 1 PRIMARY + 4 SECONDARY
```

Cả 5 node giữ dữ liệu, mỗi node 1 vote; majority=3. mongo1 priority=2, các node khác=1. Mỗi container giới hạn 1 GiB RAM, 1 CPU và WiredTiger cache 0,25 GiB. Tổng giới hạn RAM 5 GiB, dành phần còn lại cho host. Một host chỉ mô phỏng 5 server, không có HA khi host hỏng. Image chính thức mongo:6.0.26 cài sẵn MongoDB; CPU cần AVX. MongoDB 6.0 đã hết hỗ trợ thông thường, sử dụng theo yêu cầu lab.

## Chức năng từng file

| File | Chức năng |
|---|---|
| ansible.cfg | Inventory, roles path, remote_tmp |
| requirements.yml | Collection Docker được ghim phiên bản |
| docker-compose.yml | 5 node, auth, volume, mạng, RAM, readiness |
| inventory/hosts.yml | Điều phối Docker bằng Ansible localhost |
| group_vars/all.yml | Biến dự án, credential từ môi trường |
| playbooks/deploy.yml | Chạy role rồi verify |
| playbooks/verify.yml | Kiểm tra health, fail khi không đạt |
| roles/mongodb_deploy/tasks/main.yml | Preflight, key, Compose up, initiate, bootstrap user |
| scripts/cluster.py | Docker/mongosh qua stdin, bootstrap, kiểm tra từng node |
| scripts/check_cluster.sh | PASS/FAIL và exit code tương ứng |
| scripts/run_lab.sh | Chạy trọn bộ, lưu log, kiểm tra changed=0 và container không restart |
| scripts/prepare_low_disk_runtime.py | Chuẩn bị runtime dùng chung từ image chính thức cho host vfs hạn chế đĩa |
| docker-compose.low-disk.yml, low-disk-vars.yml | Profile kiểm thử tiết kiệm đĩa, tùy chọn |
| logs/ | Log thực tế |

## Dependencies trên Ubuntu

Cài Docker Engine và Compose plugin theo tài liệu chính thức Docker cho bản Ubuntu đang dùng. Cần Compose v2.18+, user truy cập được daemon (quyền Docker tương đương quản trị host). Dành 15–20 GB đĩa trống; vfs có thể cần nhiều hơn vì sao chép filesystem cho từng container.

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv openssl
cd mongodb-ansible-lab
python3 -m venv .venv
source .venv/bin/activate
pip install 'ansible-core>=2.17,<2.19'
export ANSIBLE_HOME="$PWD/.ansible"
ansible-galaxy collection install -r requirements.yml
docker version
docker compose version
ansible --version
free -h
df -h .
```

## Secret và bootstrap

Không có password mặc định. Nhập ít nhất 16 ký tự, giữ nguyên cho lần chạy sau và lưu trong password manager. Không bật set -x hoặc ghi secret vào git.

```bash
export MONGO_ADMIN_USER=labadmin
read -rsp 'MongoDB password (>=16 ký tự): ' MONGO_ADMIN_PASSWORD; echo
export MONGO_ADMIN_PASSWORD
```

Có thể thay biến password trong group_vars bằng biến mã hóa Ansible Vault rồi chạy --ask-vault-pass.

Ansible tạo key một lần ở .secrets/rs0.key, thư mục mode 0700. Container copy key vào /tmp, đặt owner mongodb, mode 0400 rồi entrypoint chính thức hạ quyền. Auth và internal keyfile bật từ đầu. Localhost exception cho phép initiate khi chưa có user; sau election, script tìm PRIMARY và tạo root user với write concern majority. Lần sau phải auth và đọc được rs.status() mới bỏ qua initiate. Không coi lỗi auth là replica set chưa tồn tại. Giữ keyfile cùng volumes, sao lưu an toàn; không sinh key mới thay key bị mất khi còn dữ liệu.

Password chuyển vào mongosh qua stdin, không nằm trên command line. Bootstrap dùng no_log và không in lỗi MongoDB thô. Người có quyền quản trị host vẫn có thể đọc environment. Lab chưa cấu hình TLS, không mở MongoDB ra Internet.

## Chạy playbook và kiểm tra

```bash
set -o pipefail
mkdir -p logs
ansible-playbook --syntax-check playbooks/deploy.yml
ansible-playbook --syntax-check playbooks/verify.yml
ansible-playbook playbooks/deploy.yml | tee logs/deploy-local.log
docker compose -p mongodb-ansible-lab ps
ansible-playbook playbooks/verify.yml | tee logs/verify-local.log
bash scripts/check_cluster.sh | tee logs/check-local.log
ansible-playbook playbooks/deploy.yml | tee logs/idempotency-local.log
```

Kết quả lần thứ hai trong profile tiết kiệm đĩa: changed=0, không tạo lại key/user/Replica Set hoặc recreate/restart container; ID và StartedAt của 5 container giữ nguyên. Không dùng Compose trực tiếp thay playbook triển khai. Không tự rs.reconfig() nếu membership hiện hữu khác mong đợi; verify phải báo lỗi.

Verify dùng authenticated rs.status(), rs.conf(), buildInfo trên từng node, yêu cầu version 6.0.x, set rs0, đúng 5 hostname, 5 data-bearing voting members, 1 PRIMARY, 4 SECONDARY và health=1. Có retry cho election/initial sync. Docker ping healthcheck chỉ phục vụ readiness.

Xem rs.status() trực tiếp, nhập password tại prompt:

```bash
docker exec -it mongo1 mongosh --host 127.0.0.1 \
  --username "$MONGO_ADMIN_USER" --authenticationDatabase admin --password
```

Trong mongosh:

```javascript
rs.status()
rs.status().members.map(m => ({name:m.name, state:m.stateStr, health:m.health}))
rs.conf().members.map(m => ({host:m.host, votes:m.votes, arbiterOnly:m.arbiterOnly || false}))
db.version()
db.hello().primary
```

PRIMARY là state 1, nhận ghi; SECONDARY là state 2, sao chép. PRIMARY có thể thay đổi sau election.

## Chụp ảnh minh chứng

Chụp dependencies và syntax-check; recap deploy; Compose ps với 5 healthy; verify PASS và danh sách 1 PRIMARY/4 SECONDARY; recap lần hai changed=0. Chỉ chụp khi thực tế đạt. Không chụp credential/environment/keyfile. Gói này có log thực tế, không có ảnh giả lập.

## Lỗi thường gặp

| Lỗi | Khắc phục |
|---|---|
| No space left on device | Tăng dung lượng, kiểm tra docker info/storage driver; không xóa volumes |
| Docker permission denied | Kiểm tra daemon/context và quyền socket |
| Tên mongo1…mongo5 đã dùng | Preflight từ chối container ngoài project; dùng môi trường trống |
| Authentication failed/timeout | Dùng đúng credential tạo lần đầu; đổi biến không tự đổi user đã lưu |
| Keyfile permission denied | Kiểm tra mount, owner mongodb, mode 0400 của bản copy |
| OOM | Kiểm tra docker stats --no-stream, RAM và workload lab |
| Không có PRIMARY | Kiểm tra DNS, cùng keyfile và ít nhất 3 voting node hoạt động |
| Version/membership sai | Verify FAIL; kiểm tra dữ liệu và image, không tự xóa volume |
| Ansible home chỉ đọc | Đặt ANSIBLE_HOME vào nơi ghi được; remote_tmp đã ở /tmp |
| Illegal instruction | Kiểm tra CPU hỗ trợ AVX |

Chỉ xem log đúng project: docker compose -p mongodb-ansible-lab logs --tail=100 mongo1. Không down -v, prune, xóa volume hoặc sửa container ngoài project. Không làm upgrade 7.0, Câu 2 hoặc Câu 3.


## Chạy trọn bộ bằng một lệnh

Sau khi cài dependencies và export credential:

```bash
bash scripts/run_lab.sh
```

Script lưu log vào logs/run-YYYYMMDD-HHMMSS/, dừng ngay nếu bất kỳ bước nào lỗi, kiểm tra health trước/sau lần deploy thứ hai và đối chiếu ID/StartedAt. Khi muốn đổi password phải đổi user trong MongoDB có kiểm soát; không chỉ đổi biến môi trường. Thiếu key nhưng còn volumes: preflight từ chối để tránh sinh key mới gây mất kết nối nội bộ.

## Profile tiết kiệm đĩa đã dùng để kiểm thử

Trên host Ubuntu đủ đĩa, dùng cấu hình mặc định phía trên. Riêng host dùng vfs rất hạn chế đĩa có thể dùng profile sau (cần Python 3.12+ cho helper):

```bash
# Chạy một lần TRƯỚC khi có container của project đang chạy.
python3 scripts/prepare_low_disk_runtime.py
export MONGO_RUNTIME_ROOT="$PWD/.runtime/rootfs"
bash scripts/run_lab.sh -e @low-disk-vars.yml
```

Helper tải đúng digest image MongoDB chính thức qua HTTPS, giải nén chương trình vào .runtime/rootfs và import một image filesystem nhỏ riêng cho lab. Binaries/libraries của cả 5 container dùng chung qua bind mount read-only; mỗi container vẫn chạy mongod riêng, volume /data/db riêng, xác thực và keyfile như bình thường. Không dùng chung data directory. Profile thêm WiredTiger log file_max=10MB để giảm journal, vẫn bật journal; không dùng tmpfs cho dữ liệu. Không sửa hoặc xóa .runtime khi container còn chạy. Không áp dụng helper lên cluster đang hoạt động. Gói ZIP không chứa binaries tải về, dữ liệu hoặc secret.

Log kiểm thử ghi đúng profile được sử dụng; không suy rộng thành chứng nhận Ubuntu hoặc image mặc định đã được chạy tại đây. Log lỗi ban đầu vẫn được giữ để truy vết. Các đường dẫn /workspace/work trong log là đường dẫn của môi trường kiểm thử, không phải đường dẫn cần hardcode trên máy bạn.
