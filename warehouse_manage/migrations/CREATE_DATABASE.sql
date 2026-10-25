-- Run this while connected to the default `postgres` database, as a role with CREATEDB.
-- CREATE DATABASE cannot run inside a transaction block and will fail if it already exists.
CREATE DATABASE desi_masala ENCODING 'UTF8';
