DROP VIEW IF EXISTS test.secure_credentials;

create view public.secure_credentials as
select
  scv.id,
  scv.user_id,
  scv.service_name,
  scv.key_name,
  ds.decrypted_secret as secret_key,
  scv.created_at
from
  secure_credentials_vault scv
  join vault.decrypted_secrets ds on ds.id = scv.secret_id;