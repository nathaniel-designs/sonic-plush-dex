from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Annotated, Optional
import app.models as models
import math
from app.database import engine, SessionLocal
from sqlalchemy.orm import Session

#error handling
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

#double check these
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exception_handlers import request_validation_exception_handler

#login
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from .auth import create_access_token, verify_password, get_password_hash



app = FastAPI()
models.Base.metadata.create_all(bind = engine)

#Add authentication routes.

class PlushBase(BaseModel):
    character: str
    variation: str
    set: str
    releaseyear: int
     

#dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
            db.close()

db_dependency = Annotated[Session, Depends(get_db)]

#returns entire database
@app.get("/plushies/all")
def get_all_plushies(db: Session = Depends(get_db)):
    return db.query(models.PlushTable).order_by(models.PlushTable.id.asc()).all()

@app.get("/plushies/{plush_id}")
async def get_plush(plush_id: int, db: db_dependency):
     result = db.query(models.PlushTable).filter(models.PlushTable.id == plush_id).first()
     if not result:
          raise HTTPException(status_code = 404, detail = "Plush not found!")
     return result

#add new plushie to database
@app.post("/plushies/")
async def create_plush(plush: PlushBase, db: db_dependency):
    db_plush = models.PlushTable(
         character = plush.character,
         variation = plush.variation,
         set = plush.set,
         releaseyear = plush.releaseyear
    )
    db.add(db_plush)
    db.commit()
    db.refresh(db_plush)
    return db_plush

#database search function w/ pagination
@app.get("/search/")
def search_plushies(
    q: Optional[str] = None,  # Optional query parameter 'q'
    character: Optional[str] = None,
    variation: Optional[str] = None,
    set: Optional[str] = None,
    skip: int = 0, 
    limit: int = 10, 
    db: Session = Depends(get_db)
):

    query = db.query(models.PlushTable)
    if q:
        query = query.filter(
        models.PlushTable.character.ilike(f"%{q}%") |
        models.PlushTable.variation.ilike(f"%{q}%") |
        models.PlushTable.set.ilike(f"%{q}%")
    )

    if character:
        query = query.filter(models.PlushTable.character.ilike(f"%{character}%"))
    if variation:
        query = query.filter(models.PlushTable.variation.ilike(f"%{variation}%"))
    if set:
        query = query.filter(models.PlushTable.set.ilike(f"%{set}%"))

    total_results = query.count()
    results = query.offset(skip).limit(limit).all()
    total_pages = math.ceil(total_results / limit) if limit else 1


    return{
        "skip": skip,
        "total_pages": total_pages,
        "current_page": (skip // limit) + 1 if limit else 1,
        "limit": limit,
        "results": results
    }

#database pagination function
@app.get("/plushies/")
def get_plushies(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.PlushTable).order_by(models.PlushTable.id.asc()).offset(skip).limit(limit).all()

#database filter function w/ pagination
@app.get("/filter/")
def filter_plushies(
    characters: Optional[List[str]] = Query(None),
    variations: Optional[List[str]] = Query(None),
    sets: Optional[List[str]] = Query(None),
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):

    query = db.query(models.PlushTable)

    if characters:
        query = query.filter(models.PlushTable.character.in_(characters))
    if variations:
        query = query.filter(models.PlushTable.variation.in_(variations))
    if sets:
        query = query.filter(models.PlushTable.set.in_(sets))
    if min_year:
        query = query.filter(models.PlushTable.releaseyear >= min_year)
    if max_year:
        query = query.filter(models.PlushTable.releaseyear <= max_year)

    total_results = query.count()
    results = query.offset(skip).limit(limit).all()
    total_pages = math.ceil(total_results / limit) if limit else 1

    return{
        "filters": {
            "characters": characters,
            "variations": variations,
            "sets": sets,
            "min_year": min_year,
            "max_year": max_year
        },
        "skip": skip,
        "total_pages": total_pages,
        "current_page": (skip // limit) + 1 if limit else 1,
        "limit": limit,
        "results": results
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
            "message": "Request validation failed"
        },
    )

@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=400,
        content={"message": "Database integrity error", "detail": str(exc.orig)}
    )

@app.exception_handler(SQLAlchemyError)
async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"message": "Database error", "detail": str(exc)}
    )

#login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "token")

#register user
@app.post("/register")
def register(form_data:OAuth2PasswordRequestForm = Depends(), db:Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if existing_user:
        raise HTTPException(status_code = 400, detail = "Username already registered.")
    hashed_pw = get_password_hash(form_data.password)
    new_user = models.User(username = form_data.username, hashed_password = hashed_pw)
    db.add(new_user)
    db.commit()
    return{
        "msg": "User registered successfully!"
    }

#user login
@app.post("/token")
def login(form_data:OAuth2PasswordRequestForm = Depends(), db:Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code = 401, detail = "Invalid username or password")
    access_token = create_access_token(
        data={"sub":user.username},
        expires_delta = timedelta(minutes = 60)
    )
    return{"access_token": access_token,"token_type": "bearer"}

