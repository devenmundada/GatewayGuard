# app/api/v1/tasks.py
from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def list_tasks():
    """
    Tasks endpoint placeholder.

    Tests expect this to return an empty list for a new user.
    """
    return []

@router.get("/ping")
async def ping():
    return {"message": "Tasks endpoint placeholder"}