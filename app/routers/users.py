from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.config import settings
from app.database import get_db

router       = APIRouter(prefix="/api/auth",         tags=["Auth"])
users_router = APIRouter(prefix="/api/utilisateurs", tags=["Utilisateurs"])


@router.post("/token", response_model=schemas.TokenSchema)
def connexion_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = auth.authentifier_utilisateur(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Email ou mot de passe incorrect",
                            headers={"WWW-Authenticate": "Bearer"})
    user.derniere_connexion = datetime.utcnow()
    db.commit()
    token = auth.creer_token_acces(
        data={"sub": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return schemas.TokenSchema(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        utilisateur=schemas.UtilisateurPublic.model_validate(user),
    )


@router.post("/login", response_model=schemas.TokenSchema)
def connexion_json(
    credentials: schemas.LoginSchema,
    db: Session = Depends(get_db),
):
    user = auth.authentifier_utilisateur(
        db, credentials.email, credentials.mot_de_passe
    )
    if not user:
        raise HTTPException(401, "Email ou mot de passe incorrect")
    user.derniere_connexion = datetime.utcnow()
    db.commit()
    token = auth.creer_token_acces(
        data={"sub": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return schemas.TokenSchema(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        utilisateur=schemas.UtilisateurPublic.model_validate(user),
    )


@router.get("/moi", response_model=schemas.UtilisateurDetail)
def profil(current_user=Depends(auth.get_utilisateur_courant)):
    return current_user


@users_router.post("/", response_model=schemas.UtilisateurPublic, status_code=201)
def creer_utilisateur(
    data: schemas.UtilisateurCreate,
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(models.RoleUtilisateur.ADMIN)),
):
    if db.query(models.Utilisateur).filter(
        models.Utilisateur.email == data.email
    ).first():
        raise HTTPException(409, "Email déjà utilisé")
    user = models.Utilisateur(
        nom=data.nom, prenom=data.prenom, email=data.email,
        mot_de_passe=auth.hacher_mot_de_passe(data.mot_de_passe),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@users_router.get("/", response_model=list[schemas.UtilisateurPublic])
def lister_utilisateurs(
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN,
        models.RoleUtilisateur.GREFFIER,
    )),
):
    return db.query(models.Utilisateur).all()
