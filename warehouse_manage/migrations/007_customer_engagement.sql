-- Desi Masala customer engagement, wishlist, feedback and birthday offers.
-- Run after UPGRADE_EXISTING_DATABASE_MANUAL_PAYMENTS.sql in pgAdmin 4.
BEGIN;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS expiry_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (expiry_discount_percent BETWEEN 0 AND 100);
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS expiry_discount_until DATE;
CREATE TABLE IF NOT EXISTS public.customer_favorites (
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(user_id, product_id)
);
CREATE TABLE IF NOT EXISTS public.customer_feedback (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  order_id INTEGER REFERENCES public.orders(id) ON DELETE SET NULL,
  feedback_type VARCHAR(30) NOT NULL DEFAULT 'GENERAL' CHECK (feedback_type IN ('GENERAL','PRODUCT','DELIVERY','FEATURE_REQUEST','COMPLAINT')),
  rating SMALLINT CHECK (rating BETWEEN 1 AND 5),
  subject VARCHAR(180) NOT NULL,
  message TEXT NOT NULL CHECK (length(trim(message)) > 0),
  status VARCHAR(20) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','REVIEWING','PLANNED','RESOLVED','CLOSED')),
  admin_response TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_customer_feedback_status_created ON public.customer_feedback(status, created_at DESC);
CREATE TABLE IF NOT EXISTS public.birthday_offer_log (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  offer_year INTEGER NOT NULL,
  offer_code VARCHAR(40) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, offer_year)
);
CREATE TABLE IF NOT EXISTS public.scheduled_job_log (
  job_key VARCHAR(160) PRIMARY KEY,
  ran_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  result JSONB NOT NULL DEFAULT '{}'::jsonb
);
COMMIT;
