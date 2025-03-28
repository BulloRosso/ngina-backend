-- Drop the enum types
DROP TYPE IF EXISTS public.app_role;
DROP TYPE IF EXISTS public.app_permission;
DROP TYPE IF EXISTS public.agent_composition_type;
DROP TYPE IF EXISTS public.agent_output_type;

-- Create agent_output_type enum
CREATE TYPE public.agent_output_type AS ENUM (
    'conversational',
    'content-creation',
    'other'
);

-- Create agent_composition_type enum
CREATE TYPE public.agent_composition_type AS ENUM (
    'atom',
    'chain',
    'dynamic'
);

-- Create app_permission enum
CREATE TYPE public.app_permission AS ENUM (
    'dashboards.edit',
    'dashboards.view'
);

-- Create app_role enum
CREATE TYPE public.app_role AS ENUM (
    'developer',
    'customer'
);