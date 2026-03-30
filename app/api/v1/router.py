from fastapi import APIRouter
from app.api.v1 import extract, feedback, account

router = APIRouter(prefix="/v1")

router.include_router(extract.router, prefix="/extract", tags=["extract"])
router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
router.include_router(account.router, prefix="/account", tags=["account"])
