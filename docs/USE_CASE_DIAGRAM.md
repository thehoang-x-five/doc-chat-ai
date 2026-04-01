@startuml
title Use Case Diagram - Hệ thống RAG cho Sinh viên
left to right direction

' ==========================================
' STYLING
' ==========================================
skinparam packageStyle rectangle
skinparam usecase {
    BackgroundColor White
    BorderColor #2C3E50
    ArrowColor #2C3E50
    Shadowing false
}
skinparam actor {
    BackgroundColor #ECF0F1
    BorderColor #2C3E50
}
skinparam rectangle {
    BackgroundColor #F8F9FA
    BorderColor #BDC3C7
}

' ==========================================
' ACTORS
' ==========================================
actor "Admin\n(Quản trị viên)" as Admin
actor "Teacher\n(Giáo viên)" as Teacher
actor "Student\n(Sinh viên)" as Student
actor "System\n(AI/Worker)" as System

' ==========================================
' USE CASES
' ==========================================

rectangle "1️⃣ Authentication & User Management" {
    usecase "UC1: Đăng ký tài khoản" as UC1
    usecase "UC2: Đăng nhập Email/Pass" as UC2
    usecase "UC3: Đăng nhập Google OAuth" as UC3
    usecase "UC4: Quản lý profile" as UC4
    usecase "UC5: Đổi mật khẩu" as UC5
    usecase "UC6: Quên mật khẩu" as UC6
    
    usecase "UC10: Quản lý DS giáo viên" as UC10
    usecase "UC11: Quản lý DS sinh viên" as UC11
    usecase "UC12: Import DS từ Excel" as UC12
    usecase "UC13: Phân quyền người dùng" as UC13
}

rectangle "2️⃣ Workspace Management" {
    usecase "UC20: Tạo môn học mới" as UC20
    usecase "UC21: Gán giáo viên phụ trách" as UC21
    usecase "UC22: Gán sinh viên vào môn" as UC22
    usecase "UC23: Xem danh sách môn học" as UC23
    usecase "UC24: Cập nhật thông tin môn" as UC24
    usecase "UC25: Xóa môn học" as UC25
}

rectangle "3️⃣ Document Management" {
    usecase "UC30: Upload tài liệu (PDF/DOCX)" as UC30
    usecase "UC31: Upload tài liệu từ URL" as UC31
    usecase "UC32: Xem danh sách tài liệu" as UC32
    usecase "UC33: Tìm kiếm tài liệu" as UC33
    usecase "UC34: Phân loại Category" as UC34
    usecase "UC35: Gắn tags" as UC35
    usecase "UC36: Xóa/Update tài liệu" as UC36
    usecase "UC37: Xem chi tiết" as UC37
    usecase "UC38: Xem lịch sử phiên bản" as UC38

    ' System processes
    usecase "UC40: Parse tài liệu (Docling)" as UC40 #E8F8F5
    usecase "UC41: Chunking văn bản" as UC41 #E8F8F5
    usecase "UC42: Generate embeddings" as UC42 #E8F8F5
    usecase "UC43: Lưu Vector DB" as UC43 #E8F8F5
    usecase "UC44: Theo dõi tiến trình" as UC44 #E8F8F5
}

rectangle "4️⃣ RAG Chat System" {
    usecase "UC50: Chọn môn học" as UC50
    usecase "UC51: Tạo conversation mới" as UC51
    usecase "UC52: Gửi câu hỏi" as UC52
    usecase "UC53: Nhận câu trả lời" as UC53
    usecase "UC54: Xem trích dẫn nguồn" as UC54
    usecase "UC55: Xem lịch sử chat" as UC55
    usecase "UC56: Xóa conversation" as UC56
    usecase "UC57: Đổi tên conversation" as UC57

    ' System processes
    usecase "UC60: Detect intent" as UC60 #E8F8F5
    usecase "UC61: Vector search" as UC61 #E8F8F5
    usecase "UC62: Rerank kết quả" as UC62 #E8F8F5
    usecase "UC63: Build context" as UC63 #E8F8F5
    usecase "UC64: Call LLM API" as UC64 #E8F8F5
    usecase "UC65: Generate answer" as UC65 #E8F8F5
    usecase "UC66: Extract citations" as UC66 #E8F8F5
    usecase "UC67: Lưu message & citations" as UC67 #E8F8F5
}

