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
