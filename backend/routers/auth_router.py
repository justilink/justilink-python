from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from jose import JWTError, jwt

from backend.database import get_db
from backend import models
from backend.config import settings
from backend.auth import (
    authentifier_utilisateur,
    creer_token_acces,
    creer_refresh_token,
    generer_secret_mfa,
    obtenir_qr_mfa,
    verifier_code_mfa,
    get_utilisateur_courant,
    get_utilisateur_mfa_en_attente,
    journaliser,
)

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class MFACodeRequest(BaseModel):
    code: str

class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str


@router.post("/token", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authentifier_utilisateur(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    user.derniere_connexion = datetime.utcnow()
    db.commit()
    journaliser(db, action="LOGIN", utilisateur_id=user.id, ressource="auth")
    if user.mfa_active:
        temp = creer_token_acces(data={"sub": user.email, "mfa_pending": True})
        return TokenResponse(access_token=temp, refresh_token="", mfa_required=True)
    return TokenResponse(
        access_token=creer_token_acces({"sub": user.email}),
        refresh_token=creer_refresh_token({"sub": user.email}),
    )


@router.get("/me")
def get_me(current_user: models.Utilisateur = Depends(get_utilisateur_courant)):
    return {
        "id": current_user.id,
        "nom": current_user.nom,
        "prenom": current_user.prenom,
        "email": current_user.email,
        "role": current_user.role,
        "mfa_active": current_user.mfa_active,
        "derniere_connexion": current_user.derniere_connexion,
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.refresh_token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token invalide")
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expiré")
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == email, models.Utilisateur.actif == True
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return TokenResponse(
        access_token=creer_token_acces({"sub": user.email}),
        refresh_token=creer_refresh_token({"sub": user.email}),
    )


@router.post("/logout")
def logout(current_user: models.Utilisateur = Depends(get_utilisateur_courant),
           db: Session = Depends(get_db)):
    journaliser(db, action="LOGOUT", utilisateur_id=current_user.id, ressource="auth")
    return {"message": "Déconnexion réussie"}


@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(current_user: models.Utilisateur = Depends(get_utilisateur_courant),
              db: Session = Depends(get_db)):
    if current_user.mfa_active:
        raise HTTPException(status_code=400, detail="MFA déjà activé")
    secret = generer_secret_mfa()
    current_user.mfa_secret = secret
    db.commit()
    return MFASetupResponse(secret=secret, qr_code=obtenir_qr_mfa(current_user.email, secret))


@router.post("/mfa/activer")
def activer_mfa(request: MFACodeRequest,
                current_user: models.Utilisateur = Depends(get_utilisateur_courant),
                db: Session = Depends(get_db)):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="Appelez d'abord /api/auth/mfa/setup")
    if not verifier_code_mfa(current_user.mfa_secret, request.code):
        raise HTTPException(status_code=401, detail="Code invalide")
    current_user.mfa_active = True
    db.commit()
    return {"message": "MFA activé ✅"}


@router.post("/mfa/verifier", response_model=TokenResponse)
def verifier_mfa(request: MFACodeRequest,
                 user: models.Utilisateur = Depends(get_utilisateur_mfa_en_attente),
                 db: Session = Depends(get_db)):
    if not user.mfa_secret or not verifier_code_mfa(user.mfa_secret, request.code):
        raise HTTPException(status_code=401, detail="Code MFA invalide")
    return TokenResponse(
        access_token=creer_token_acces({"sub": user.email}),
        refresh_token=creer_refresh_token({"sub": user.email}),
    )


@router.post("/mfa/desactiver")
def desactiver_mfa(request: MFACodeRequest,
                   current_user: models.Utilisateur = Depends(get_utilisateur_courant),
                   db: Session = Depends(get_db)):
    if not current_user.mfa_active:
        raise HTTPException(status_code=400, detail="MFA non activé")
    if not verifier_code_mfa(current_user.mfa_secret, request.code):
        raise HTTPException(status_code=401, detail="Code invalide")
    current_user.mfa_active = False
    current_user.mfa_secret = None
    db.commit()
    return {"message": "MFA désactivé"}
