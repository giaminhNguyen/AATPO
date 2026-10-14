"""Discovery: ONE highest-impact question per turn, each answerable with 'Tôi chưa biết, hãy đề xuất'."""
from __future__ import annotations

from aatpo.customer.text import fold


def domain_of(brief: str) -> str:
    f = fold(brief)
    if any(k in f for k in ("kho", "ton kho", "nhap xuat")):
        return "inventory"
    if any(k in f for k in ("ban hang", "don hang", "khach hang", "cua hang")):
        return "sales"
    return "generic"


QUESTIONS = {
    "inventory": ("Để làm đúng ý bạn, điều quan trọng nhất cần theo dõi trong kho là gì: "
                  "nhập – xuất hàng, số lượng tồn, hay cảnh báo sắp hết hàng? "
                  "(Bạn cũng có thể trả lời “Tôi chưa biết, hãy đề xuất”.)"),
    "sales": ("Việc quan trọng nhất bạn muốn phần mềm làm được khi bán hàng là gì: "
              "ghi đơn hàng, theo dõi khách hàng, hay báo cáo doanh thu? "
              "(Bạn cũng có thể trả lời “Tôi chưa biết, hãy đề xuất”.)"),
    "generic": ("Việc quan trọng nhất mà phần mềm này phải làm được là gì? "
                "(Bạn cũng có thể trả lời “Tôi chưa biết, hãy đề xuất”.)"),
    "change": ("Bạn có thể mô tả cụ thể hơn không: bạn thấy hiện tượng gì, ở màn hình nào, "
               "và mong muốn nó hoạt động thế nào? (Hoặc “Tôi chưa biết, hãy đề xuất”.)"),
}

DEFAULT_ASSUMPTION = {
    "inventory": "Tôi đề xuất bắt đầu với: quản lý danh mục hàng, nhập kho, xuất kho và xem tồn kho hiện tại — "
                 "đây là phần hầu hết kho nhỏ cần nhất. Đánh đổi: chưa có cảnh báo và báo cáo nâng cao ở bản đầu.",
    "sales": "Tôi đề xuất bắt đầu với: ghi đơn hàng, danh sách khách hàng và tổng doanh thu theo ngày. "
             "Đánh đổi: chưa có phân quyền nhiều nhân viên ở bản đầu.",
    "generic": "Tôi đề xuất bắt đầu với một chức năng cốt lõi dùng được ngay, lưu dữ liệu trên máy của bạn. "
               "Đánh đổi: các chức năng phụ để lại cho các bước sau.",
    "change": "Tôi sẽ kiểm tra khu vực liên quan trong dự án và đề xuất cách sửa nhỏ nhất. "
              "Đánh đổi: có thể cần hỏi thêm nếu phát hiện nhiều nguyên nhân.",
}


def question_for(kind: str, brief: str) -> tuple[str, str]:
    """-> (question text, domain key)."""
    key = "change" if kind == "change" else domain_of(brief)
    return QUESTIONS[key], key
