import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import engine, Base
from app import models  # noqa – crée les tables
from app.routers import users, admissibilite, dossiers, documents, greffe, dashboard
from app.routers.auth_router import router as auth_router
from app.auth import hacher_mot_de_passe
from app.database import SessionLocal




def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Utilisateur).count() > 0:
            return
        for u in [
            {"nom": "Tremblay", "prenom": "Marie-Claude",
             "email": "admin@justlink.gouv.qc.ca",
             "mot_de_passe": hacher_mot_de_passe("Admin2026!"),
             "role": models.RoleUtilisateur.ADMIN},
            {"nom": "Bergeron", "prenom": "Jean-François",
             "email": "greffier@justlink.gouv.qc.ca",
             "mot_de_passe": hacher_mot_de_passe("Greffier2026!"),
             "role": models.RoleUtilisateur.GREFFIER},
            {"nom": "Lavoie", "prenom": "Sophie",
             "email": "avocat@justlink.gouv.qc.ca",
             "mot_de_passe": hacher_mot_de_passe("Avocat2026!"),
             "role": models.RoleUtilisateur.AVOCAT},
            {"nom": "Côté", "prenom": "Patrick",
             "email": "agent@justlink.gouv.qc.ca",
             "mot_de_passe": hacher_mot_de_passe("Agent2026!"),
             "role": models.RoleUtilisateur.AGENT_AJ},
            {"nom": "Dubois", "prenom": "Amélie",
             "email": "citoyen@justlink.gouv.qc.ca",
             "mot_de_passe": hacher_mot_de_passe("Citoyen2026!"),
             "role": models.RoleUtilisateur.CITOYEN},
        ]:
            db.add(models.Utilisateur(**u))
        db.commit()
        print("✅ Comptes de démonstration créés")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="JustiLink",
    description="Plateforme numérique de gestion judiciaire – Projet pilote Longueuil",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(users.users_router)
app.include_router(admissibilite.router)
app.include_router(dossiers.router)
app.include_router(documents.router)
app.include_router(greffe.router)
app.include_router(dashboard.router)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory="frontend/static", html=True), name="static")


@app.get("/", tags=["Accueil"])
def accueil():
    return {
        "message": "Bienvenue sur JustiLink !",
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }


@app.get("/health", tags=["Santé"])
def health():
    return {"status": "healthy", "version": settings.APP_VERSION}

