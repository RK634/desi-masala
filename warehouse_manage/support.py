"""Customer support tickets and delivery exception handling."""
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database import get_connection
from commerce import current_user, admin_user
from email_service import send_email
from notification_service import send_whatsapp_if_enabled

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["Customer support and delivery exceptions"])

class TicketCreate(BaseModel):
    subject: str = Field(min_length=4, max_length=180)
    category: Literal["order", "delivery", "payment", "return_refund", "product", "other"] = "other"
    message: str = Field(min_length=10, max_length=5000)
    order_id: int | None = Field(default=None, gt=0)

class MessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=5000)

class TicketStatusInput(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "RESOLVED", "CLOSED"]

class DeliveryExceptionInput(BaseModel):
    code: Literal["DELAYED", "ADDRESS_ISSUE", "CUSTOMER_UNAVAILABLE", "DAMAGED", "LOST", "RETURNED_TO_SENDER", "OTHER"]
    description: str = Field(min_length=5, max_length=2000)

class ResolveExceptionInput(BaseModel):
    resolution: str = Field(min_length=5, max_length=2000)

@router.post("/tickets", status_code=201)
def create_ticket(data: TicketCreate, user=Depends(current_user)):
    with get_connection() as conn:
        if data.order_id is not None and not conn.execute("SELECT id FROM public.orders WHERE id=%s AND user_id=%s", (data.order_id,user["id"])).fetchone():
            raise HTTPException(status_code=404, detail="Order not found for this account.")
        ticket = conn.execute("INSERT INTO public.support_tickets(user_id,order_id,subject,category) VALUES (%s,%s,%s,%s) RETURNING *", (user["id"],data.order_id,data.subject.strip(),data.category)).fetchone()
        conn.execute("INSERT INTO public.support_messages(ticket_id,sender_user_id,sender_role,message) VALUES (%s,%s,'customer',%s)", (ticket["id"],user["id"],data.message.strip()))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'support','Support request received',%s)", (user["id"],f"Support ticket #{ticket['id']} was created."))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) SELECT id,'admin_support','New support ticket',%s FROM public.users WHERE role='admin'", (f"Ticket #{ticket['id']}: {data.subject.strip()}.",))
    return dict(ticket)

@router.get("/tickets")
def customer_tickets(user=Depends(current_user)):
    with get_connection() as conn:
        tickets = conn.execute("""SELECT t.id,t.order_id,t.subject,t.category,t.status,t.created_at,t.updated_at,
            COALESCE((SELECT json_agg(json_build_object('id',m.id,'sender_role',m.sender_role,'message',m.message,'created_at',m.created_at) ORDER BY m.created_at,m.id) FROM public.support_messages m WHERE m.ticket_id=t.id),'[]'::json) AS messages
            FROM public.support_tickets t WHERE t.user_id=%s ORDER BY t.updated_at DESC,t.id DESC LIMIT 100""", (user["id"],)).fetchall()
    return [dict(t) for t in tickets]

@router.post("/tickets/{ticket_id}/messages", status_code=201)
def customer_reply(ticket_id: int, data: MessageInput, user=Depends(current_user)):
    with get_connection() as conn:
        ticket = conn.execute("SELECT id,status FROM public.support_tickets WHERE id=%s AND user_id=%s FOR UPDATE", (ticket_id,user["id"])).fetchone()
        if not ticket: raise HTTPException(status_code=404, detail="Support ticket not found.")
        if ticket["status"] == "CLOSED": raise HTTPException(status_code=409, detail="This ticket is closed. Create a new ticket if you still need help.")
        conn.execute("INSERT INTO public.support_messages(ticket_id,sender_user_id,sender_role,message) VALUES (%s,%s,'customer',%s)", (ticket_id,user["id"],data.message.strip()))
        conn.execute("UPDATE public.support_tickets SET status='OPEN',updated_at=CURRENT_TIMESTAMP WHERE id=%s", (ticket_id,))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) SELECT id,'admin_support','Customer replied to support ticket',%s FROM public.users WHERE role='admin'", (f"Customer replied to ticket #{ticket_id}.",))
    return {"message":"Reply added."}

@router.get("/admin/tickets")
def admin_tickets(status: str | None = None, admin=Depends(admin_user)):
    with get_connection() as conn:
        if status:
            rows=conn.execute("""SELECT t.id,t.user_id,u.name AS customer_name,u.email,t.order_id,t.subject,t.category,t.status,t.created_at,t.updated_at,
                COALESCE((SELECT json_agg(json_build_object('id',m.id,'sender_role',m.sender_role,'message',m.message,'created_at',m.created_at) ORDER BY m.created_at,m.id) FROM public.support_messages m WHERE m.ticket_id=t.id),'[]'::json) AS messages
                FROM public.support_tickets t JOIN public.users u ON u.id=t.user_id WHERE t.status=%s ORDER BY t.updated_at DESC LIMIT 300""", (status,)).fetchall()
        else:
            rows=conn.execute("""SELECT t.id,t.user_id,u.name AS customer_name,u.email,t.order_id,t.subject,t.category,t.status,t.created_at,t.updated_at,
                COALESCE((SELECT json_agg(json_build_object('id',m.id,'sender_role',m.sender_role,'message',m.message,'created_at',m.created_at) ORDER BY m.created_at,m.id) FROM public.support_messages m WHERE m.ticket_id=t.id),'[]'::json) AS messages
                FROM public.support_tickets t JOIN public.users u ON u.id=t.user_id ORDER BY t.updated_at DESC LIMIT 300""").fetchall()
    return [dict(r) for r in rows]

