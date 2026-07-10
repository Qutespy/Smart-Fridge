from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from core.config import settings
from core.schemas import User, UserCreate
from models.user import UserModel

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthHandler:
    def __init__(self, db: Session):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def authenticate_user(self, email: str, password: str) -> Optional[UserModel]:
        user = self.db.query(UserModel).filter(UserModel.email == email).first()
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        if "sub" in to_encode:
            to_encode["sub"] = str(to_encode["sub"])
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    def create_user(self, user_data: UserCreate) -> User:
        hashed_password = self.get_password_hash(user_data.password)

        db_user = UserModel(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            role=user_data.role
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return db_user

    def get_current_user(self, token: str) -> Optional[UserModel]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id_raw = payload.get("sub")
            if user_id_raw is None:
                return None
            user_id = int(user_id_raw)
        except (JWTError, ValueError):
            return None

        user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        return user