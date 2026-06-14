import base64, hashlib, hmac, json, os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .database import get_db
from .models import User

SECRET_KEY = os.getenv('SECRET_KEY', 'streamhub-coursework-secret')
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')

def create_token(user: User) -> str:
    payload = {'sub': str(user.id), 'exp': (datetime.now(timezone.utc) + timedelta(days=7)).timestamp()}
    body = _b64(json.dumps(payload).encode())
    sig = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
    return f'{body}.{_b64(sig)}'

def parse_token(token: str) -> str:
    try:
      body, sig = token.split('.', 1)
      expected = _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
      if not hmac.compare_digest(sig, expected):
          raise ValueError('bad signature')
      payload = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)).decode())
      if payload['exp'] < datetime.now(timezone.utc).timestamp():
          raise ValueError('expired')
      return payload['sub']
    except Exception:
      raise HTTPException(status_code=401, detail='登录状态已失效，请重新登录')

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='请先登录')
    user_id = parse_token(authorization.replace('Bearer ', '', 1))
    user = db.get(User, user_id)
    if not user or user.status != 0:
        raise HTTPException(status_code=401, detail='用户不存在或已被封禁')
    return user

def require_creator(user: User = Depends(get_current_user)) -> User:
    if user.user_type < 1:
        raise HTTPException(status_code=403, detail='需要创作者权限')
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.user_type < 2:
        raise HTTPException(status_code=403, detail='需要管理员权限')
    return user

from typing import Optional

def get_current_user_optional(authorization: str = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    """获取当前用户，未登录时返回 None"""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    try:
        user_id = parse_token(authorization.replace('Bearer ', '', 1))
        user = db.get(User, user_id)
        if user and user.status == 0:
            return user
        return None
    except Exception:
        return None