# api/v1/__init__.py
from fastapi import APIRouter
from .auth  import router as auth_router
# from .supportbot import router as supportbot_router
from .agents import router as agents_router
from .team import router as team_router
from .mockup_agents import router as mockup_agents_router
from .vault import router as vault_router 
from .tagging import router as tagging_router
from .operations import router as operations_router
from .build import router as build_router
from .accounting import router as accounting_router
from .scratchpads import router as scratchpads_router
from .context import router as context_router
from .prompts import router as prompts_router
from .dashboards import router as dashboards_router
from .dashboard_components import router as dashboard_components_router
from .users import router as users_router
from .diagnostics import router as diagnostics_router 
from .dashboardbot import router as dashboardbot_router
from .dashboardskpi import router as dashboardskpi_router
from .mcp import router as mcp_router 

router = APIRouter(prefix="/v1")
router.include_router(auth_router)
# router.include_router(supportbot_router)
router.include_router(agents_router)
router.include_router(team_router)
router.include_router(mockup_agents_router)
router.include_router(vault_router) 
router.include_router(tagging_router)
router.include_router(operations_router)
router.include_router(build_router)
router.include_router(accounting_router)
router.include_router(scratchpads_router)
router.include_router(context_router)
router.include_router(prompts_router)
router.include_router(dashboards_router)
router.include_router(dashboard_components_router)
router.include_router(users_router)
router.include_router(diagnostics_router)
router.include_router(dashboardbot_router)
router.include_router(dashboardskpi_router)
router.include_router(mcp_router)