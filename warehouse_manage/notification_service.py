"""Optional WhatsApp Cloud API delivery for Desi Masala.

No message is sent unless the customer explicitly enables WhatsApp and provides a number.
For proactive messages outside the 24-hour customer-service window, use approved templates;
this helper intentionally sends free-form text only and logs Meta rejections.
"""
import json
import logging
import os
import re
import urllib.error
import urllib.request
from database import get_connection

logger = logging.getLogger(__name__)


def send_whatsapp_if_enabled(user_id: int, message: str, category: str = "transactional") -> dict:
    """Attempt one consent-checked WhatsApp text. Never raise into checkout/order flows."""
    recipient = None
    try:
        with get_connection() as conn:
            row = conn.execute("""SELECT np.whatsapp_enabled,np.whatsapp_number,np.whatsapp_order_updates,
                    np.whatsapp_marketing,u.marketing_opt_in
                FROM public.users u LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                WHERE u.id=%s""", (user_id,)).fetchone()
        if not row or not row.get("whatsapp_enabled") or not row.get("whatsapp_number"):
            return {"status": "skipped", "reason": "WhatsApp consent or number missing"}
        if category in ("marketing", "back_in_stock"):
            if not row.get("whatsapp_marketing") or not row.get("marketing_opt_in"):
                return {"status": "skipped", "reason": "Marketing consent missing"}
            if category == "back_in_stock":
                with get_connection() as conn:
                    pref = conn.execute("SELECT back_in_stock FROM public.notification_preferences WHERE user_id=%s", (user_id,)).fetchone()
                if not pref or not pref.get("back_in_stock", True):
                    return {"status": "skipped", "reason": "Back-in-stock preference disabled"}
        elif not row.get("whatsapp_order_updates", True):
            return {"status": "skipped", "reason": "Transactional WhatsApp preference disabled"}
        recipient = re.sub(r"\D", "", row["whatsapp_number"] or "")
        if len(recipient) < 7 or len(recipient) > 15:
            return {"status": "skipped", "reason": "WhatsApp number must include a valid international country code"}
        phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
        version = os.getenv("WHATSAPP_API_VERSION", "v23.0").strip()
        if not phone_id or not token:
            _log_delivery(user_id, category, "skipped", recipient, "WhatsApp Cloud API credentials are not configured")
            return {"status": "skipped", "reason": "WhatsApp Cloud API credentials are not configured"}
        marketing = category in ("marketing", "back_in_stock")
        template_name = os.getenv("WHATSAPP_MARKETING_TEMPLATE_NAME" if marketing else "WHATSAPP_TRANSACTIONAL_TEMPLATE_NAME", "").strip()
        if template_name:
            payload_object = {"messaging_product": "whatsapp", "to": recipient, "type": "template", "template": {
                "name": template_name,
                "language": {"code": os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "de").strip()},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": message[:900]}]}]
            }}
        else:
            # Free-form text normally requires an open 24-hour customer-service window.
            payload_object = {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"preview_url": False, "body": message[:4000]}}
        payload = json.dumps(payload_object).encode("utf-8")
        request = urllib.request.Request(
            f"https://graph.facebook.com/{version}/{phone_id}/messages", data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
            message_id = ((body.get("messages") or [{}])[0]).get("id")
            _log_delivery(user_id, category, "sent", recipient, None, message_id)
            return {"status": "sent", "provider_message_id": message_id}
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")[:1000]
            _log_delivery(user_id, category, "failed", recipient, error_body)
            logger.warning("WhatsApp provider rejected message for user %s: %s", user_id, error_body)
            return {"status": "failed", "reason": error_body}
        except Exception as exc:
            _log_delivery(user_id, category, "failed", recipient, str(exc)[:1000])
            logger.exception("WhatsApp delivery failed for user %s", user_id)
            return {"status": "failed", "reason": str(exc)}
    except Exception:
        logger.exception("WhatsApp delivery setup failed for user %s", user_id)
        return {"status": "failed", "reason": "WhatsApp delivery setup failed"}


def _log_delivery(user_id: int, category: str, status: str, recipient: str | None, error: str | None = None, provider_id: str | None = None) -> None:
    try:
        with get_connection() as conn:
            conn.execute("""INSERT INTO public.notification_deliveries
                (user_id,channel,category,status,recipient,provider_message_id,error_message,sent_at)
                VALUES (%s,'whatsapp',%s,%s,%s,%s,%s,CASE WHEN %s='sent' THEN CURRENT_TIMESTAMP ELSE NULL END)""",
                (user_id,category,status,recipient,provider_id,error,status))
    except Exception:
        logger.exception("Could not write WhatsApp delivery history for user %s", user_id)