@router.post("/admin/tickets/{ticket_id}/messages", status_code=201)
def admin_reply(ticket_id: int, data: MessageInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        ticket=conn.execute("SELECT t.id,t.user_id,t.status,u.email FROM public.support_tickets t JOIN public.users u ON u.id=t.user_id WHERE t.id=%s FOR UPDATE OF t", (ticket_id,)).fetchone()
        if not ticket: raise HTTPException(status_code=404, detail="Support ticket not found.")
        conn.execute("INSERT INTO public.support_messages(ticket_id,sender_user_id,sender_role,message) VALUES (%s,%s,'admin',%s)", (ticket_id,admin["id"],data.message.strip()))
        conn.execute("UPDATE public.support_tickets SET status='WAITING_CUSTOMER',updated_at=CURRENT_TIMESTAMP WHERE id=%s", (ticket_id,))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'support','Support replied',%s)", (ticket["user_id"],f"Our support team replied to ticket #{ticket_id}."))
        email=ticket["email"]
    try: send_email(email, f"Desi Masala support replied to ticket #{ticket_id}", f"Our support team replied to your request. Sign in to your account to read the reply.\n\nReply: {data.message.strip()}")
    except Exception: logger.exception("Could not email support reply for ticket %s", ticket_id)
    send_whatsapp_if_enabled(ticket["user_id"], f"Desi Masala support replied to ticket #{ticket_id}. Sign in to your account to read the reply.", "transactional")
    return {"message":"Reply sent."}

@router.patch("/admin/tickets/{ticket_id}/status")
def admin_update_ticket_status(ticket_id: int, data: TicketStatusInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        row=conn.execute("""INSERT INTO public.admin_audit_log(admin_user_id, action, entity_type, entity_id, details) VALUES (%s,'update_support_ticket','support_ticket',%s,jsonb_build_object('status', %s::text))""",(admin["id"], str(ticket_id), data.status))
        if not row: raise HTTPException(status_code=404, detail="Support ticket not found.")
        conn.execute("INSERT INTO public.admin_audit_log(admin_user_id,action,entity_type,entity_id,details) VALUES (%s,'update_support_ticket','support_ticket',%s,jsonb_build_object('status',%s))", (admin["id"],str(ticket_id),data.status))
    return dict(row)

@router.get("/admin/delivery-exceptions")
def list_delivery_exceptions(status: str = "OPEN", admin=Depends(admin_user)):
    with get_connection() as conn:
        rows=conn.execute("""SELECT e.*,o.user_id,u.email AS customer_email,u.name AS customer_name,o.status AS order_status,o.tracking_number
            FROM public.delivery_exceptions e JOIN public.orders o ON o.id=e.order_id JOIN public.users u ON u.id=o.user_id
            WHERE e.status=%s ORDER BY e.created_at DESC LIMIT 300""", (status,)).fetchall()
    return [dict(r) for r in rows]

@router.post("/admin/orders/{order_id}/delivery-exceptions", status_code=201)
def create_delivery_exception(order_id: int, data: DeliveryExceptionInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        order=conn.execute("SELECT o.id,o.user_id,u.email FROM public.orders o JOIN public.users u ON u.id=o.user_id WHERE o.id=%s FOR UPDATE OF o", (order_id,)).fetchone()
        if not order: raise HTTPException(status_code=404, detail="Order not found.")
        exception=conn.execute("INSERT INTO public.delivery_exceptions(order_id,reported_by,code,description) VALUES (%s,%s,%s,%s) RETURNING *", (order_id,admin["id"],data.code,data.description.strip())).fetchone()
        conn.execute("INSERT INTO public.order_status_history(order_id,status,note,changed_by) VALUES (%s,(SELECT status FROM public.orders WHERE id=%s),%s,%s)", (order_id,order_id,f"Delivery exception ({data.code}): {data.description.strip()}",admin["id"]))
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'delivery_exception','Delivery update',%s)", (order["user_id"],f"There is a delivery issue with order #{order_id}: {data.description.strip()}"))
        email=order["email"]
    try: send_email(email, f"Delivery update for Desi Masala order #{order_id}", f"We need to let you know about a delivery issue for order #{order_id}.\n\n{data.description.strip()}\n\nPlease sign in to your account or contact support if you need help.")
    except Exception: logger.exception("Could not email delivery exception for order %s", order_id)
    return dict(exception)

@router.post("/admin/delivery-exceptions/{exception_id}/resolve")
def resolve_delivery_exception(exception_id: int, data: ResolveExceptionInput, admin=Depends(admin_user)):
    with get_connection() as conn:
        row=conn.execute("UPDATE public.delivery_exceptions SET status='RESOLVED',resolution=%s,resolved_by=%s,resolved_at=CURRENT_TIMESTAMP WHERE id=%s AND status='OPEN' RETURNING *", (data.resolution.strip(),admin["id"],exception_id)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="Open delivery exception not found.")
        order=conn.execute("SELECT user_id FROM public.orders WHERE id=%s", (row["order_id"],)).fetchone()
        conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'delivery_exception','Delivery issue resolved',%s)", (order["user_id"],f"The delivery issue for order #{row['order_id']} has been updated: {data.resolution.strip()}"))
    return dict(row)
