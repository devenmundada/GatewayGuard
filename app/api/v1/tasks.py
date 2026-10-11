"""
Tasks API. Every operation is scoped to the authenticated user: asking for someone
else's task id returns 404 (not 403, so ids of other users' tasks are not revealed).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db import crud
from app.db.database import get_db
from app.schemas.tasks import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter()


async def _get_owned_task(db: AsyncSession, user_id: int, task_id: int):
    task = await crud.get_task(db, user_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await crud.create_task(db, user_id, body.title, body.description)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    completed: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_tasks(db, user_id, completed, limit, offset)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_task(db, user_id, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(db, user_id, task_id)
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is None:
        raise HTTPException(status_code=422, detail="title cannot be null")
    if "completed" in changes and changes["completed"] is None:
        raise HTTPException(status_code=422, detail="completed cannot be null")
    return await crud.update_task(db, task, changes)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(db, user_id, task_id)
    await crud.delete_task(db, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
