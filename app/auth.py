import pyotp
import qrcode
import io
import base64
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
# ─── Refresh Token ────────────────────────────────────────────────────────────

def creer_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY,
                      algorithm=settings.ALGORITHM)


# ─── MFA (TOTP) ───────────────────────────────────────────────────────────────

def generer_secret_mfa() -> str:
    return pyotp.random_base32()


def obtenir_qr_mfa(email: str, secret: str) -> str:
    """Retourne une image QR code encodée en base64 (PNG)."""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name="JustiLink")
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def verifier_code_mfa(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ─── Dépendance MFA en attente ────────────────────────────────────────────────

def get_utilisateur_mfa_en_attente(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.Utilisateur:
    """Utilisé uniquement pendant l'étape de vérification MFA."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        if not payload.get("mfa_pending"):
            raise HTTPException(status_code=401, detail="Token invalide")
        email: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expiré")
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == email
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user

