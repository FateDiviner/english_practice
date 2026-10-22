from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.schemas.common import ApiResponse
from app.services.auth import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[UserOut],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[UserOut]:
    """注册普通用户；接口不提供管理员注册入口。"""
    user = await register_user(
        session=session,
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return ApiResponse[UserOut](code=0, message="ok", data=UserOut.model_validate(user))


@router.post("/login", response_model=ApiResponse[TokenOut])
async def login(
    payload: LoginIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[TokenOut]:
    """按 username 优先、email 其次登录并返回 JWT。"""
    user = await authenticate_user(
        session=session,
        account=payload.account,
        password=payload.password,
    )
    token = create_access_token(user.id, user.role)
    token_data = TokenOut(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )
    return ApiResponse[TokenOut](code=0, message="ok", data=token_data)


@router.get("/me", response_model=ApiResponse[UserOut])
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[UserOut]:
    """返回当前登录用户信息。"""
    return ApiResponse[UserOut](
        code=0,
        message="ok",
        data=UserOut.model_validate(current_user),
    )
