-- Additive Stripe, support, and delivery-exception schema. Existing commerce data is preserved.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS stripe_checkout_session_id TEXT,
  ADD COLUMN IF NOT EXISTS payment_intent_id TEXT,
  ADD COLUMN IF NOT EXISTS refund_reference TEXT,
  ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMP;
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_stripe_checkout_session
  ON public.orders(stripe_checkout_session_id) WHERE stripe_checkout_session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_orders_payment_intent ON public.orders(payment_intent_id) WHERE payment_intent_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.stripe_webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type VARCHAR(120) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.support_tickets (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  order_id INTEGER REFERENCES public.orders(id) ON DELETE SET NULL,
  subject VARCHAR(180) NOT NULL,
  category VARCHAR(30) NOT NULL DEFAULT 'other',
  status VARCHAR(30) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_PROGRESS','WAITING_CUSTOMER','RESOLVED','CLOSED')),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_support_tickets_status_updated ON public.support_tickets(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_support_tickets_user_updated ON public.support_tickets(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.support_messages (
  id BIGSERIAL PRIMARY KEY,
  ticket_id BIGINT NOT NULL REFERENCES public.support_tickets(id) ON DELETE CASCADE,
  sender_user_id INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
  sender_role VARCHAR(20) NOT NULL CHECK (sender_role IN ('customer','admin','system')),
  message TEXT NOT NULL CHECK (length(trim(message)) > 0),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_support_messages_ticket_created ON public.support_messages(ticket_id, created_at, id);

CREATE TABLE IF NOT EXISTS public.delivery_exceptions (
  id BIGSERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  reported_by INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
  code VARCHAR(40) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED')),
  resolution TEXT,
  resolved_by INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_delivery_exceptions_status_created ON public.delivery_exceptions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_delivery_exceptions_order ON public.delivery_exceptions(order_id, created_at DESC);
