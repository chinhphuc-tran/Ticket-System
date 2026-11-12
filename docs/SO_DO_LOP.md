# Sơ đồ lớp

```mermaid
classDiagram
    class User {
        <<abstract>>
        -username
        -full_name
        -email
        -phone
        -password_hash
        -salt
        +active
        +can(permission) bool
        +ticket_scope()* str
    }
    User <|-- AdminUser
    User <|-- AgentUser
    User <|-- EndUser
    class Ticket {
        -ticket_id
        -title
        -description
        -requester
        -category
        -priority
        -status
        +group_id
        +assignee
        +due_at
        +sla_state(now) str
        +processing_hours() float
        +change_status(new, actor, note)
        +assign(assignee, group, actor)
        +add_feedback(author, content, internal)
    }
    class Feedback { author; content; created_at; internal }
    class HistoryEntry { actor; action; detail; time }
    class SupportGroup { group_id; name; description; lead }
    Ticket "1" *-- "*" Feedback
    Ticket "1" *-- "*" HistoryEntry
    Ticket "*" --> "0..1" SupportGroup
    class JsonStore { +load() +save(data) +backup() +restore_latest() }
    class UserManager { +register() +create() +update() +delete() +search() }
    class GroupManager { +create() +update() +delete() }
    class TicketManager { +create() +update() +delete() +search() +assign() +change_status() +add_feedback() +import_external() }
    class AuthService { +login() +logout() +register() +change_password() }
    class ApiService { +fetch_issues() +clean_records() }
    class AppContext
    UserManager --> JsonStore
    GroupManager --> JsonStore
    TicketManager --> JsonStore
    ApiService --> JsonStore
    AuthService --> UserManager
    AppContext o-- UserManager
    AppContext o-- GroupManager
    AppContext o-- TicketManager
    AppContext o-- AuthService
    AppContext o-- ApiService
```

## Bảng mô tả lớp chính
| Lớp | Thuộc tính chính | Phương thức chính | Ghi chú OOP |
|---|---|---|---|
| User (ABC) | username, full_name, email, phone, password_hash, salt | can(), ticket_scope() | Lớp trừu tượng, property kiểm tra dữ liệu |
| AdminUser / AgentUser / EndUser | PERMISSIONS | can() (Admin ghi đè), ticket_scope() | Kế thừa, đa hình theo vai trò |
| Ticket | id, tiêu đề, mô tả, phân loại, ưu tiên, trạng thái, thời gian | sla_state(), change_status(), assign() | Đóng gói, quy trình trạng thái |
| Feedback, HistoryEntry | tác giả, nội dung, thời gian | to_dict(), from_dict() | Lớp dữ liệu |
| SupportGroup | mã, tên, mô tả | to_dict() | Lớp dữ liệu |
| JsonStore | đường dẫn, thư mục backup | load(), save(), backup(), restore_latest() | Lớp xử lý file |
| UserManager, GroupManager, TicketManager | từ điển bản ghi | CRUD, search | Lớp quản lý |
| CustomWidget: PriorityBadge, StatusBadge, SLAMeter, LabeledEntry, DateEntry | | | Kế thừa widget Tkinter |
