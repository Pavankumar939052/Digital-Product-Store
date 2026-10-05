from datetime import datetime

from pydantic import BaseModel


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    price: float
    quantity: int
    subtotal: float

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    id: int
    amount: float
    status: str
    stripe_session_id: str | None = None

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    total_amount: float
    status: str
    created_at: datetime
    items: list[OrderItemResponse]
    payment: PaymentResponse | None = None

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    page: int
    limit: int
    total: int
    total_pages: int