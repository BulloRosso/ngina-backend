# nginA API Backend
This is the nginA API backend based on
* Python
* FastAPI/Pydantic

<img src="/docs/splash-screen.jpg" width="500">

More about the origins of ngina: [background story on LinkedIn](https://www.linkedin.com/pulse/5-challenges-agentaiand-how-inspired-me-build-better-content-g%C3%B6llner-l7jrf)

## nginA Use Case
nginA offers a friendly **self-service user interface** to customers for
* **Asynchronous AI applications** (Long running workflows)
* **Synchronous AI applications** (Chatbots or Taskbots)

nginA is most useful in scenarios where you need to combine **private data** with AI applications and/or
want to give customers UI access for large amounts of AI generated content (PDFs, images, ...).
![Use case](/docs/ngina-usecase.jpg)

## Why was nginA invented?
nginA is a wrapper around n8n to execute agentic workflows. It was
written to enable self-hosted workflows which are compliant to
EU regulations (e. g. hostend on EU servers).

<img src="/docs/high-level-overview.jpg" width="500">

All data is stored in a Supabase instance:
* nginA objects
* n8n schema tables
* Langchain memory
* ...

This setup simplifies backup/restore, because it automatically keeps
the relations between n8n workflows and nginA workflow pointers in sync.

### API Support
nginA is an API-centric product: though it at the core a automation of automations, it 
can be automated itself by using API calls.

When the API service powers up, it shows the API documentation page:

![nginA API catalog](/docs/backend-api-doc.jpg)

This API provides the following main building blocks:

![API structure overview](/docs/api-overview.jpg)

### Authentication
Supabase provides the authentication subsystem which is extended by
several nginA API methods.

To be able to distinguish between customers and you (the developer) we must use RBAC which adds
some complexity to our setup (for security's sake). 

<img src="/docs/auth-hook.jpg" width="380">

The necessary steps are described here: [nginA RBAC](docs/rbac.MD)

### Credential Store
Supabase provides the secure credential store via the PostgreSQL vault
extension. nginA provides API methods for credential management - these
are built upon the Supabase functionality

## Setup

### Fast Lane Setup
Recommended for trials and MVPs. 
#### Database
Subscribe to a Supabase managed service and create your PostgresInstance on an EU server.

Install the 
* [nginA secrets management schema](docs/secrets-management.MD)
* [nginA tagging subsystem](docs/tagging-subsystem.MD)

 
#### n8n
Subscribe to render.com and pull the latest n8n Docker image.
Set the environment variables to point to the Supabase instance:

<img src="/docs/render-com-params-n8n-anonymous.jpg" width="600">

Please enter "n8n" as schema name (instead of public).

Make sure you use the pooled connection settings from the Supabase connection list!

#### Frontend and Python API Backend
Clone the current public objects from replit.com and enter the secrets
for both.

### Mid Scale Setup
Recommended for production loads: Azure cloud.
#### Database
Deploy Supabase using Docker to the Azure cloud. Attention: Docker compose installs several images!
#### n8n
Deploy n8n using the single Docker image to AKS.
#### Frontend
Deploy the React frontend to a static website app.
#### Python Backend API
Create a Docker image and deploy the Docker image to AKS.

## Integrated Diagnostics endpoint
The API features a streaming diagnostics endpoint to validate the current installation
at any time (also in production): GET /api/v1/diagnostics

<img src="/docs/diagnostics-output.jpg" width="500">

Just lean back and watch the tests scrolling by - for advanced automation this endpoint
returns **http status** 200 if all tests passed and 500 if there were errors.

## The Frontend
[React/Vite/Mui Frontend](https://github.com/BulloRosso/nginA-Frontend)