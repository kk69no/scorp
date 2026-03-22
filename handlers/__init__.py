"""Register all routers."""

from aiogram import Router

from .start import router as start_router
from .booking import router as booking_router
from .my_bookings import router as my_bookings_router
from .loyalty import router as loyalty_router
from .showcase import router as showcase_router
from .admin import router as admin_router
from .feedback import router as feedback_router


def get_all_routers() -> list[Router]:
    return [
        start_router,
        booking_router,
        my_bookings_router,
        loyalty_router,
        showcase_router,
        admin_router,
        feedback_router,
    ]
