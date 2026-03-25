from aiogram import Router
from bot.handlers.user import router as user_router
from bot.handlers.admin import router as admin_router


def get_root_router() -> Router:
    """Assemble all sub-routers into a single root router."""
    root = Router(name="root")
    root.include_router(user_router)
    root.include_router(admin_router)
    return root


__all__ = ["get_root_router"]
