from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from repositories.user_repository import UserRepository
from db.dependencies import get_db

router = APIRouter(tags=["user"])
security = HTTPBearer()


def get_user_repo(conn=Depends(get_db)) -> UserRepository:
    return UserRepository(conn)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    repo: UserRepository = Depends(get_user_repo),
) -> dict:
    user = repo.get_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.get("/user")
def get_user(current_user: dict = Depends(get_current_user)):
    return current_user


@router.get("/videos")
def get_videos(current_user: dict = Depends(get_current_user)):
    return {"archive_1": ["video_1", "video_2"], "archive_2": ["video_3"]}