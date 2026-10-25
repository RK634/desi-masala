-- Desi Masala existing-database upgrade for PostgreSQL / pgAdmin 4
-- Intended for the user's existing public.users/products/warehouses/inventory/orders schema.
-- Safe to run more than once; additive only. Does not drop/truncate existing data.
-- Run in pgAdmin 4 Query Tool against the inventory database.
BEGIN;


-- ===== Align the user's already-created email verification table =====
ALTER TABLE public.email_verification_tokens
  ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0);
CREATE INDEX IF NOT EXISTS idx_email_verification_user ON public.email_verification_tokens(user_id);

-- ===== Commerce columns and supporting tables (from 002) =====
-- Desi Masala commerce foundation. Additive migration; does not drop existing data.
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'customer',
  ADD COLUMN IF NOT EXISTS marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS category VARCHAR(100),
  ADD COLUMN IF NOT EXISTS image_url TEXT,
  ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
  ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS is_new_arrival BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS warehouse_id INTEGER REFERENCES public.warehouses(id),
  ADD COLUMN IF NOT EXISTS idempotency_key UUID,
  ADD COLUMN IF NOT EXISTS payment_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS payment_reference TEXT,
  ADD COLUMN IF NOT EXISTS customer_note TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_idempotency_key ON public.orders(idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.inventory_batches (
  id BIGSERIAL PRIMARY KEY,
  warehouse_id INTEGER NOT NULL REFERENCES public.warehouses(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  quantity_received INTEGER NOT NULL CHECK (quantity_received >= 0),
  quantity_remaining INTEGER NOT NULL CHECK (quantity_remaining >= 0),
  unit_cost NUMERIC(10,2) NOT NULL CHECK (unit_cost >= 0),
  expiry_date DATE,
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  supplier_reference TEXT
);
CREATE INDEX IF NOT EXISTS ix_inventory_batches_expiry ON public.inventory_batches(expiry_date) WHERE quantity_remaining > 0;
CREATE INDEX IF NOT EXISTS ix_inventory_batches_product ON public.inventory_batches(product_id, warehouse_id);

CREATE TABLE IF NOT EXISTS public.customer_addresses (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  label VARCHAR(60) NOT NULL DEFAULT 'Home',
  recipient_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30),
  address_line1 VARCHAR(200) NOT NULL,
  address_line2 VARCHAR(200),
  postal_code VARCHAR(20) NOT NULL,
  city VARCHAR(100) NOT NULL,
  country VARCHAR(80) NOT NULL DEFAULT 'Germany',
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_customer_addresses_user ON public.customer_addresses(user_id);

-- Store processor token/reference only. Never store raw card numbers or CVV.
CREATE TABLE IF NOT EXISTS public.customer_payment_methods (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  provider VARCHAR(40) NOT NULL,
  provider_payment_method_id TEXT NOT NULL,
  brand VARCHAR(40),
  last4 CHAR(4),
  exp_month SMALLINT CHECK (exp_month BETWEEN 1 AND 12),
  exp_year SMALLINT,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_payment_method_id)
);

CREATE TABLE IF NOT EXISTS public.notifications (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  kind VARCHAR(40) NOT NULL,
  title VARCHAR(160) NOT NULL,
  message TEXT NOT NULL,
  related_product_id INTEGER REFERENCES public.products(id) ON DELETE SET NULL,
  read_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON public.notifications(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.product_alert_subscriptions (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notified_at TIMESTAMP,
  UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS public.notification_preferences (
  user_id INTEGER PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  order_updates BOOLEAN NOT NULL DEFAULT TRUE,
  back_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
  new_products BOOLEAN NOT NULL DEFAULT FALSE,
  abandoned_cart_reminders BOOLEAN NOT NULL DEFAULT FALSE,
  marketing_emails BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.admin_audit_log (
  id BIGSERIAL PRIMARY KEY,
  admin_user_id INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(60) NOT NULL,
  entity_id TEXT,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_created ON public.admin_audit_log(created_at DESC);


-- ===== Order tracking (from 003) =====
-- Additive order tracking and status history. Existing orders are retained.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS carrier VARCHAR(80),
  ADD COLUMN IF NOT EXISTS tracking_number VARCHAR(160),
  ADD COLUMN IF NOT EXISTS tracking_url TEXT,
  ADD COLUMN IF NOT EXISTS estimated_delivery DATE,
  ADD COLUMN IF NOT EXISTS shipped_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS public.order_status_history (
  id BIGSERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  status VARCHAR(30) NOT NULL,
  note TEXT,
  changed_by INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_order_status_history_order_created
  ON public.order_status_history(order_id, created_at, id);

-- Seed a starting timeline entry for existing orders without history.
INSERT INTO public.order_status_history(order_id, status, note, created_at)
SELECT o.id, o.status, 'Order status recorded during tracking setup', COALESCE(o.created_at, CURRENT_TIMESTAMP)
FROM public.orders o
WHERE NOT EXISTS (SELECT 1 FROM public.order_status_history h WHERE h.order_id = o.id);


-- Record the exact stock batches consumed by each order line so a permitted
-- pre-packing cancellation can restore the same expiry/cost batches.
CREATE TABLE IF NOT EXISTS public.order_batch_allocations (
  id BIGSERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  batch_id BIGINT NOT NULL REFERENCES public.inventory_batches(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  UNIQUE(order_id, batch_id)
);


-- ===== Customer support and delivery exceptions (manual-payment build) =====
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


-- ===== Manual payment confirmation =====
-- Manual payment workflow. Additive only; preserves existing orders and payment history.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
  ADD COLUMN IF NOT EXISTS payment_received_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS payment_received_by INTEGER REFERENCES public.users(id) ON DELETE SET NULL;

-- Existing pending orders are also treated as manual-payment orders until confirmed by an admin.
UPDATE public.orders SET payment_method='MANUAL' WHERE payment_method IS NULL;


-- Extra indexes matching the existing schema and common API queries.
CREATE INDEX IF NOT EXISTS ix_orders_user_created
  ON public.orders (user_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_orders_warehouse_created
  ON public.orders (warehouse_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_orders_product_created
  ON public.orders (product_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_inventory_product
  ON public.inventory (product_id);

COMMIT;

-- Verify after running:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_schema='public' AND table_name='orders' ORDER BY ordinal_position;
-- SELECT to_regclass('public.support_tickets'), to_regclass('public.delivery_exceptions'),
--        to_regclass('public.inventory_batches'), to_regclass('public.order_status_history');
