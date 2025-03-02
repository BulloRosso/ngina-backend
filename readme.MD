# nginA API Backend
This is the nginA API backend based on
* Python
* FastAPI/Pydantic

![Splash screen](/doc/splash-screen.jpg)

More about the origins of ngina: [background story on LinkedIn](https://www.linkedin.com/pulse/5-challenges-agentaiand-how-inspired-me-build-better-content-g%C3%B6llner-l7jrf)

## Why was nginA invented?
nginA is a wrapper around n8n to execute agentic workflows. It was
written to enable self-hosted workflows which are compliant to
EU regulations (e. g. hostend on EU servers).

![High level overview](/doc/high-level-overview.jpg)

All data is stored in a Supabase instance:
* nginA objects
* n8n schema tables
* Langchain memory
* ...

This setup simplifies backup/restore, because it automatically keeps
the relations between n8n workflows and nginA workflow pointers in sync.

### Authentication
Supabase provides the authentication subsystem which is extended by
several nginA API methods.

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
* [nginA secrets management schema](docs/secrets-managwment.MD)
* [nginA tagging subsystem](docs/tagging-subsystem.MD)

 
#### n8n
Subscribe to render.com and pull the latest n8n Docker image.
Set the environment variables to point to the Supabase instance:

![Docker environment variables](/doc/render-com-params-n8n-anonymous.jpg)

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
