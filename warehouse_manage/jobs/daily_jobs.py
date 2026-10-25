"""Daily birthday and near-expiry jobs. Run from warehouse_manage with: python -m jobs.daily_jobs"""
import secrets
import string
from datetime import date
from database import get_connection
from email_service import send_email


def birthday_offers(today: date):
    queued = 0
    with get_connection() as conn:
        customers = conn.execute("""SELECT id,name,email FROM public.users
            WHERE role='customer' AND email_verified=TRUE AND date_of_birth IS NOT NULL
              AND EXTRACT(MONTH FROM date_of_birth)=%s AND EXTRACT(DAY FROM date_of_birth)=%s
              AND marketing_opt_in=TRUE""", (today.month, today.day)).fetchall()
        for customer in customers:
            if conn.execute('SELECT id FROM public.birthday_offer_log WHERE user_id=%s AND offer_year=%s',(customer['id'],today.year)).fetchone():
                continue
            code = 'BIRTHDAY-' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            conn.execute('INSERT INTO public.birthday_offer_log(user_id,offer_year,offer_code) VALUES (%s,%s,%s)',(customer['id'],today.year,code))
            conn.execute("INSERT INTO public.notifications(user_id,kind,title,message) VALUES (%s,'birthday_offer','Happy birthday!',%s)",(customer['id'],f"Happy birthday, {customer['name']}! Your birthday offer code is {code}. Mention it when arranging manual payment with the store."))
            try:
                send_email(customer['email'], 'Happy birthday from Desi Masala 🎉', f"Happy birthday, {customer['name']}!\n\nThank you for shopping with Desi Masala. Your birthday offer code is {code}. Please mention it when arranging payment with the store. Contact the store for offer terms.")
            except Exception as exc:
                print(f"Birthday email failed for user {customer['id']}: {exc}")
            queued += 1
    return queued


def expiry_discounts():
    with get_connection() as conn:
        # Expiry discounts live in separate columns so the admin's normal discount is preserved.
        conn.execute("""UPDATE public.products p SET expiry_discount_percent=CASE
            WHEN EXISTS (SELECT 1 FROM public.inventory_batches b WHERE b.product_id=p.id AND b.quantity_remaining>0 AND b.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+7) THEN 20
            WHEN EXISTS (SELECT 1 FROM public.inventory_batches b WHERE b.product_id=p.id AND b.quantity_remaining>0 AND b.expiry_date BETWEEN CURRENT_DATE+8 AND CURRENT_DATE+30) THEN 10
            ELSE 0 END,
            expiry_discount_until=(SELECT MIN(b.expiry_date) FROM public.inventory_batches b WHERE b.product_id=p.id AND b.quantity_remaining>0 AND b.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+30)
            WHERE p.active=TRUE""")
        rows = conn.execute("SELECT id,name,price,expiry_discount_percent,expiry_discount_until FROM public.products WHERE active=TRUE AND expiry_discount_percent>0").fetchall()
        email_queue = []
        for product in rows:
            message=f"{product['name']} has a limited-time {product['expiry_discount_percent']}% discount because its best-before date is approaching. Offer ends {product['expiry_discount_until']}."
            email_rows = conn.execute("""SELECT u.id,u.email FROM public.users u
                LEFT JOIN public.notification_preferences np ON np.user_id=u.id
                WHERE u.role='customer' AND u.email_verified=TRUE AND u.marketing_opt_in=TRUE
                  AND COALESCE(np.marketing_emails,FALSE)=TRUE
                  AND NOT EXISTS (SELECT 1 FROM public.notifications n WHERE n.user_id=u.id AND n.related_product_id=%s AND n.kind='expiry_offer' AND n.created_at::date=CURRENT_DATE)""", (product['id'],)).fetchall()
            email_queue.extend((r['email'], product['name'], product['expiry_discount_percent'], product['expiry_discount_until']) for r in email_rows)
            conn.execute("""INSERT INTO public.notifications(user_id,kind,title,message,related_product_id)
                SELECT u.id,'expiry_offer','Limited-time grocery offer',%s,%s FROM public.users u
                WHERE u.role='customer' AND u.email_verified=TRUE AND u.marketing_opt_in=TRUE
                AND NOT EXISTS (SELECT 1 FROM public.notifications n WHERE n.user_id=u.id AND n.related_product_id=%s AND n.kind='expiry_offer' AND n.created_at::date=CURRENT_DATE)""",(message,product['id'],product['id']))
    for email, product_name, discount, expiry_date in email_queue:
        try:
            send_email(email, f"Limited-time offer: {product_name}",
                f"{product_name} has a {discount}% limited-time discount because its best-before date is approaching. The offer ends {expiry_date}. Visit Desi Masala to check availability.")
        except Exception as exc:
            print(f"Expiry offer email failed for {product_name}: {exc}")
    return len(rows)

if __name__ == '__main__':
    print({'birthday_offers_created': birthday_offers(date.today()), 'products_with_expiry_discounts': expiry_discounts()})
