"""Sinh dữ liệu ticket mẫu bằng module random (có thể tái lập bằng seed)."""
import random
from datetime import datetime, timedelta
from typing import List, Optional

import config
from models.feedback import Feedback
from models.ticket import HistoryEntry, Ticket
from models.user import User
from services.group_manager import GroupManager
from services.ticket_manager import TicketManager
from services.user_manager import UserManager

# (tiêu đề, mô tả, phân loại)
TEMPLATES = [
    ("Không kết nối được Wi-Fi tại tầng {n}", "Laptop báo kết nối giới hạn, thử quên mạng và nối lại vẫn lỗi.", "Mạng"),
    ("VPN thường xuyên bị ngắt kết nối", "VPN công ty tự ngắt sau vài phút, ảnh hưởng truy cập hệ thống nội bộ.", "Mạng"),
    ("Mạng LAN phòng {n} chậm bất thường", "Tải tệp qua mạng nội bộ rất chậm, các máy cùng phòng đều bị.", "Mạng"),
    ("Máy in phòng {n} bị kẹt giấy", "Máy in báo kẹt giấy liên tục dù đã kiểm tra khay giấy.", "Phần cứng"),
    ("Màn hình máy tính bị nhấp nháy", "Màn hình nhấp nháy mỗi vài giây, đã thử đổi cáp HDMI nhưng không đỡ.", "Phần cứng"),
    ("Bàn phím và chuột không nhận", "Sau khi khởi động lại, bàn phím và chuột USB không hoạt động.", "Phần cứng"),
    ("Máy tính khởi động rất chậm", "Máy mất hơn mười phút mới vào được màn hình làm việc.", "Phần cứng"),
    ("Excel bị treo khi mở tệp lớn", "Mở bảng tính trên 20MB thì Excel không phản hồi và tự đóng.", "Phần mềm"),
    ("Cần cài đặt phần mềm kế toán", "Cần cài phần mềm kế toán phiên bản mới cho máy tại phòng {n}.", "Phần mềm"),
    ("Ứng dụng email báo lỗi đồng bộ", "Outlook không đồng bộ được thư mới từ sáng nay.", "Phần mềm"),
    ("Quên mật khẩu tài khoản email", "Không đăng nhập được email công ty, cần cấp lại mật khẩu.", "Tài khoản & Bảo mật"),
    ("Tài khoản bị khóa do nhập sai", "Tài khoản hệ thống nhân sự bị khóa sau nhiều lần nhập sai mật khẩu.", "Tài khoản & Bảo mật"),
    ("Nghi ngờ email lừa đảo", "Nhận được email giả mạo yêu cầu cung cấp mật khẩu, cần kiểm tra.", "Tài khoản & Bảo mật"),
    ("Đề nghị cấp quyền thư mục chung", "Cần quyền truy cập thư mục chung của phòng kinh doanh.", "Tài khoản & Bảo mật"),
    ("Hỗ trợ chuẩn bị phòng họp trực tuyến", "Cần kiểm tra micro và camera phòng họp {n} trước cuộc họp chiều nay.", "Khác"),
]
FEEDBACK_SAMPLES = [
    "Đã nhận thông tin, đang kiểm tra.", "Bạn vui lòng cho biết thêm thời điểm xảy ra lỗi.",
    "Đã thử cách khắc phục, vui lòng kiểm tra lại giúp mình.", "Sự cố đã được xử lý, cảm ơn bạn.",
    "Lỗi vẫn còn xuất hiện sau khi khởi động lại máy.",
]
PRIORITY_WEIGHTS = [("critical", 1), ("high", 3), ("medium", 5), ("low", 3)]


def generate(tickets: TicketManager, users: UserManager, groups: GroupManager,
             count: int = 40, seed: Optional[int] = None) -> int:
    """Sinh `count` ticket ngẫu nhiên trong 30 ngày gần nhất. Trả về số ticket đã thêm."""
    if count < 1 or count > 500:
        raise ValueError("Số ticket mẫu phải trong khoảng 1-500.")
    rng = random.Random(seed)
    requesters = users.ensure_sample_users()
    staff: List[User] = users.staff() or [users.list()[0]]
    group_ids = [g.group_id for g in groups.list()]
    priorities = [p for p, w in PRIORITY_WEIGHTS for _ in range(w)]
    now = datetime.now().replace(microsecond=0)

    existing = [int(t.ticket_id[2:]) for t in tickets.all_tickets()]
    next_number = max(existing) + 1 if existing else 1
    created = []
    for i in range(count):
        title_tpl, desc, category = rng.choice(TEMPLATES)
        n = rng.randint(1, 5)
        priority = rng.choice(priorities)
        requester = rng.choice(requesters)
        stage = rng.choices(["new", "in_progress", "waiting", "resolved", "closed"], weights=[2, 3, 2, 4, 3])[0]
        if stage in config.OPEN_STATUSES:
            # Ticket đang mở: tạo gần đây để có đủ trong hạn / sắp quá hạn / quá hạn
            sla = config.PRIORITY_INFO[priority]["sla_hours"]
            created_at = now - timedelta(hours=rng.uniform(0.1, 1.3) * sla)
        else:
            created_at = now - timedelta(minutes=rng.randint(30, 30 * 24 * 60))
        created_at = created_at.replace(microsecond=0)
        ticket = Ticket(f"TK{next_number + i:06d}", title_tpl.format(n=n), desc.format(n=n),
                        requester.username, category, priority,
                        group_id=config.CATEGORY_DEFAULT_GROUP.get(category, rng.choice(group_ids)),
                        created_at=created_at, source="sample")
        ticket.history.append(_entry(requester.username, "Tạo ticket", f"Ưu tiên {ticket.priority_label}", created_at))

        # Tiến triển ngẫu nhiên của ticket theo quy trình
        agent = rng.choice(staff)
        path = {"new": [], "in_progress": ["in_progress"], "waiting": ["in_progress", "waiting"],
                "resolved": ["in_progress", "resolved"], "closed": ["in_progress", "resolved", "closed"]}[stage]
        moment = created_at
        if path:
            ticket.assignee = agent.username
            ticket.history.append(_entry(agent.username, "Phân công", f"Người xử lý: {agent.username}", created_at))
        for step in path:
            # Thời gian xử lý ngẫu nhiên từ 0.2 đến 1.6 lần SLA -> một phần ticket sẽ trễ SLA
            moment = min(moment + timedelta(hours=rng.uniform(0.2, 1.6) * ticket.sla_hours / len(path)), now)
            _advance(ticket, step, agent.username, moment)
        if path and rng.random() < 0.6:
            ticket.feedbacks.append(_feedback(requester.username if rng.random() < 0.4 else agent.username,
                                              rng.choice(FEEDBACK_SAMPLES), moment))
        created.append(ticket)
    return tickets.bulk_add(created)


# --- hàm phụ: ghi trạng thái mà không làm hỏng mốc thời gian mô phỏng ---------
def _entry(actor, action, detail, when):
    return HistoryEntry(actor, action, detail, when)


def _feedback(author, content, when):
    return Feedback(author, content, when)


def _advance(ticket: Ticket, new_status: str, actor: str, when: datetime) -> None:
    ticket.change_status(new_status, actor, "")
    if new_status == "resolved":
        ticket.resolved_at = when.replace(microsecond=0)
    ticket.history[-1].time = when.replace(microsecond=0)
    ticket.updated_at = when.replace(microsecond=0)
