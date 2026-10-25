"""Wishlist, feedback, admin feedback triage, and birthday-offer endpoints."""
import os
import re
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from commerce import current_user, admin_user
from database import get_connection
from notification_service import send_whatsapp_if_enabled

router = APIRouter(prefix="/engagement", tags=["Customer engagement"])

class FeedbackInput(BaseModel):
    feedback_type: str = Field(default="GENERAL", pattern=r"^(GENERAL|PRODUCT|DELIVERY|FEATURE_REQUEST|COMPLAINT)$")
    order_id: int | None = Field(default=None, gt=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    subject: str = Field(min_length=3, max_length=180)
    message: str = Field(min_length=5, max_length=5000)

class FeedbackStatusInput(BaseModel):
    status: str = Field(pattern=r"^(NEW|REVIEWING|PLANNED|RESOLVED|CLOSED)$")
    admin_response: str | None = Field(default=None, max_length=5000)

@router.get('/favorites')
def favorites(user=Depends(current_user)):
    with get_connection() as conn:
        rows = conn.execute('''SELECT p.id,p.name,p.price,p.brand,p.description,p.category,p.image_url,p.discount_percent,
            COALESCE(SUM(i.quantity),0)::int AS stock_quantity, f.created_at AS favorited_at
            FROM public.customer_favorites f JOIN public.products p ON p.id=f.product_id
            LEFT JOIN public.inventory i ON i.product_id=p.id WHERE f.user_id=%s
            GROUP BY p.id,f.created_at ORDER BY f.created_at DESC''',(user['id'],)).fetchall()
    return [dict(r) for r in rows]

@router.post('/favorites/{product_id}', status_code=201)
def add_favorite(product_id: int, user=Depends(current_user)):
    with get_connection() as conn:
        if not conn.execute('SELECT id FROM public.products WHERE id=%s AND active=TRUE',(product_id,)).fetchone():
            raise HTTPException(status_code=404, detail='Product not found.')
        conn.execute('INSERT INTO public.customer_favorites(user_id,product_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',(user['id'],product_id))
    return {'message':'Product added to favorites.'}

@router.delete('/favorites/{product_id}')
def remove_favorite(product_id: int, user=Depends(current_user)):
    with get_connection() as conn:
        conn.execute('DELETE FROM public.customer_favorites WHERE user_id=%s AND product_id=%s',(user['id'],product_id))
    return {'message':'Product removed from favorites.'}

@router.post('/feedback', status_code=201)
def submit_feedback(data: FeedbackInput, user=Depends(current_user)):
    with get_connection() as conn:
        if data.order_id and not conn.execute('SELECT id FROM public.orders WHERE id=%s AND user_id=%s',(data.order_id,user['id'])).fetchone():
            raise HTTPException(status_code=404, detail='Order not found for this account.')
        row=conn.execute('''INSERT INTO public.customer_feedback(user_id,order_id,feedback_type,rating,subject,message)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,status,created_at''',
            (user['id'],data.order_id,data.feedback_type,data.rating,data.subject.strip(),data.message.strip())).fetchone()
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) SELECT id,'feedback','Feedback received','Thank you for helping us improve Desi Masala.' FROM public.users WHERE role='admin'")
    return dict(row)

@router.get('/feedback')
def my_feedback(user=Depends(current_user)):
    with get_connection() as conn:
        rows=conn.execute('SELECT id,order_id,feedback_type,rating,subject,message,status,admin_response,created_at,updated_at FROM public.customer_feedback WHERE user_id=%s ORDER BY created_at DESC',(user['id'],)).fetchall()
    return [dict(r) for r in rows]

@router.get('/admin/feedback')
def admin_feedback(admin=Depends(admin_user)):
    with get_connection() as conn:
        rows=conn.execute('''SELECT f.id,f.user_id,u.name AS customer_name,u.email,f.order_id,f.feedback_type,f.rating,
            f.subject,f.message,f.status,f.admin_response,f.created_at FROM public.customer_feedback f
            JOIN public.users u ON u.id=f.user_id ORDER BY CASE f.status WHEN 'NEW' THEN 0 WHEN 'REVIEWING' THEN 1 ELSE 2 END,f.created_at DESC LIMIT 500''').fetchall()
    return [dict(r) for r in rows]

@router.patch('/admin/feedback/{feedback_id}')
def update_feedback(feedback_id: int, data: FeedbackStatusInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        row=conn.execute('''UPDATE public.customer_feedback SET status=%s,admin_response=%s,updated_at=CURRENT_TIMESTAMP
            WHERE id=%s RETURNING id,user_id,status,admin_response''',(data.status,data.admin_response,feedback_id)).fetchone()
        if not row: raise HTTPException(status_code=404,detail='Feedback not found.')
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'feedback','Feedback updated',%s)",(row['user_id'],f"Your feedback #{feedback_id} is now {row['status'].lower()}"))
    return dict(row)

@router.get('/profile')
def profile(user=Depends(current_user)):
    with get_connection() as conn:
        row=conn.execute('SELECT id,name,email,phone,date_of_birth,email_verified,marketing_opt_in FROM public.users WHERE id=%s',(user['id'],)).fetchone()
    return dict(row)

class ProfileInput(BaseModel):
    phone: str = Field(min_length=7,max_length=30)
    date_of_birth: date | None = None
    marketing_opt_in: bool = False

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"\+?[0-9() .\-/]+", value):
            raise ValueError("Enter a valid phone number.")
        return value

