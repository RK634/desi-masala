-- Manual payment workflow. Additive only; preserves existing orders and payment history.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
  ADD COLUMN IF NOT EXISTS payment_received_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS payment_received_by INTEGER REFERENCES public.users(id) ON DELETE SET NULL;

-- Existing pending orders are also treated as manual-payment orders until confirmed by an admin.
UPDATE public.orders SET payment_method='MANUAL' WHERE payment_method IS NULL;
