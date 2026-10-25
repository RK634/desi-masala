"""Commerce API for Desi Masala. Apply migrations 001_auth.sql and 002_commerce.sql first."""
import csv
import hashlib
import io
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, HttpUrl

from database import get_connection
from email_service import send_order_status_email, send_email
from notification_service import send_whatsapp_if_enabled
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/commerce", tags=["Commerce"])
bearer = HTTPBearer(auto_error=False)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or not JWT_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Please sign in.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Your session is invalid or expired.")
    with get_connection() as conn:
        user = conn.execute("SELECT id, name, email, role FROM public.users WHERE id = %s", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    return user


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


class AddressInput(BaseModel):
    label: str = Field(default="Home", max_length=60)
    recipient_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str = Field(min_length=1, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    postal_code: str = Field(min_length=2, max_length=20)
    city: str = Field(min_length=1, max_length=100)
    country: str = Field(default="Germany", min_length=2, max_length=80)
    is_default: bool = False


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    brand: str | None = Field(default=None, max_length=100)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    image_url: str | None = None
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    is_featured: bool = False
    is_new_arrival: bool = False
    active: bool = True


class OrderStatusInput(BaseModel):
    status: Literal["PLACED", "CONFIRMED", "PACKING", "SHIPPED", "DELIVERED", "CANCELLED"]
    carrier: str | None = Field(default=None, max_length=80)
    tracking_number: str | None = Field(default=None, max_length=160)
    tracking_url: HttpUrl | None = None
    estimated_delivery: date | None = None
    note: str | None = Field(default=None, max_length=500)


class CheckoutItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class CheckoutInput(BaseModel):
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)
    warehouse_id: int = Field(gt=0)
    address_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=16, max_length=100)
    customer_note: str | None = Field(default=None, max_length=1000)
    promo_code: str | None = Field(default=None, max_length=60)


@router.get("/payment-info")
def public_manual_payment_info():
    """Public bank-transfer instructions; values come from backend environment configuration."""
    return {
        "payment_method": "MANUAL_BANK_TRANSFER",
        "account_holder": os.getenv("BANK_ACCOUNT_HOLDER", ""),
        "bank_name": os.getenv("BANK_NAME", ""),
        "iban": os.getenv("BANK_IBAN", ""),
        "bic": os.getenv("BANK_BIC", ""),
        "payment_reference_prefix": os.getenv("BANK_PAYMENT_REFERENCE_PREFIX", "Desi Masala order"),
        "configured": bool(os.getenv("BANK_ACCOUNT_HOLDER") and os.getenv("BANK_IBAN")),
    }


