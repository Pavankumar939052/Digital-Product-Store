import stripe

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.order import Order, Payment
from app.models.user import User
from app.routers.auth import get_current_user


stripe.api_key = settings.stripe_secret_key

router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.post("/create-checkout-session")
def create_checkout_session(
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

    if order.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is not available for payment"
        )

    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found"
        )

    if payment.status == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has already been paid"
        )

    try:
        line_items = []

        for item in order.items:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": item.product_name
                    },
                    "unit_amount": int(
                        item.price * 100
                    )
                },
                "quantity": item.quantity
            })

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=(
                f"{settings.frontend_url}/orders"
                "?payment=success"
            ),
            cancel_url=(
                f"{settings.frontend_url}/cart"
                "?payment=cancelled"
            ),
            metadata={
                "order_id": str(order.id),
                "user_id": str(current_user.id)
            }
        )

        payment.stripe_session_id = checkout_session.id

        db.commit()

        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "order_id": order.id
        }

    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(exc)}"
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    payload = await request.body()

    signature = request.headers.get(
        "stripe-signature"
    )

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.stripe_webhook_secret
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload"
        )

    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature"
        )

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        order_id = session.get(
            "metadata",
            {}
        ).get("order_id")

        if order_id:
            order = (
                db.query(Order)
                .filter(
                    Order.id == int(order_id)
                )
                .first()
            )

            if order:
                order.status = "PAID"

                payment = (
                    db.query(Payment)
                    .filter(
                        Payment.order_id == order.id
                    )
                    .first()
                )

                if payment:
                    payment.status = "PAID"

                    payment.stripe_payment_intent_id = (
                        session.get("payment_intent")
                    )

                db.commit()

    elif event["type"] == "checkout.session.expired":

        session = event["data"]["object"]

        order_id = session.get(
            "metadata",
            {}
        ).get("order_id")

        if order_id:
            order = (
                db.query(Order)
                .filter(
                    Order.id == int(order_id)
                )
                .first()
            )

            if order and order.status == "PENDING":
                order.status = "CANCELLED"

                payment = (
                    db.query(Payment)
                    .filter(
                        Payment.order_id == order.id
                    )
                    .first()
                )

                if payment:
                    payment.status = "CANCELLED"

                db.commit()

    return {"received": True}