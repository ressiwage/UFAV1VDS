from fastapi import APIRouter, Depends, HTTPException
from repositories.user_repository import UserRepository
from db.dependencies import get_db
from _shared._common.models.models import UserLogin, UserRegister

router = APIRouter(tags=["auth"])


def get_user_repo(conn=Depends(get_db)) -> UserRepository:
    return UserRepository(conn)


@router.post("/register")
def register(user: UserRegister, repo: UserRepository = Depends(get_user_repo)):
    repo.create(user.username, user.password)
    return {"status": "ok"}


@router.post("/login")
def login(user: UserLogin, repo: UserRepository = Depends(get_user_repo)):
    result = repo.get_by_credentials(user.username, user.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = repo.set_token(result["id"])
    return {"token": token}