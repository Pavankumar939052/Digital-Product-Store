from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartProductResponse,
    CartResponse,
)


router = APIRouter(
    prefix="/cart",
    tags=["Cart"]
)


def get_or_create_cart(
    db: Session,
    user_id: int
):
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id)
        .first()
    )

    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

    return cart


def build_cart_response(cart: Cart):
    items = []
    total_amount = 0.0

    for item in cart.items:
        subtotal = item.product.price * item.quantity
        total_amount += subtotal

        items.append(
            CartItemResponse(
                id=item.id,
                product=CartProductResponse(
                    id=item.product.id,
                    name=item.product.name,
                    price=item.product.price
                ),
                quantity=item.quantity,
                subtotal=subtotal
            )
        )

    return CartResponse(
        id=cart.id,
        items=items,
        total_amount=total_amount
    )


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED
)
def add_to_cart(
    item_data: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = (
        db.query(Product)
        .filter(
            Product.id == item_data.product_id,
            Product.is_active == True
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    if item_data.quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested quantity exceeds available stock"
        )

    cart = get_or_create_cart(
        db,
        current_user.id
    )

    existing_item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product.id
        )
        .first()
    )

    if existing_item:
        new_quantity = (
            existing_item.quantity +
            item_data.quantity
        )

        if new_quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested quantity exceeds available stock"
            )

        existing_item.quantity = new_quantity

    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=item_data.quantity
        )

        db.add(cart_item)

    db.commit()
    db.refresh(cart)

    return build_cart_response(cart)


@router.get(
    "",
    response_model=CartResponse
)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart = get_or_create_cart(
        db,
        current_user.id
    )

    return build_cart_response(cart)


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse
)
def update_cart_item(
    item_id: int,
    item_data: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart = get_or_create_cart(
        db,
        current_user.id
    )

    item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )

    if item_data.quantity > item.product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested quantity exceeds available stock"
        )

    item.quantity = item_data.quantity

    db.commit()
    db.refresh(cart)

    return build_cart_response(cart)


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse
)
def remove_cart_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart = get_or_create_cart(
        db,
        current_user.id
    )

    item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )

    db.delete(item)
    db.commit()
    db.refresh(cart)

    return build_cart_response(cart)


@router.delete(
    "",
    response_model=CartResponse
)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart = get_or_create_cart(
        db,
        current_user.id
    )

    for item in cart.items:
        db.delete(item)

    db.commit()
    db.refresh(cart)

    return build_cart_response(cart)