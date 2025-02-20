# Secrets Management
Any secret is stored via the vault endpoint of nginA inside of Supabase with an activated Vault module (PostgreSQL).

The secrets can be accessed only by the authenticated user (enforced via RLS). 

A secret for an user has the following properties:
* service_name
* key_name
* secret_key

## API endpoints
The secrets are managed via an API endpoint /api/v1/vault which uses JWT authentication to find out the UUID of the current user.

This implementation:
* Uses JWT authentication through the get_current_user dependency
* Provides CRUD operations for vault credentials
* Ensures users can only access their own credentials
* Uses the secure_credentials view we created earlier
* Handles errors appropriately with logging
* Uses Pydantic models for request/response validation

You can test these endpoints with:

* CREATE: POST /api/v1/vault
* READ: GET /api/v1/vault or GET /api/v1/vault/{credential_id}
* UPDATE: PUT /api/v1/vault/{credential_id}
* DELETE: DELETE /api/v1/vault/{credential_id}

All endpoints require a valid JWT token in the Authorization header with the format: Bearer <token>.

## Database objects creation (SQL)
Use this script to set up the vault subsystem from scratch (the Supabase vault extension must be active!)
```
-- First, enable vault extension if not already enabled
create extension if not exists vault with schema vault;

-- Drop existing objects if they exist for clean setup
drop trigger if exists secure_credentials_insert_trigger on secure_credentials;
drop view if exists secure_credentials;
drop function if exists secure_credentials_insert();
drop table if exists secure_credentials_vault;

-- Create base table with encrypted storage
create table secure_credentials_vault (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  service_name text not null,
  key_name text not null,
  secret_id uuid,  -- Reference to the vault secret
  created_at timestamptz default now()
);

-- Add unique constraint
alter table secure_credentials_vault 
add constraint unique_user_service_key unique (user_id, service_name, key_name);

-- Create view that handles decryption
create view secure_credentials as
  select 
    scv.id,
    scv.user_id,
    scv.service_name,
    scv.key_name,
    ds.decrypted_secret as secret_key,
    scv.created_at
  from secure_credentials_vault scv
  join vault.decrypted_secrets ds on ds.id = scv.secret_id;

-- Create trigger function that handles encryption and upsert logic
create or replace function secure_credentials_insert() returns trigger as $$
declare
  new_secret_id uuid;
  existing_record secure_credentials_vault%ROWTYPE;
begin
  -- Check if record exists
  select * into existing_record 
  from secure_credentials_vault 
  where user_id = NEW.user_id 
    and service_name = NEW.service_name 
    and key_name = NEW.key_name;

  -- Create new secret in vault
  select vault.create_secret(NEW.secret_key) into new_secret_id;

  if existing_record.id is null then
    -- Insert new record if doesn't exist
    insert into secure_credentials_vault (user_id, service_name, key_name, secret_id)
    values (
      NEW.user_id,
      NEW.service_name,
      NEW.key_name,
      new_secret_id
    );
  else
    -- Update existing record
    update secure_credentials_vault 
    set secret_id = new_secret_id
    where id = existing_record.id;
  end if;

  return NEW;
end;
$$ language plpgsql;

-- Create trigger
create trigger secure_credentials_insert_trigger
  instead of insert on secure_credentials
  for each row
  execute function secure_credentials_insert();

-- Enable Row Level Security
alter table secure_credentials_vault enable row level security;

-- Create RLS policy
create policy "Users can only access their own credentials"
  on secure_credentials_vault
  for all
  using (auth.uid() = user_id);

-- Grant necessary permissions
grant all on secure_credentials_vault to authenticated;
grant all on secure_credentials to authenticated;
```