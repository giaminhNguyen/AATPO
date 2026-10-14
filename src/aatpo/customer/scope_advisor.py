"""Scope advisor: MUST/SHOULD/LATER/DROP, 'Tiết kiệm' vs 'Cân bằng'. Effort is a qualitative XS..XL size;
no monetary quote is ever invented (spec 5.4)."""
from __future__ import annotations

from dataclasses import dataclass

# (name, priority in lean, priority in balanced, note)
_F = {
    "inventory": [
        ("Danh mục hàng hóa", "MUST", "MUST", ""), ("Nhập kho", "MUST", "MUST", ""),
        ("Xuất kho", "MUST", "MUST", ""), ("Xem tồn kho hiện tại", "MUST", "MUST", ""),
        ("Cảnh báo sắp hết hàng", "LATER", "SHOULD", "Cần ngưỡng tối thiểu cho từng mặt hàng"),
        ("Báo cáo nhập – xuất theo tháng", "LATER", "SHOULD", ""),
        ("Phân quyền nhiều người dùng", "LATER", "LATER", "Chỉ cần khi có nhiều nhân viên"),
        ("Kết nối máy quét mã vạch", "DROP", "LATER", "Cần thiết bị phù hợp"),
        ("Đồng bộ lên đám mây", "DROP", "LATER", "Sẽ phát sinh phí lưu trữ định kỳ"),
    ],
    "sales": [
        ("Ghi đơn hàng", "MUST", "MUST", ""), ("Danh sách khách hàng", "MUST", "MUST", ""),
        ("Tổng doanh thu theo ngày", "MUST", "MUST", ""),
        ("In hóa đơn", "LATER", "SHOULD", ""), ("Báo cáo doanh thu theo tháng", "LATER", "SHOULD", ""),
        ("Phân quyền nhân viên", "LATER", "LATER", ""), ("Đồng bộ lên đám mây", "DROP", "LATER", "Có phí lưu trữ định kỳ"),
    ],
    "generic": [
        ("Chức năng cốt lõi bạn mô tả", "MUST", "MUST", ""), ("Lưu dữ liệu trên máy", "MUST", "MUST", ""),
        ("Màn hình tìm kiếm và lọc", "LATER", "SHOULD", ""), ("Xuất dữ liệu ra tệp", "LATER", "SHOULD", ""),
        ("Nhiều người dùng", "DROP", "LATER", ""), ("Đồng bộ lên đám mây", "DROP", "LATER", "Có phí lưu trữ định kỳ"),
    ],
    "change": [
        ("Tìm nguyên nhân và sửa đúng chỗ", "MUST", "MUST", ""), ("Kiểm tra lại bằng thử nghiệm", "MUST", "MUST", ""),
        ("Dọn dẹp mã xung quanh", "DROP", "LATER", "Không bắt buộc để sửa lỗi"),
    ],
}
_COST = {
    "lean": "Không phát sinh chi phí vận hành định kỳ: chạy trên máy của bạn.",
    "balanced": "Không phát sinh chi phí vận hành định kỳ ở phạm vi này; các mục đồng bộ đám mây (nếu làm sau) sẽ có phí lưu trữ.",
}


@dataclass(frozen=True)
class ScopeDraft:
    option_key: str
    title_vi: str
    effort: str
    cost_note: str
    features: list[tuple[str, str, str]]  # name, priority, note


def propose(domain: str, assumption: str | None = None) -> list[ScopeDraft]:
    rows = _F[domain]
    lean = ScopeDraft("lean", "Tiết kiệm", "XS" if domain == "change" else "S", _COST["lean"],
                      [(n, pl, note) for n, pl, _, note in rows])
    bal = ScopeDraft("balanced", "Cân bằng", "S" if domain == "change" else "M", _COST["balanced"],
                     [(n, pb, note) for n, _, pb, note in rows])
    return [lean, bal]
