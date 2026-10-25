-- Run only after registering and verifying your own account.
-- Replace the email below with the account that should be the store administrator.
UPDATE public.users
SET role = 'admin', updated_at = CURRENT_TIMESTAMP
WHERE lower(email) = lower('desimasala001@gmail.com');

-- Verify the result. This should return exactly your intended admin account.
SELECT id, name, email, role, email_verified
FROM public.users
WHERE lower(email) = lower('desimasala001@gmail.com');