@router.get("/warehouses")
def list_warehouses():
    with get_connection() as conn:
        rows = conn.execute("SELECT id,name,location FROM public.warehouses ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@router.get("/products/{product_id}/related")
def related_products(product_id: int, limit: int = 8):
    limit = max(1, min(limit, 20))
    with get_connection() as conn:
        product = conn.execute("SELECT id, category FROM public.products WHERE id=%s AND active=TRUE", (product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        rows = conn.execute("""
            SELECT p.id, p.name, p.price, p.brand, p.category, p.description, p.image_url,
                   GREATEST(p.discount_percent, COALESCE(p.expiry_discount_percent,0)) AS discount_percent, p.is_featured, p.is_new_arrival,
                   COALESCE(SUM(i.quantity),0)::int AS stock_quantity
            FROM public.products p LEFT JOIN public.inventory i ON i.product_id=p.id
            WHERE p.active=TRUE AND p.id<>%s AND (p.category=%s OR p.is_featured=TRUE)
            GROUP BY p.id ORDER BY (p.category=%s) DESC, p.is_featured DESC, p.name LIMIT %s
        """, (product_id, product["category"], product["category"], limit)).fetchall()
    return [dict(r) for r in rows]


@router.get("/customer/recommendations")
def customer_recommendations(user=Depends(current_user)):
    """Recommend products from the customer's most recent order category, then featured products."""
    with get_connection() as conn:
        recent = conn.execute("""SELECT p.category FROM public.orders o JOIN public.products p ON p.id=o.product_id
            WHERE o.user_id=%s ORDER BY o.created_at DESC,o.id DESC LIMIT 1""", (user["id"],)).fetchone()
        category = recent["category"] if recent else None
        rows = conn.execute("""SELECT p.id,p.name,p.price,p.brand,p.description,p.category,p.image_url,GREATEST(p.discount_percent, COALESCE(p.expiry_discount_percent,0)) AS discount_percent,
            p.is_featured,p.is_new_arrival,COALESCE(SUM(i.quantity),0)::int AS stock_quantity
            FROM public.products p LEFT JOIN public.inventory i ON i.product_id=p.id
            WHERE p.active=TRUE AND p.id NOT IN
              (SELECT product_id FROM public.orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 5)
            GROUP BY p.id ORDER BY (p.category=%s) DESC,p.is_featured DESC,p.is_new_arrival DESC,p.name LIMIT 12""", (user["id"], category)).fetchall()
    return [dict(r) for r in rows]


class NotificationPreferencesInput(BaseModel):
    order_updates: bool = True
    back_in_stock: bool = True
    new_products: bool = False
    abandoned_cart_reminders: bool = False
    marketing_emails: bool = False
    discount_alerts: bool = False
    birthday_offers: bool = False
    expiry_alerts: bool = False
    whatsapp_enabled: bool = False
    whatsapp_number: str | None = Field(default=None, min_length=7, max_length=30)
    whatsapp_order_updates: bool = True
    whatsapp_marketing: bool = False


@router.get("/customer/notification-preferences")
def get_notification_preferences(user=Depends(current_user)):
    with get_connection() as conn:
        row = conn.execute("""INSERT INTO public.notification_preferences(user_id) VALUES (%s)
            ON CONFLICT(user_id) DO UPDATE SET user_id=EXCLUDED.user_id RETURNING *""", (user["id"],)).fetchone()
    return dict(row)


@router.put("/customer/notification-preferences")
def update_notification_preferences(data: NotificationPreferencesInput, user=Depends(current_user)):
    with get_connection() as conn:
        row = conn.execute("""INSERT INTO public.notification_preferences
            (user_id,order_updates,back_in_stock,new_products,abandoned_cart_reminders,marketing_emails,
             discount_alerts,birthday_offers,expiry_alerts,whatsapp_enabled,whatsapp_number,whatsapp_order_updates,whatsapp_marketing)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id) DO UPDATE SET order_updates=EXCLUDED.order_updates,
            back_in_stock=EXCLUDED.back_in_stock,new_products=EXCLUDED.new_products,
            abandoned_cart_reminders=EXCLUDED.abandoned_cart_reminders,marketing_emails=EXCLUDED.marketing_emails,
            discount_alerts=EXCLUDED.discount_alerts,birthday_offers=EXCLUDED.birthday_offers,
            expiry_alerts=EXCLUDED.expiry_alerts,whatsapp_enabled=EXCLUDED.whatsapp_enabled,
            whatsapp_number=EXCLUDED.whatsapp_number,whatsapp_order_updates=EXCLUDED.whatsapp_order_updates,
            whatsapp_marketing=EXCLUDED.whatsapp_marketing,updated_at=CURRENT_TIMESTAMP RETURNING *""",
            (user["id"],data.order_updates,data.back_in_stock,data.new_products,data.abandoned_cart_reminders,
             data.marketing_emails,data.discount_alerts,data.birthday_offers,data.expiry_alerts,
             data.whatsapp_enabled,data.whatsapp_number.strip() if data.whatsapp_number else None,
             data.whatsapp_order_updates,data.whatsapp_marketing)).fetchone()
    return dict(row)


@router.get("/customer/addresses")
def list_addresses(user=Depends(current_user)):
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM public.customer_addresses WHERE user_id=%s ORDER BY is_default DESC, id DESC", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@router.post("/customer/addresses", status_code=201)
def add_address(data: AddressInput, user=Depends(current_user)):
    with get_connection() as conn:
        if data.is_default:
            conn.execute("UPDATE public.customer_addresses SET is_default=FALSE WHERE user_id=%s", (user["id"],))
        row = conn.execute("""INSERT INTO public.customer_addresses
            (user_id,label,recipient_name,phone,address_line1,address_line2,postal_code,city,country,is_default)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (user["id"],data.label,data.recipient_name,data.phone,data.address_line1,data.address_line2,data.postal_code,data.city,data.country,data.is_default)).fetchone()
    return dict(row)


@router.patch("/customer/addresses/{address_id}")
def update_address(address_id: int, data: AddressInput, user=Depends(current_user)):
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM public.customer_addresses WHERE id=%s AND user_id=%s", (address_id, user["id"])).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Address not found.")
        if data.is_default:
            conn.execute("UPDATE public.customer_addresses SET is_default=FALSE WHERE user_id=%s", (user["id"],))
        row = conn.execute("""UPDATE public.customer_addresses SET label=%s,recipient_name=%s,phone=%s,
            address_line1=%s,address_line2=%s,postal_code=%s,city=%s,country=%s,is_default=%s
            WHERE id=%s AND user_id=%s RETURNING *""",
            (data.label,data.recipient_name,data.phone,data.address_line1,data.address_line2,data.postal_code,data.city,data.country,data.is_default,address_id,user["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Address not found.")
    return dict(row)


@router.delete("/customer/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, user=Depends(current_user)):
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM public.customer_addresses WHERE id=%s AND user_id=%s", (address_id,user["id"]))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Address not found.")
    return None


@router.get("/customer/notifications")
def list_notifications(user=Depends(current_user)):
    with get_connection() as conn:
        rows = conn.execute("SELECT id,kind,title,message,related_product_id,read_at,created_at FROM public.notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 100", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@router.patch("/customer/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user=Depends(current_user)):
    with get_connection() as conn:
        row = conn.execute("UPDATE public.notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE id=%s AND user_id=%s RETURNING id,read_at", (notification_id,user["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return dict(row)


@router.post("/customer/notifications/read-all")
def mark_all_notifications_read(user=Depends(current_user)):
    with get_connection() as conn:
        result = conn.execute("UPDATE public.notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=%s AND read_at IS NULL", (user["id"]))
    return {"updated": result.rowcount}


@router.get("/admin/notifications")
def admin_notifications(admin=Depends(admin_user)):
    with get_connection() as conn:
        rows = conn.execute("SELECT id,kind,title,message,read_at,created_at FROM public.notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 100", (admin["id"],)).fetchall()
    return [dict(row) for row in rows]


@router.patch("/admin/notifications/{notification_id}/read")
def mark_admin_notification_read(notification_id: int, admin=Depends(admin_user)):
    with get_connection() as conn:
        row = conn.execute("UPDATE public.notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE id=%s AND user_id=%s RETURNING id,read_at", (notification_id,admin["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return dict(row)


@router.post("/customer/products/{product_id}/back-in-stock-alert", status_code=201)
def subscribe_back_in_stock(product_id: int, user=Depends(current_user)):
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM public.products WHERE id=%s AND active=TRUE", (product_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Product not found.")
        conn.execute("INSERT INTO public.product_alert_subscriptions(user_id,product_id) VALUES (%s,%s) ON CONFLICT(user_id,product_id) DO NOTHING", (user["id"],product_id))
    return {"message": "We'll notify you when this product is back in stock."}


@router.post("/checkout/discount-preview")
def discount_preview(data: CheckoutInput, user=Depends(current_user)):
    """Validate a promo code and calculate the best single discount; discounts never stack."""
    with get_connection() as conn:
        order_count = conn.execute("SELECT COUNT(*) AS n FROM public.orders WHERE user_id=%s AND status <> 'CANCELLED'", (user["id"],)).fetchone()["n"]
        lifetime_spend = conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM public.orders WHERE user_id=%s AND payment_status='PAID' AND status <> 'CANCELLED'", (user["id"],)).fetchone()["total"]
        subtotal = Decimal("0.00")
        for item in data.items:
            product = conn.execute("SELECT p.price,p.discount_percent,p.active,COALESCE(p.expiry_discount_percent,0) AS expiry_discount_percent FROM public.products p WHERE p.id=%s", (item.product_id,)).fetchone()
            if not product or not product["active"]:
                raise HTTPException(status_code=400, detail=f"Product {item.product_id} is unavailable.")
            item_price = Decimal(product["price"])
            product_discount = max(Decimal(product["discount_percent"] or 0), Decimal(product["expiry_discount_percent"] or 0))
            item_price = (item_price * (Decimal("100") - product_discount) / Decimal("100")).quantize(Decimal("0.01"))
            subtotal += item_price * item.quantity
        if order_count == 0:
            automatic_percent = Decimal("20.00")
            discount_reason = "First order discount"
        else:
            spent = Decimal(lifetime_spend or 0)
            automatic_percent = Decimal("10.00") if spent > 500 else Decimal("5.00") if spent >= 251 else Decimal("2.50") if spent >= 101 else Decimal("1.00") if spent >= 100 else Decimal("0.00")
            discount_reason = "Customer loyalty discount" if automatic_percent else "No loyalty discount yet"
        promo_percent = Decimal("0.00")
        promo_code = (data.promo_code or "").strip().upper()
        if promo_code:
            promo = conn.execute("""SELECT code,discount_percent,active,starts_at,expires_at,min_order_amount,max_redemptions
                FROM public.promo_codes WHERE UPPER(code)=UPPER(%s)""", (promo_code,)).fetchone()
            if not promo or not promo["active"]:
                raise HTTPException(status_code=400, detail="This promo code is invalid or inactive.")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if promo["starts_at"] and promo["starts_at"] > now:
                raise HTTPException(status_code=400, detail="This promo code is not active yet.")
            if promo["expires_at"] and promo["expires_at"] < now:
                raise HTTPException(status_code=400, detail="This promo code has expired.")
            if subtotal < Decimal(promo["min_order_amount"] or 0):
                raise HTTPException(status_code=400, detail=f"This code requires a minimum basket of €{Decimal(promo['min_order_amount']):.2f}.")
            if promo["max_redemptions"] is not None:
                redeemed = conn.execute("SELECT COUNT(*) AS n FROM public.promo_code_redemptions WHERE promo_code=%s", (promo["code"],)).fetchone()["n"]
                if redeemed >= promo["max_redemptions"]:
                    raise HTTPException(status_code=400, detail="This promo code has reached its redemption limit.")
            already_used = conn.execute("SELECT 1 FROM public.promo_code_redemptions WHERE user_id=%s AND UPPER(promo_code)=UPPER(%s) LIMIT 1", (user["id"], promo["code"])).fetchone()
            if already_used:
                raise HTTPException(status_code=400, detail="You have already used this promo code.")
            promo_percent = Decimal(promo["discount_percent"])
        # A single discount applies: choose the best of first-order/loyalty and promo-code discounts.
        final_percent = max(automatic_percent, promo_percent)
        discount_amount = (subtotal * final_percent / Decimal("100")).quantize(Decimal("0.01"))
        return {"subtotal": str(subtotal), "automatic_discount_percent": str(automatic_percent), "promo_discount_percent": str(promo_percent), "discount_percent": str(final_percent), "discount_amount": str(discount_amount), "total": str(max(Decimal("0"), subtotal-discount_amount)), "discount_reason": discount_reason, "promo_code": promo_code or None, "promo_applied": bool(promo_code and promo_percent >= automatic_percent)}


@router.post("/checkout", status_code=201)
def checkout(data: CheckoutInput, user=Depends(current_user)):
    """Creates order lines and decrements stock atomically; payment is confirmed manually by an administrator."""
    try:
        base_key = uuid.UUID(data.idempotency_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="idempotency_key must be a UUID.")
    order_confirmation_emails = []
    with get_connection() as conn:
        address = conn.execute("SELECT id FROM public.customer_addresses WHERE id=%s AND user_id=%s", (data.address_id,user["id"])).fetchone()
        if not address:
            raise HTTPException(status_code=400, detail="Choose a saved delivery address.")
        # Idempotent retries return the already-created order lines without consuming stock or a promo twice.
        existing_lines = []
        all_lines_exist = True
        for item in data.items:
            existing = conn.execute("SELECT id,status,amount FROM public.orders WHERE idempotency_key=%s", (uuid.uuid5(base_key, str(item.product_id)),)).fetchone()
            if not existing:
                all_lines_exist = False
                break
            existing_lines.append(dict(existing))
        if all_lines_exist:
            return {"message":"Order was already placed successfully.","orders":existing_lines,"payment_status":"PENDING","payment_method":"MANUAL"}
        # Preview inside the same transaction so submitted discount values are never trusted.
        order_count = conn.execute("SELECT COUNT(*) AS n FROM public.orders WHERE user_id=%s AND status <> 'CANCELLED'", (user["id"],)).fetchone()["n"]
        lifetime_spend = conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM public.orders WHERE user_id=%s AND payment_status='PAID' AND status <> 'CANCELLED'", (user["id"],)).fetchone()["total"]
        automatic_percent = Decimal("20.00") if order_count == 0 else (Decimal("10.00") if Decimal(lifetime_spend or 0) > 500 else Decimal("5.00") if Decimal(lifetime_spend or 0) >= 251 else Decimal("2.50") if Decimal(lifetime_spend or 0) >= 101 else Decimal("1.00") if Decimal(lifetime_spend or 0) >= 100 else Decimal("0.00"))
        promo_percent = Decimal("0.00")
        promo_code = (data.promo_code or "").strip().upper()
        if promo_code:
            promo = conn.execute("SELECT * FROM public.promo_codes WHERE UPPER(code)=UPPER(%s) FOR UPDATE", (promo_code,)).fetchone()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if not promo or not promo["active"] or (promo["starts_at"] and promo["starts_at"] > now) or (promo["expires_at"] and promo["expires_at"] < now):
                raise HTTPException(status_code=400, detail="This promo code is invalid, inactive, or expired.")
            already_used = conn.execute("SELECT 1 FROM public.promo_code_redemptions WHERE user_id=%s AND UPPER(promo_code)=UPPER(%s) LIMIT 1", (user["id"], promo["code"])).fetchone()
            if already_used:
                raise HTTPException(status_code=400, detail="You have already used this promo code.")
            if promo["max_redemptions"] is not None:
                redeemed = conn.execute("SELECT COUNT(*) AS n FROM public.promo_code_redemptions WHERE promo_code=%s", (promo["code"],)).fetchone()["n"]
                if redeemed >= promo["max_redemptions"]:
                    raise HTTPException(status_code=400, detail="This promo code has reached its redemption limit.")
            promo_percent = Decimal(promo["discount_percent"])
            promo_code = promo["code"]
        final_percent = max(automatic_percent, promo_percent)
        applied_promo_code = promo_code if promo_code and promo_percent >= automatic_percent else None
        # Calculate discounted line amounts from server-side prices before creating rows.
        line_data = []
        subtotal = Decimal("0.00")
        for item in data.items:
            stock = conn.execute("SELECT i.quantity,p.price,p.active,GREATEST(p.discount_percent,COALESCE(p.expiry_discount_percent,0)) AS discount_percent FROM public.inventory i JOIN public.products p ON p.id=i.product_id WHERE i.warehouse_id=%s AND i.product_id=%s FOR UPDATE OF i", (data.warehouse_id,item.product_id)).fetchone()
            if not stock or not stock["active"]:
                raise HTTPException(status_code=400, detail=f"Product {item.product_id} is unavailable in this warehouse.")
            if stock["quantity"] < item.quantity:
                raise HTTPException(status_code=409, detail=f"Insufficient stock for product {item.product_id}.")
            price = (Decimal(stock["price"]) * (Decimal("100") - Decimal(stock["discount_percent"] or 0)) / Decimal("100")).quantize(Decimal("0.01"))
            raw_amount = price * item.quantity
            subtotal += raw_amount
            line_data.append((item, stock, price, raw_amount))
        if promo_code and subtotal < Decimal(promo["min_order_amount"] or 0):
            raise HTTPException(status_code=400, detail=f"This code requires a minimum basket of €{Decimal(promo['min_order_amount']):.2f}.")
        created = []
        remaining_discount = (subtotal * final_percent / Decimal("100")).quantize(Decimal("0.01"))
        for index, (item, stock, effective_price, raw_amount) in enumerate(line_data):
            key = uuid.uuid5(base_key, str(item.product_id))
            existing = conn.execute("SELECT id,status,amount FROM public.orders WHERE idempotency_key=%s", (key,)).fetchone()
            if existing:
                created.append(dict(existing)); continue
            # Allocate discount proportionally to each order line; last line absorbs rounding cents.
            if index == len(line_data)-1:
                line_discount = remaining_discount
            else:
                line_discount = (raw_amount * final_percent / Decimal("100")).quantize(Decimal("0.01"))
                remaining_discount -= line_discount
            amount = max(Decimal("0.00"), raw_amount - line_discount)
            discounted_unit_price = (amount / item.quantity).quantize(Decimal("0.01"))
            row = conn.execute("""INSERT INTO public.orders
                (user_id,product_id,quantity,unit_price,amount,status,warehouse_id,idempotency_key,payment_status,customer_note,discount_percent,promo_code,subtotal_amount,discount_amount)
                VALUES (%s,%s,%s,%s,%s,'PLACED',%s,%s,'PENDING',%s,%s,%s,%s,%s) RETURNING id,status,amount""",
                (user["id"],item.product_id,item.quantity,discounted_unit_price,amount,data.warehouse_id,key,data.customer_note,final_percent,applied_promo_code,raw_amount,line_discount)).fetchone()
            conn.execute("INSERT INTO public.order_status_history(order_id,status,note,changed_by) VALUES (%s,'PLACED','Order placed by customer',%s)", (row["id"],user["id"]))
            conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'order_update','Order placed — payment pending',%s)", (user["id"], f"Order #{row['id']} was placed successfully. Payment is pending until the store confirms your bank transfer."))
            conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) SELECT id,'admin_new_order','New order received',%s FROM public.users WHERE role='admin' ON CONFLICT DO NOTHING", (f"Order #{row['id']} was placed. Amount: €{amount:.2f}. Customer: {user.get('name') or user.get('email')}.",))
            order_confirmation_emails.append({"id": row["id"], "amount": amount})
            conn.execute("UPDATE public.inventory SET quantity=quantity-%s,updated_at=CURRENT_TIMESTAMP WHERE warehouse_id=%s AND product_id=%s", (item.quantity,data.warehouse_id,item.product_id))
            remaining_to_consume = item.quantity
            batches = conn.execute("SELECT id,quantity_remaining FROM public.inventory_batches WHERE warehouse_id=%s AND product_id=%s AND quantity_remaining>0 ORDER BY expiry_date ASC NULLS LAST,received_at ASC,id ASC FOR UPDATE", (data.warehouse_id,item.product_id)).fetchall()
            for batch in batches:
                if remaining_to_consume <= 0: break
                consumed = min(remaining_to_consume, batch["quantity_remaining"])
                conn.execute("UPDATE public.inventory_batches SET quantity_remaining=quantity_remaining-%s WHERE id=%s", (consumed,batch["id"]))
                conn.execute("INSERT INTO public.order_batch_allocations(order_id,batch_id,quantity) VALUES (%s,%s,%s) ON CONFLICT(order_id,batch_id) DO UPDATE SET quantity=public.order_batch_allocations.quantity+EXCLUDED.quantity", (row["id"],batch["id"],consumed))
                remaining_to_consume -= consumed
            created.append(dict(row))
        if applied_promo_code and created:
            conn.execute("INSERT INTO public.promo_code_redemptions(promo_code,user_id,discount_percent,discount_amount,order_ids) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id,promo_code) DO NOTHING", (applied_promo_code,user["id"],promo_percent,(subtotal*promo_percent/Decimal("100")).quantize(Decimal("0.01")),[int(o["id"]) for o in created]))
    for order in order_confirmation_emails:
        bank_details = "\n".join(part for part in [f"Account holder: {os.getenv('BANK_ACCOUNT_HOLDER')}" if os.getenv("BANK_ACCOUNT_HOLDER") else "", f"Bank: {os.getenv('BANK_NAME')}" if os.getenv("BANK_NAME") else "", f"IBAN: {os.getenv('BANK_IBAN')}" if os.getenv("BANK_IBAN") else "", f"BIC: {os.getenv('BANK_BIC')}" if os.getenv("BANK_BIC") else ""] if part)
        transfer_instructions = (f"\n\nBank transfer details:\n{bank_details}\nReference: {os.getenv('BANK_PAYMENT_REFERENCE_PREFIX', 'Desi Masala order')} #{order['id']}" if bank_details else "\n\nThe store will provide bank-transfer details. Your order remains pending until payment is confirmed.")
        try:
            send_email(user["email"], f"Desi Masala order #{order['id']} placed — payment pending", f"Thank you for your order.\n\nOrder number: #{order['id']}\nAmount: €{order['amount']:.2f}\nPayment status: PENDING\nPayment method: Bank transfer{transfer_instructions}\n\nWe will update you when the store confirms receipt.")
        except Exception:
            logger.exception("Could not send order confirmation email for order %s", order["id"])
        send_whatsapp_if_enabled(user["id"], f"Desi Masala: order #{order['id']} placed. Amount €{order['amount']:.2f}. Payment is pending until the store confirms your bank transfer.", "transactional")
    return {"message":"Order placed successfully. Payment is pending manual confirmation.","orders":created,"payment_status":"PENDING","payment_method":"MANUAL","discount_percent":str(final_percent),"promo_code":applied_promo_code}


@router.get("/admin/discount-usage")
def admin_discount_usage(admin=Depends(admin_user)):
    """Show every discounted order line, including automatic first-order and loyalty discounts."""
    with get_connection() as conn:
        rows = conn.execute("""SELECT o.id,o.user_id,COALESCE(o.promo_code,CASE WHEN o.discount_percent>=20 THEN 'FIRST ORDER DISCOUNT' ELSE 'LOYALTY DISCOUNT' END) AS promo_code,
            o.discount_percent,o.discount_amount,ARRAY[o.id] AS order_ids,o.created_at,u.name AS customer_name,u.email
            FROM public.orders o JOIN public.users u ON u.id=o.user_id
            WHERE COALESCE(o.discount_amount,0)>0 OR COALESCE(o.promo_code,'')<>''
            ORDER BY o.created_at DESC LIMIT 500""").fetchall()
    return [dict(row) for row in rows]


@router.get("/customer/orders")
def customer_orders(user=Depends(current_user)):
    with get_connection() as conn:
        rows = conn.execute("""SELECT o.id,o.product_id,p.name AS product_name,o.quantity,o.unit_price,o.amount,
            o.status,o.payment_status,o.created_at,o.carrier,o.tracking_number,o.tracking_url,o.estimated_delivery,
            o.shipped_at,o.delivered_at,
            COALESCE((SELECT json_agg(json_build_object('status',h.status,'note',h.note,'created_at',h.created_at) ORDER BY h.created_at,h.id)
              FROM public.order_status_history h WHERE h.order_id=o.id),'[]'::json) AS tracking_history
            FROM public.orders o JOIN public.products p ON p.id=o.product_id
            WHERE o.user_id=%s ORDER BY o.created_at DESC,o.id DESC LIMIT 200""", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@router.get("/customer/orders/{order_id}")
def customer_order_tracking(order_id: int, user=Depends(current_user)):
    """Return tracking details only to the customer who owns this order."""
    with get_connection() as conn:
        row = conn.execute("""SELECT o.id,o.product_id,p.name AS product_name,o.quantity,o.unit_price,o.amount,
            o.status,o.payment_status,o.created_at,o.carrier,o.tracking_number,o.tracking_url,o.estimated_delivery,
            o.shipped_at,o.delivered_at,
            COALESCE((SELECT json_agg(json_build_object('status',h.status,'note',h.note,'created_at',h.created_at) ORDER BY h.created_at,h.id)
              FROM public.order_status_history h WHERE h.order_id=o.id),'[]'::json) AS tracking_history
            FROM public.orders o JOIN public.products p ON p.id=o.product_id
            WHERE o.id=%s AND o.user_id=%s""", (order_id,user["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found.")
    return dict(row)


@router.post("/customer/orders/{order_id}/cancel")
def cancel_customer_order(order_id: int, user=Depends(current_user)):
    """Customers may cancel only orders that have not entered packing/shipping."""
    with get_connection() as conn:
        row = conn.execute("""SELECT id,status,product_id,quantity,warehouse_id FROM public.orders
            WHERE id=%s AND user_id=%s FOR UPDATE""", (order_id,user["id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found.")
        if row["status"] not in ("PLACED", "CONFIRMED"):
            raise HTTPException(status_code=409, detail="This order can no longer be cancelled online. Contact support for help.")
        conn.execute("UPDATE public.orders SET status='CANCELLED' WHERE id=%s", (order_id,))
        if row["warehouse_id"] is not None:
            conn.execute("UPDATE public.inventory SET quantity=quantity+%s,updated_at=CURRENT_TIMESTAMP WHERE warehouse_id=%s AND product_id=%s", (row["quantity"],row["warehouse_id"],row["product_id"]))
        allocations = conn.execute("SELECT batch_id,quantity FROM public.order_batch_allocations WHERE order_id=%s", (order_id,)).fetchall()
        for allocation in allocations:
            conn.execute("UPDATE public.inventory_batches SET quantity_remaining=quantity_remaining+%s WHERE id=%s", (allocation["quantity"],allocation["batch_id"]))
        conn.execute("INSERT INTO public.order_status_history(order_id,status,note,changed_by) VALUES (%s,'CANCELLED','Cancelled by customer; stock returned to inventory',%s)", (order_id,user["id"]))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'order_update','Order cancelled',%s)", (user["id"],f"Your order #{order_id} was cancelled."))
    return {"message":"Order cancelled and stock restored."}


@router.get("/admin/overview")
def admin_overview(admin=Depends(admin_user)):
    with get_connection() as conn:
        low_stock = conn.execute("""SELECT p.id,p.name,COALESCE(SUM(i.quantity),0)::int AS stock_quantity
            FROM public.products p LEFT JOIN public.inventory i ON i.product_id=p.id WHERE p.active=TRUE
            GROUP BY p.id HAVING COALESCE(SUM(i.quantity),0)<=10 ORDER BY stock_quantity,p.name LIMIT 100""").fetchall()
        expiring = conn.execute("""SELECT b.id,p.name,b.quantity_remaining,b.expiry_date,b.unit_cost,w.name AS warehouse_name
            FROM public.inventory_batches b JOIN public.products p ON p.id=b.product_id JOIN public.warehouses w ON w.id=b.warehouse_id
            WHERE b.quantity_remaining>0 AND b.expiry_date IS NOT NULL AND b.expiry_date<=CURRENT_DATE+INTERVAL '30 days'
            ORDER BY b.expiry_date LIMIT 100""").fetchall()
        average_costs = conn.execute("""SELECT p.id,p.name,COALESCE(SUM(b.quantity_remaining),0)::int AS batch_quantity,
            CASE WHEN SUM(b.quantity_remaining)>0 THEN ROUND(SUM(b.quantity_remaining*b.unit_cost)/SUM(b.quantity_remaining),2) ELSE NULL END AS weighted_average_cost
            FROM public.products p LEFT JOIN public.inventory_batches b ON b.product_id=p.id AND b.quantity_remaining>0
            WHERE p.active=TRUE GROUP BY p.id,p.name ORDER BY p.name LIMIT 300""").fetchall()
        totals = conn.execute("""SELECT COUNT(*)::int AS order_count,
            COUNT(*) FILTER (WHERE status IN ('PLACED','PENDING','CONFIRMED','PACKING'))::int AS pending_orders,
            COALESCE(SUM(amount) FILTER (WHERE payment_status='PAID'),0) AS paid_revenue,
            COALESCE(SUM(amount) FILTER (WHERE payment_status='PENDING'),0) AS pending_revenue
            FROM public.orders""").fetchone()
        product_count = conn.execute("SELECT COUNT(*)::int AS count FROM public.products WHERE active=TRUE").fetchone()["count"]
        fast_selling = conn.execute("""SELECT p.id,p.name,COALESCE(SUM(o.quantity),0)::int AS units_sold
            FROM public.products p JOIN public.orders o ON o.product_id=p.id
            WHERE o.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days' AND o.status <> 'CANCELLED'
            GROUP BY p.id,p.name ORDER BY units_sold DESC,p.name LIMIT 10""").fetchall()
        most_requested = conn.execute("""SELECT p.id,p.name,COUNT(s.id)::int AS request_count,
            COALESCE((SELECT SUM(i.quantity) FROM public.inventory i WHERE i.product_id=p.id),0)::int AS stock_quantity
            FROM public.products p JOIN public.product_alert_subscriptions s ON s.product_id=p.id
            WHERE s.notified_at IS NULL AND p.active=TRUE
            GROUP BY p.id,p.name ORDER BY request_count DESC,p.name LIMIT 10""").fetchall()
    return {"products_count":product_count,"orders":dict(totals),"low_stock":[dict(r) for r in low_stock],"expiring_stock":[dict(r) for r in expiring],"average_costs":[dict(r) for r in average_costs],"fast_selling":[dict(r) for r in fast_selling],"most_requested":[dict(r) for r in most_requested]}


@router.get("/admin/analytics")
def admin_analytics(admin=Depends(admin_user)):
    """Paid sales, stock investment, and estimated gross profit/loss for admin charts."""
    with get_connection() as conn:
        daily_sales = conn.execute("""WITH days AS (
            SELECT generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, INTERVAL '1 day')::date AS day
        )
        SELECT d.day::text AS day,
               COALESCE(SUM(o.amount) FILTER (WHERE o.payment_status='PAID' AND o.status <> 'CANCELLED'),0) AS sales
        FROM days d LEFT JOIN public.orders o ON o.created_at::date=d.day
        GROUP BY d.day ORDER BY d.day""").fetchall()
        monthly_comparison = conn.execute("""WITH months AS (
            SELECT generate_series(date_trunc('month', CURRENT_DATE) - INTERVAL '5 months', date_trunc('month', CURRENT_DATE), INTERVAL '1 month')::date AS month
        ), investment AS (
            SELECT date_trunc('month', received_at)::date AS month, SUM(quantity_received * unit_cost) AS amount
            FROM public.inventory_batches GROUP BY 1
        ), sales AS (
            SELECT date_trunc('month', created_at)::date AS month, SUM(amount) AS amount
            FROM public.orders WHERE payment_status='PAID' AND status <> 'CANCELLED' GROUP BY 1
        )
        SELECT to_char(m.month,'YYYY-MM') AS month, COALESCE(i.amount,0) AS investment, COALESCE(s.amount,0) AS sales
        FROM months m LEFT JOIN investment i ON i.month=m.month LEFT JOIN sales s ON s.month=m.month ORDER BY m.month""").fetchall()
        monthly_profit_loss = conn.execute("""WITH months AS (
            SELECT generate_series(date_trunc('month', CURRENT_DATE) - INTERVAL '5 months', date_trunc('month', CURRENT_DATE), INTERVAL '1 month')::date AS month
        ), eligible_orders AS (
            SELECT o.id, o.created_at, o.amount, o.product_id, o.quantity,
                COALESCE(a.cost_amount, o.quantity * COALESCE(c.avg_cost,0)) AS cost_amount
            FROM public.orders o
            LEFT JOIN LATERAL (
                SELECT SUM(oba.quantity * b.unit_cost) AS cost_amount
                FROM public.order_batch_allocations oba JOIN public.inventory_batches b ON b.id=oba.batch_id
                WHERE oba.order_id=o.id
            ) a ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(b.quantity_received*b.unit_cost)/NULLIF(SUM(b.quantity_received),0) AS avg_cost
                FROM public.inventory_batches b WHERE b.product_id=o.product_id
            ) c ON TRUE
            WHERE o.payment_status='PAID' AND o.status <> 'CANCELLED'
        ), monthly AS (
            SELECT date_trunc('month',created_at)::date AS month, SUM(amount) AS revenue, SUM(cost_amount) AS cost
            FROM eligible_orders GROUP BY 1
        )
        SELECT to_char(m.month,'YYYY-MM') AS month, COALESCE(x.revenue,0) AS revenue,
               COALESCE(x.cost,0) AS cost, COALESCE(x.revenue,0)-COALESCE(x.cost,0) AS profit
        FROM months m LEFT JOIN monthly x ON x.month=m.month ORDER BY m.month""").fetchall()
    return {"daily_sales":[dict(r) for r in daily_sales], "monthly_comparison":[dict(r) for r in monthly_comparison], "monthly_profit_loss":[dict(r) for r in monthly_profit_loss]}


@router.get("/admin/orders")
def admin_orders(status: str | None = None, admin=Depends(admin_user)):
    with get_connection() as conn:
        if status:
            rows = conn.execute("""SELECT o.id,o.user_id,u.name AS customer_name,u.email,o.product_id,p.name AS product_name,
                o.quantity,o.unit_price,o.amount,o.status,o.payment_status,o.created_at,o.warehouse_id,o.carrier,o.tracking_number,o.tracking_url,o.estimated_delivery
                FROM public.orders o JOIN public.users u ON u.id=o.user_id JOIN public.products p ON p.id=o.product_id
                WHERE o.status=%s ORDER BY o.created_at DESC LIMIT 500""", (status,)).fetchall()
        else:
            rows = conn.execute("""SELECT o.id,o.user_id,u.name AS customer_name,u.email,o.product_id,p.name AS product_name,
                o.quantity,o.unit_price,o.amount,o.status,o.payment_status,o.created_at,o.warehouse_id,o.carrier,o.tracking_number,o.tracking_url,o.estimated_delivery
                FROM public.orders o JOIN public.users u ON u.id=o.user_id JOIN public.products p ON p.id=o.product_id
                ORDER BY o.created_at DESC LIMIT 500""").fetchall()
    return [dict(r) for r in rows]


@router.post("/admin/orders/{order_id}/confirm-payment")
def confirm_manual_payment(order_id: int, admin=Depends(admin_user)):
    """Manually confirm that payment was received outside the website."""
    with get_connection() as conn:
        order = conn.execute(
            "SELECT o.id,o.user_id,o.payment_status,o.status,u.email FROM public.orders o JOIN public.users u ON u.id=o.user_id WHERE o.id=%s FOR UPDATE OF o",
            (order_id,),
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")
        if order["status"] == "CANCELLED":
            raise HTTPException(status_code=409, detail="A cancelled order cannot be marked as paid.")
        if order["payment_status"] == "PAID":
            return {"order_id": order_id, "payment_status": "PAID", "message": "Payment was already confirmed."}
        if order["payment_status"] == "REFUNDED":
            raise HTTPException(status_code=409, detail="A refunded order cannot be marked as paid.")
        conn.execute(
            """UPDATE public.orders SET payment_status='PAID', payment_method='MANUAL',
               payment_reference=COALESCE(payment_reference,'MANUAL_CONFIRMED'),
               payment_received_at=CURRENT_TIMESTAMP, payment_received_by=%s WHERE id=%s""",
            (admin["id"], order_id),
        )
        conn.execute(
            "INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'order_update','Payment confirmed',%s)",
            (order["user_id"], f"Manual payment for order #{order_id} has been confirmed."),
        )
        conn.execute(
            "INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,entity_id,details) VALUES (%s,'confirm_manual_payment','order',%s,jsonb_build_object('payment_status','PAID','payment_method','MANUAL'))",
            (admin["id"], str(order_id)),
        )
    try:
        send_email(order["email"], f"Payment confirmed for Desi Masala order #{order_id}", f"We have confirmed receipt of your payment for order #{order_id}. Thank you for shopping with Desi Masala.")
    except Exception:
        logger.exception("Could not send payment confirmation email for order %s", order_id)
    send_whatsapp_if_enabled(order["user_id"], f"Desi Masala: payment for order #{order_id} has been confirmed.", "transactional")
    return {"order_id": order_id, "payment_status": "PAID", "payment_method": "MANUAL", "message": "Payment marked as received."}


@router.patch("/admin/orders/{order_id}/status")
def update_order_status(order_id: int, data: OrderStatusInput, admin=Depends(admin_user)):
    """Update order progress and shipment information, recording an audit timeline."""
    with get_connection() as conn:
        previous = conn.execute("SELECT o.id,o.user_id,o.status,u.email FROM public.orders o JOIN public.users u ON u.id=o.user_id WHERE o.id=%s FOR UPDATE OF o", (order_id,)).fetchone()
        if not previous:
            raise HTTPException(status_code=404, detail="Order not found.")
        if data.status == "CANCELLED" and previous["status"] not in ("CANCELLED", "PLACED", "CONFIRMED"):
            raise HTTPException(status_code=409, detail="This order has entered packing or shipping. Use the support/returns workflow instead of cancelling it.")
        if data.status == "CANCELLED" and previous["status"] in ("PLACED", "CONFIRMED"):
            stock_row = conn.execute("SELECT product_id,quantity,warehouse_id FROM public.orders WHERE id=%s", (order_id,)).fetchone()
            if stock_row["warehouse_id"] is not None:
                conn.execute("UPDATE public.inventory SET quantity=quantity+%s,updated_at=CURRENT_TIMESTAMP WHERE warehouse_id=%s AND product_id=%s", (stock_row["quantity"],stock_row["warehouse_id"],stock_row["product_id"]))
            allocations = conn.execute("SELECT batch_id,quantity FROM public.order_batch_allocations WHERE order_id=%s", (order_id,)).fetchall()
            for allocation in allocations:
                conn.execute("UPDATE public.inventory_batches SET quantity_remaining=quantity_remaining+%s WHERE id=%s", (allocation["quantity"],allocation["batch_id"]))
        row = conn.execute("""UPDATE public.orders SET status=%s,
            carrier=COALESCE(%s,carrier), tracking_number=COALESCE(%s,tracking_number),
            tracking_url=COALESCE(%s,tracking_url), estimated_delivery=COALESCE(%s,estimated_delivery),
            shipped_at=CASE WHEN %s='SHIPPED' THEN COALESCE(shipped_at,CURRENT_TIMESTAMP) ELSE shipped_at END,
            delivered_at=CASE WHEN %s='DELIVERED' THEN COALESCE(delivered_at,CURRENT_TIMESTAMP) ELSE delivered_at END
            WHERE id=%s RETURNING id,user_id,status,carrier,tracking_number,tracking_url,estimated_delivery,shipped_at,delivered_at""",
            (data.status,data.carrier,data.tracking_number,str(data.tracking_url) if data.tracking_url else None,
             data.estimated_delivery,data.status,data.status,order_id)).fetchone()
        if previous["status"] != data.status or any([data.carrier,data.tracking_number,data.tracking_url,data.estimated_delivery,data.note]):
            note = data.note or (f"Shipment updated via {data.carrier}" if data.carrier else "Order status updated by store")
            conn.execute("INSERT INTO public.order_status_history(order_id,status,note,changed_by) VALUES (%s,%s,%s,%s)", (order_id,data.status,note,admin["id"]))
            conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'order_update','Order update',%s)", (row["user_id"],f"Your order #{order_id} is now {row['status'].lower()}."))
        conn.execute("INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,entity_id,details) VALUES (%s,'update_order_tracking','order',%s,jsonb_build_object('status',%s::text,'carrier',%s::text,'tracking_number',%s::text))", (admin["id"],str(order_id),data.status,data.carrier,data.tracking_number))
    # Send only after the database transaction commits; email failure must not undo fulfilment.
    if previous["status"] != data.status:
        try:
            if data.status in ("SHIPPED", "DELIVERED"):
                send_order_status_email(previous["email"], order_id, data.status, row.get("carrier"), row.get("tracking_number"), row.get("tracking_url"), row.get("estimated_delivery"))
            else:
                send_email(previous["email"], f"Order #{order_id} status updated", f"Your Desi Masala order #{order_id} is now {data.status.lower().replace('_', ' ')}. Sign in to your account to view the latest order details.")
        except Exception:
            logger.exception("Could not send %s notification for order %s", data.status, order_id)
    if previous["status"] != data.status:
        send_whatsapp_if_enabled(row["user_id"], f"Desi Masala: order #{order_id} status updated to {data.status.lower().replace('_', ' ')}.", "transactional")
    return dict(row)


@router.get("/admin/products")
def admin_products(admin=Depends(admin_user)):
    with get_connection() as conn:
        rows = conn.execute("""SELECT p.id,p.name,p.price,p.brand,p.description,p.category,p.image_url,p.discount_percent,
            p.is_featured,p.is_new_arrival,p.active,COALESCE(p.expiry_discount_percent,0) AS expiry_discount_percent, p.expiry_discount_until,
            COALESCE(SUM(i.quantity),0)::int AS stock_quantity
            FROM public.products p LEFT JOIN public.inventory i ON i.product_id=p.id
            GROUP BY p.id ORDER BY p.name LIMIT 1000""").fetchall()
    return [dict(r) for r in rows]


@router.post("/admin/products", status_code=201)
def create_product(data: ProductInput, admin=Depends(admin_user)):
    new_product_emails = []
    new_product_whatsapp = []
    with get_connection() as conn:
        row = conn.execute("""INSERT INTO public.products(name,price,brand,description,category,image_url,discount_percent,is_featured,is_new_arrival,active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (data.name,data.price,data.brand,data.description,data.category,data.image_url,data.discount_percent,data.is_featured,data.is_new_arrival,data.active)).fetchone()
        conn.execute("INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,entity_id) VALUES (%s,'create_product','product',%s)", (admin["id"],str(row["id"])))
        if data.is_new_arrival:
            conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,related_product_id)
                SELECT u.id,'new_product','New grocery available',%s,%s FROM public.users u
                LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                WHERE u.role='customer' AND u.email_verified=TRUE AND COALESCE(np.new_products,FALSE)=TRUE""",
                (f"{data.name} is now available at Desi Masala.",row["id"]))
            new_product_emails = conn.execute("""SELECT u.email FROM public.users u
                LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                WHERE u.role='customer' AND u.email_verified=TRUE AND u.marketing_opt_in=TRUE
                  AND COALESCE(np.marketing_emails,FALSE)=TRUE""").fetchall()
            new_product_whatsapp = conn.execute("""SELECT u.id FROM public.users u
                JOIN public.notification_preferences np ON np.user_id=u.id
                WHERE u.role='customer' AND u.marketing_opt_in=TRUE AND np.new_products=TRUE
                  AND np.whatsapp_enabled=TRUE AND np.whatsapp_marketing=TRUE""").fetchall()
    for customer in new_product_emails:
        try:
            send_email(customer["email"], f"New at Desi Masala: {data.name}",
                f"A new grocery product is available: {data.name}.\nCategory: {data.category}\nPrice: €{data.price}.\nVisit the Desi Masala store to learn more.")
        except Exception:
            logger.exception("Could not send new-product email for product %s", row["id"])
    for customer in new_product_whatsapp:
        send_whatsapp_if_enabled(customer["id"], f"Desi Masala: new product available — {data.name}. Visit the store to see details.", "marketing")
    return dict(row)


@router.patch("/admin/products/{product_id}")
def update_product(product_id: int, data: ProductInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        row = conn.execute("""UPDATE public.products SET name=%s,price=%s,brand=%s,description=%s,category=%s,image_url=%s,
            discount_percent=%s,is_featured=%s,is_new_arrival=%s,active=%s WHERE id=%s RETURNING *""",
            (data.name,data.price,data.brand,data.description,data.category,data.image_url,data.discount_percent,data.is_featured,data.is_new_arrival,data.active,product_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found.")
        conn.execute("INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,entity_id) VALUES (%s,'update_product','product',%s)", (admin["id"],str(product_id)))
    return dict(row)


@router.post("/admin/stock/import-csv")
def import_stock_csv(file: UploadFile = File(...), admin=Depends(admin_user)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file. Save Excel files as CSV first.")
    try:
        text = file.file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        required = {"warehouse_id","quantity","unit_cost"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)) or not ({"product_id","product_name"} & set(reader.fieldnames)):
            raise HTTPException(status_code=400, detail="CSV headers must include warehouse_id, quantity, unit_cost, and either product_id or product_name. Optional columns: new_price, brand, category, expiry_date, supplier_reference.")
        rows = list(reader)
        if not rows or len(rows) > 5000:
            raise HTTPException(status_code=400, detail="CSV must contain between 1 and 5000 rows.")
        parsed=[]
        for n, row in enumerate(rows, start=2):
            product_id=int(row["product_id"]) if row.get("product_id", "").strip() else None
            product_name=row.get("product_name", "").strip() or None
            warehouse_id=int(row["warehouse_id"]); quantity=int(row["quantity"]); cost=Decimal(row["unit_cost"])
            if (product_id is not None and product_id<=0) or warehouse_id<=0 or quantity<0 or cost<0: raise ValueError(f"Invalid value on CSV row {n}.")
            if product_id is None and not product_name: raise ValueError(f"Provide product_id or product_name on CSV row {n}.")
            expiry=(date.fromisoformat(row["expiry_date"]) if row.get("expiry_date","").strip() else None)
            new_price = Decimal(row["new_price"]) if row.get("new_price", "").strip() else None
            if new_price is not None and new_price < 0: raise ValueError(f"Invalid new_price on CSV row {n}.")
            parsed.append((product_id,warehouse_id,quantity,cost,expiry,row.get("supplier_reference","").strip() or None,new_price,product_name,row.get("brand","").strip() or None,row.get("category","").strip() or "Other Groceries"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}")
    stock_alert_emails = []
    with get_connection() as conn:
        resolved = []
        for product_id,warehouse_id,quantity,cost,expiry,supplier,new_price,product_name,brand,category in parsed:
            if not conn.execute("SELECT id FROM public.warehouses WHERE id=%s",(warehouse_id,)).fetchone():
                raise HTTPException(status_code=400, detail=f"Warehouse {warehouse_id} does not exist; no import committed.")
            if product_id is not None:
                product = conn.execute("SELECT id FROM public.products WHERE id=%s",(product_id,)).fetchone()
                if not product:
                    raise HTTPException(status_code=400, detail=f"Product {product_id} does not exist; no import committed.")
                resolved_id = product_id
            else:
                product = conn.execute("SELECT id FROM public.products WHERE lower(name)=lower(%s) ORDER BY id LIMIT 1",(product_name,)).fetchone()
                if product:
                    resolved_id = product["id"]
                else:
                    if new_price is None:
                        raise HTTPException(status_code=400, detail=f"New product '{product_name}' requires new_price; no import committed.")
                    created = conn.execute("INSERT INTO public.products(name,price,brand,category,active) VALUES (%s,%s,%s,%s,TRUE) RETURNING id",(product_name,new_price,brand,category)).fetchone()
                    resolved_id = created["id"]
            resolved.append((resolved_id,warehouse_id,quantity,cost,expiry,supplier,new_price))
        for product_id,warehouse_id,quantity,cost,expiry,supplier,new_price in resolved:
            old_stock = conn.execute("SELECT quantity FROM public.inventory WHERE warehouse_id=%s AND product_id=%s FOR UPDATE",(warehouse_id,product_id)).fetchone()
            previous_total_stock = conn.execute("SELECT COALESCE(SUM(quantity),0)::int AS quantity FROM public.inventory WHERE product_id=%s", (product_id,)).fetchone()["quantity"]
            previous_price_row = conn.execute("SELECT price FROM public.products WHERE id=%s FOR UPDATE", (product_id,)).fetchone()
            previous_price = Decimal(previous_price_row["price"]) if previous_price_row else Decimal("0")
            conn.execute("""INSERT INTO public.inventory(warehouse_id,product_id,quantity,updated_at) VALUES (%s,%s,%s,CURRENT_TIMESTAMP)
                ON CONFLICT(warehouse_id,product_id) DO UPDATE SET quantity=public.inventory.quantity+EXCLUDED.quantity,updated_at=CURRENT_TIMESTAMP""",(warehouse_id,product_id,quantity))
            conn.execute("""INSERT INTO public.inventory_batches(warehouse_id,product_id,quantity_received,quantity_remaining,unit_cost,expiry_date,supplier_reference)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",(warehouse_id,product_id,quantity,quantity,cost,expiry,supplier))
            if new_price is not None and quantity > 0:
                # Quantity-weighted selling price: e.g. 4 units at 10 and 5 at 12 => 11.11.
                combined_quantity = previous_total_stock + quantity
                weighted_price = ((previous_price * previous_total_stock) + (new_price * quantity)) / combined_quantity if combined_quantity else new_price
                conn.execute("UPDATE public.products SET price=%s WHERE id=%s", (weighted_price.quantize(Decimal("0.01")), product_id))
            if quantity > 0 and (old_stock is None or old_stock["quantity"] == 0):
                alert_rows = conn.execute("""SELECT u.id AS user_id,u.email,p.name FROM public.product_alert_subscriptions s
                    JOIN public.products p ON p.id=s.product_id JOIN public.users u ON u.id=s.user_id
                    LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                    WHERE s.product_id=%s AND s.notified_at IS NULL AND u.email_verified=TRUE
                      AND COALESCE(np.back_in_stock,TRUE)=TRUE""", (product_id,)).fetchall()
                stock_alert_emails.extend((r["user_id"], r["email"], r["name"]) for r in alert_rows)
                conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,related_product_id)
                    SELECT s.user_id,'back_in_stock','Back in stock',p.name || ' is back in stock.',p.id
                    FROM public.product_alert_subscriptions s JOIN public.products p ON p.id=s.product_id
                    JOIN public.users u ON u.id=s.user_id LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                    WHERE s.product_id=%s AND s.notified_at IS NULL AND u.email_verified=TRUE AND COALESCE(np.back_in_stock,TRUE)=TRUE""",(product_id,))
                conn.execute("UPDATE public.product_alert_subscriptions SET notified_at=CURRENT_TIMESTAMP WHERE product_id=%s AND notified_at IS NULL",(product_id,))
        conn.execute("INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,details) VALUES (%s,'import_stock_csv','inventory',jsonb_build_object('rows',%s))",(admin["id"],len(parsed)))
    for email, product_name in stock_alert_emails:
        try:
            send_email(email, f"Back in stock: {product_name}", f"Good news! {product_name} is back in stock at Desi Masala. Visit the store to place your order.")
        except Exception:
            logger.exception("Could not send back-in-stock email for %s", product_name)
    return {"message":"Stock import completed.","rows_imported":len(parsed),"stock_alert_emails_attempted":len(stock_alert_emails),"weighted_average_cost_available":True,"selling_price_rule":"Existing product: if new_price is supplied and quantity is positive, selling price becomes the quantity-weighted average of existing stock and incoming stock. New product: new_price is its initial selling price."}