rectangle "5️⃣ Quiz Generation" {
    usecase "UC70: Tạo câu hỏi thủ công" as UC70
    usecase "UC71: Yêu cầu AI tạo câu hỏi" as UC71
    usecase "UC72: Xem DS câu hỏi" as UC72
    usecase "UC73: Chỉnh sửa câu hỏi" as UC73
    usecase "UC74: Xóa câu hỏi" as UC74
    
    usecase "UC80: Làm bài trắc nghiệm" as UC80
    usecase "UC81: Xem kết quả" as UC81
    usecase "UC82: Xem đáp án" as UC82
    usecase "UC83: Yêu cầu AI tạo bài ôn" as UC83

    ' System processes
    usecase "UC90: Trích xuất content" as UC90 #E8F8F5
    usecase "UC91: LLM Gen Question" as UC91 #E8F8F5
    usecase "UC92: Lưu kết quả làm bài" as UC92 #E8F8F5
    usecase "UC93: Thống kê kết quả" as UC93 #E8F8F5
}

rectangle "6️⃣ Analytics & Monitoring" {
    usecase "UC100: Thống kê sử dụng AI" as UC100
    usecase "UC101: Lịch sử chat SV" as UC101
    usecase "UC102: Tài liệu truy cập nhiều" as UC102
    usecase "UC103: Câu hỏi phổ biến" as UC103
    usecase "UC104: Export báo cáo" as UC104
}

' ==========================================
' RELATIONS - ACTORS TO USE CASES
' ==========================================

' --- Admin ---
Admin --> UC10
Admin --> UC11
Admin --> UC12
Admin --> UC13
Admin --> UC20
Admin --> UC21
Admin --> UC22
Admin --> UC25
Admin --> UC100
Admin --> UC101
Admin --> UC104

' --- Teacher ---
Teacher --> UC1
Teacher --> UC2
Teacher --> UC3
Teacher --> UC4
Teacher --> UC5
Teacher --> UC6
Teacher --> UC23
Teacher --> UC24
Teacher --> UC30
Teacher --> UC31
Teacher --> UC32
Teacher --> UC33
Teacher --> UC34
Teacher --> UC35
Teacher --> UC36
Teacher --> UC37
Teacher --> UC38
Teacher --> UC70
Teacher --> UC71
Teacher --> UC72
Teacher --> UC73
Teacher --> UC74
Teacher --> UC100
Teacher --> UC101
Teacher --> UC102
Teacher --> UC103

' --- Student ---
Student --> UC1
Student --> UC2
Student --> UC3
Student --> UC4
Student --> UC5
Student --> UC6
Student --> UC23
Student --> UC32
Student --> UC37
Student --> UC50
Student --> UC51
Student --> UC52
Student --> UC53
Student --> UC54
Student --> UC55
Student --> UC56
Student --> UC57
Student --> UC80
Student --> UC81
Student --> UC82
Student --> UC83

' --- System Internal Triggers ---
System --> UC40
System --> UC41
System --> UC42
System --> UC43
System --> UC44
System --> UC60
System --> UC61
System --> UC62
System --> UC63
System --> UC64
System --> UC65
System --> UC66
System --> UC67
System --> UC90
System --> UC91
System --> UC92
System --> UC93

' ==========================================
' INCLUDE RELATIONSHIPS (The Logic Flow)
' ==========================================

' Document Parsing Chain
UC30 ..> UC40 : <<include>>
UC40 ..> UC41 : <<include>>
UC41 ..> UC42 : <<include>>
UC42 ..> UC43 : <<include>>

' RAG Pipeline Chain
UC52 ..> UC60 : <<include>>
UC60 ..> UC61 : <<include>>
UC61 ..> UC62 : <<include>>
UC62 ..> UC63 : <<include>>
UC63 ..> UC64 : <<include>>
UC64 ..> UC65 : <<include>>
UC65 ..> UC66 : <<include>>
UC66 ..> UC67 : <<include>>

' Quiz Generation Chain
UC71 ..> UC90 : <<include>>
UC90 ..> UC91 : <<include>>
UC83 ..> UC90 : <<include>>

' Quiz Submission
UC80 ..> UC92 : <<include>>

@enduml