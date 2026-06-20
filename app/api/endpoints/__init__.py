from .auth import router as auth_router
from .categories import router as categories_router
from .documents import router as documents_router
from .emails import router as emails_router
from .templates import router as templates_router

__all__ = [
    "auth_router",
    "categories_router",
    "documents_router",
    "emails_router",
    "templates_router",
]
