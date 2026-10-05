from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartProductResponse(BaseModel):
    id: int
    name: str
    price: float

    class Config:
        from_attributes = True


class CartItemResponse(BaseModel):
    id: int
    product: CartProductResponse
    quantity: int
    subtotal: float


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    total_amount: float