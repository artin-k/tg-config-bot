from app.models import OrderKind, OrderStatus


ORDER_STATUS_LABELS = {
    OrderStatus.PENDING_PAYMENT.value: "در انتظار پرداخت",
    OrderStatus.PAID.value: "پرداخت شده",
    OrderStatus.CREATING_SERVICE.value: "در حال ساخت سرویس",
    OrderStatus.COMPLETED.value: "تکمیل شده",
    OrderStatus.EXPIRED.value: "منقضی شده",
    OrderStatus.CANCELLED.value: "لغو شده",
    OrderStatus.FAILED.value: "ناموفق",
    OrderStatus.PENDING_USERNAME.value: "در انتظار نام کاربری",
}

ORDER_KIND_LABELS = {
    OrderKind.PURCHASE.value: "خرید جدید",
    OrderKind.RENEWAL.value: "تمدید",
}


def order_status_label(status: str) -> str:
    return ORDER_STATUS_LABELS.get(status, status)


def order_kind_label(kind: str | None) -> str:
    return ORDER_KIND_LABELS.get(kind or OrderKind.PURCHASE.value, "خرید جدید")
