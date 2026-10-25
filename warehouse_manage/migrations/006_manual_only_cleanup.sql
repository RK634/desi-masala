-- Optional future-proofing migration: no schema changes required.
-- Manual payments use payment_method, payment_status, payment_received_at,
-- and payment_received_by, added in migrations 002 and 005.
-- Stripe-specific columns created in 004 are dormant and do not require credentials.
SELECT 'Manual payment schema ready' AS result;