@router.patch('/profile')
def update_profile(data: ProfileInput, user=Depends(current_user)):
    if data.date_of_birth and data.date_of_birth > date.today(): raise HTTPException(status_code=400,detail='Birthday cannot be in the future.')
    with get_connection() as conn:
        duplicate = conn.execute("SELECT id FROM public.users WHERE id<>%s AND regexp_replace(COALESCE(phone,''), '[^0-9]', '', 'g')=regexp_replace(%s, '[^0-9]', '', 'g') LIMIT 1", (user['id'], data.phone)).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail='This phone number is already associated with another account.')
        row=conn.execute('''UPDATE public.users SET phone=%s,date_of_birth=%s,marketing_opt_in=%s,updated_at=CURRENT_TIMESTAMP
            WHERE id=%s RETURNING id,name,email,phone,date_of_birth,email_verified,marketing_opt_in''',
            (data.phone.strip(),data.date_of_birth,data.marketing_opt_in,user['id'])).fetchone()
    return dict(row)


@router.post('/admin/run-notification-campaigns')
def run_notification_campaigns(admin=Depends(admin_user)):
    """Run birthday and near-expiry in-app campaigns once; dedupe_key prevents duplicates on retries.

    Call from a trusted scheduler daily, or manually from an authenticated admin session.
    Marketing notifications require both marketing_opt_in and the relevant category preference.
    """
    created = 0
    birthday_user_ids = []
    expiry_messages = []
    discount_messages = []
    with get_connection() as conn:
        birthdays = conn.execute("""SELECT u.id,u.name FROM public.users u
            JOIN public.notification_preferences np ON np.user_id=u.id
            WHERE u.role='customer' AND u.date_of_birth IS NOT NULL AND u.marketing_opt_in=TRUE
              AND np.birthday_offers=TRUE AND EXTRACT(MONTH FROM u.date_of_birth)=EXTRACT(MONTH FROM CURRENT_DATE)
              AND EXTRACT(DAY FROM u.date_of_birth)=EXTRACT(DAY FROM CURRENT_DATE)""").fetchall()
        for customer in birthdays:
            key = f"birthday:{customer['id']}:{date.today().year}"
            row = conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,dedupe_key)
                VALUES (%s,'birthday_offer','A birthday treat from Desi Masala',%s,%s)
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id""",
                (customer['id'],f"Happy birthday, {customer['name'] or 'from all of us'}! Check your Desi Masala account for any available birthday offer.",key)).fetchone()
            if row:
                created += 1
                birthday_user_ids.append(customer['id'])
        discounts = conn.execute("""SELECT u.id AS user_id,p.id AS product_id,p.name,p.discount_percent
            FROM public.users u JOIN public.notification_preferences np ON np.user_id=u.id
            JOIN public.products p ON p.active=TRUE AND p.discount_percent>0
            WHERE u.role='customer' AND u.marketing_opt_in=TRUE AND np.discount_alerts=TRUE
            ORDER BY p.id LIMIT 5000""").fetchall()
        for item in discounts:
            key = f"discount:{item['user_id']}:{item['product_id']}:{date.today().isoformat()}"
            row = conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,related_product_id,dedupe_key)
                VALUES (%s,'discount_offer','A Desi Masala offer',%s,%s,%s)
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id""",
                (item['user_id'],f"{item['name']} currently has a {item['discount_percent']}% discount. Visit the store to review the offer.",item['product_id'],key)).fetchone()
            if row:
                created += 1
                discount_messages.append((item['user_id'], f"Desi Masala offer: {item['name']} currently has a {item['discount_percent']}% discount."))
        expiry = conn.execute("""SELECT DISTINCT u.id AS user_id,p.id AS product_id,p.name,
                MIN(b.expiry_date) AS expiry_date, MAX(COALESCE(p.expiry_discount_percent,0)) AS discount
            FROM public.inventory_batches b JOIN public.products p ON p.id=b.product_id
            JOIN public.users u ON u.role='customer' AND u.marketing_opt_in=TRUE
            JOIN public.notification_preferences np ON np.user_id=u.id AND np.expiry_alerts=TRUE
            WHERE b.quantity_remaining>0 AND b.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+7
              AND p.active=TRUE GROUP BY u.id,p.id,p.name""").fetchall()
        for item in expiry:
            key = f"expiry:{item['user_id']}:{item['product_id']}:{item['expiry_date']}"
            pct = int(item['discount'] or 0)
            msg = f"{item['name']} has stock approaching its expiry date ({item['expiry_date']})." + (f" Current expiry discount: {pct}%." if pct else " Check the product page for current offers.")
            row = conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,related_product_id,dedupe_key)
                VALUES (%s,'expiry_alert','Expiry-related product alert',%s,%s,%s)
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id""",
                (item['user_id'],msg,item['product_id'],key)).fetchone()
            if row:
                created += 1
                expiry_messages.append((item['user_id'],msg))
    # Optional WhatsApp delivery is consent-checked and failures never roll back in-app alerts.
    for customer_id in birthday_user_ids:
        send_whatsapp_if_enabled(customer_id, "Happy birthday from Desi Masala! Sign in to see any birthday offer available to you.", "marketing")
    for customer_id, message in discount_messages:
        send_whatsapp_if_enabled(customer_id, message, "marketing")
    for customer_id, message in expiry_messages:
        send_whatsapp_if_enabled(customer_id, message, "marketing")
    return {"created_notifications": created, "birthday_notifications": len(birthday_user_ids), "discount_notifications": len(discount_messages), "expiry_notifications": len(expiry_messages)}
