import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, Payment
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.order import OrderListResponse, OrderResponse


router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED
)
def create_order(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == current_user.id)
        .first()
    )

    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create order from an empty cart"
        )

    total_amount = 0.0

    for item in cart.items:
        if not item.product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{item.product.name}' is no longer available"
            )

        if item.quantity > item.product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{item.product.name}'"
            )

        total_amount += (
            item.product.price * item.quantity
        )

    order = Order(
        user_id=current_user.id,
        total_amount=total_amount,
        status="PENDING"
    )

    db.add(order)
    db.flush()

    for item in cart.items:
        subtotal = (
            item.product.price * item.quantity
        )

        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product.id,
            product_name=item.product.name,
            price=item.product.price,
            quantity=item.quantity,
            subtotal=subtotal
        )

        db.add(order_item)

    payment = Payment(
        order_id=order.id,
        amount=total_amount,
        status="PENDING"
    )

    db.add(payment)

    for item in cart.items:
        item.product.stock -= item.quantity

    db.commit()
    db.refresh(order)

    return order


@router.get(
    "",
    response_model=OrderListResponse
)
def get_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
    )

    total = query.count()

    orders = (
        query
        .order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    total_pages = math.ceil(total / limit) if total else 0

    return {
        "items": orders,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


@router.get(
    "/{order_id}",
    response_model=OrderResponse
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return order