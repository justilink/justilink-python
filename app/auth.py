from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app import models

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return pwd_context.hash(mot_de_passe)


def verifier_mot_de_passe(plain: str, hache: str) -> bool:
    return pwd_context.verify(plain, hache)


def creer_token_acces(data: dict,
                      expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY,
                      algorithm=settings.ALGORITHM)


def get_utilisateur_courant(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.Utilisateur:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token invalide")
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"}
        )
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == email
    ).first()
    if not user or not user.actif:
        raise HTTPException(status_code=401,
                            detail="Utilisateur introuvable ou inactif")
    return user


def exiger_role(*roles: models.RoleUtilisateur):
    def _checker(
        current_user: models.Utilisateur = Depends(get_utilisateur_courant)
    ):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Accès refusé – rôle requis : {[r.value for r in roles]}"
            )
        return current_user
    return _checker


def authentifier_utilisateur(db: Session, email: str, mot_de_passe: str):
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == email
    ).first()
    if not user or not verifier_mot_de_passe(mot_de_passe, user.mot_de_passe):
        return None
    return user


def journaliser(db, action, ressource=None, ressource_id=None,
                utilisateur_id=None, details=None, adresse_ip="unknown"):
    db.add(models.JournalAudit(
        utilisateur_id=utilisateur_id, action=action,
        ressource=ressource, ressource_id=ressource_id,
        adresse_ip=adresse_ip, details=details
    ))
    db.commit()

