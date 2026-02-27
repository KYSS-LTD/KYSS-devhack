"""Маршруты API для приложения QuizBattle."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from fastapi import Cookie

from app.database import SessionLocal, get_db
from app.models import User
from app.schemas import (
    AuthResponse,
    CreateGameRequest,
    CreateGameResponse,
    GameStateOut,
    JoinGameRequest,
    JoinGameResponse,
    LoginRequest,
    RatingResponse,
    RegisterRequest,
    StartGameRequest,
    UserProfileStatsResponse,
)
from app.services.auth_service import auth_service
from app.services.game_service import game_service
from app.security import (
    create_player_token,
    create_user_session_token,
    get_cookie_settings,
    verify_player_token,
    verify_user_session_token,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
REQUEST_LOGS: dict[str, deque] = defaultdict(deque)


def enforce_rate_limit(request: Request, limit: int = 90, window: int = 60) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = REQUEST_LOGS[ip]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Слишком много запросов")
    bucket.append(now)


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})




def get_optional_authenticated_user_id(session_token: str | None, db: Session) -> int | None:
    if not session_token:
        return None

    user_id = verify_user_session_token(session_token)
    user_exists = db.query(User.id).filter(User.id == user_id).first()
    if not user_exists:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user_id


def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    user_id = verify_user_session_token(session_token)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user

@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats = game_service.get_user_stats(
        db,
        user_id=current_user.id,
        username=current_user.username
    )

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": current_user,
            "stats": stats
        }
    )


@router.get("/rating", response_class=HTMLResponse)
def rating_page(request: Request, db: Session = Depends(get_db)):
    rating = game_service.get_rating(db)
    return templates.TemplateResponse("rating.html", {"request": request, "rating": rating})


@router.get("/game/{pin}", response_class=HTMLResponse)
def game_page(request: Request, pin: str):
    return templates.TemplateResponse("game.html", {"request": request, "pin": pin.upper()})


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    user = auth_service.register(db, payload.username.strip(), payload.password)
    cookie_settings = get_cookie_settings()

    response = JSONResponse(
        content=AuthResponse(user_id=user.id, username=user.username).dict()
    )
    response.set_cookie(
        key="session_token",
        value=create_user_session_token(user.id),
        httponly=True,
        secure=cookie_settings.secure,
        samesite=cookie_settings.samesite,
    )
    return response


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    user = auth_service.login(db, payload.username.strip(), payload.password)
    cookie_settings = get_cookie_settings()

    response = JSONResponse(
        content=AuthResponse(user_id=user.id, username=user.username).dict()
    )

    response.set_cookie(
        key="session_token",
        value=create_user_session_token(user.id),
        httponly=True,
        secure=cookie_settings.secure,
        samesite=cookie_settings.samesite,
    )

    return response




@router.post("/auth/logout")
def logout():
    response = JSONResponse(content={"ok": True})
    response.delete_cookie("session_token")
    return response

@router.get("/users/{user_id}/stats", response_model=UserProfileStatsResponse)
def user_stats(user_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return game_service.get_user_stats(db, user_id=user.id, username=user.username)


@router.get("/rating/data", response_model=RatingResponse)
def rating_data(request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    return game_service.get_rating(db)


@router.post("/games", response_model=CreateGameResponse)
def create_game(payload: CreateGameRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    session_token = request.cookies.get("session_token")
    effective_user_id = get_optional_authenticated_user_id(session_token, db)

    game, host = game_service.create_game(
        db,
        payload.host_name,
        payload.topic,
        payload.questions_per_team,
        effective_user_id,
        payload.difficulty,
        payload.pin,
    )
    return CreateGameResponse(
        pin=game.pin,
        host_player_id=host.id,
        player_token=create_player_token(game.pin, host.id),
        state=game_service.to_state(db, game),
    )


@router.post("/games/{pin}/join", response_model=JoinGameResponse)
async def join_game(
    pin: str,
    payload: JoinGameRequest,
    request: Request,
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None),
):
    enforce_rate_limit(request)
    effective_user_id = get_optional_authenticated_user_id(session_token, db)
    player = game_service.join_game(db, pin.upper(), payload.name, effective_user_id)
    game = game_service.get_game(db, pin.upper())
    await game_service.broadcast_state(db, game)
    return JoinGameResponse(
        player_id=player.id,
        player_token=create_player_token(pin.upper(), player.id),
        state=game_service.to_state(db, game),
    )


@router.post("/games/{pin}/start", response_model=GameStateOut)
async def start_game(pin: str, payload: StartGameRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    game = await game_service.start_game(db, pin.upper(), payload.host_player_id)
    return game_service.to_state(db, game)


@router.get("/games/{pin}", response_model=GameStateOut)
def game_state(pin: str, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request)
    game = game_service.get_game(db, pin.upper())
    return game_service.to_state(db, game)


@router.websocket("/ws/{pin}/{player_id}")
async def game_socket(websocket: WebSocket, pin: str, player_id: int, token: str | None = Query(default=None)):
    pin = pin.upper()
    db = SessionLocal()
    try:
        verify_player_token(pin, player_id, token)
        game_service.get_game(db, pin)
        await game_service.manager.connect(pin, websocket)
        await game_service.broadcast_state(db, game_service.get_game(db, pin))
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            if action == "answer":
                await game_service.process_answer(db, pin, player_id=player_id, option_index=int(message.get("option_index")))
            elif action == "vote":
                await game_service.cast_vote(db, pin, player_id=player_id, choice=str(message.get("choice")))
            elif action == "skip":
                await game_service.process_answer(db, pin, player_id=player_id, option_index=None, skip=True)
            elif action == "transfer_captain":
                await game_service.transfer_captain(db, pin, from_player_id=player_id, to_player_id=int(message.get("to_player_id")))
            elif action == "host_control":
                await game_service.host_control(
                    db,
                    pin,
                    host_player_id=player_id,
                    action=str(message.get("control_action")),
                    target_player_id=message.get("target_player_id"),
                    topic=message.get("topic"),
                    difficulty=message.get("difficulty"),
                )
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    except HTTPException:
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        pass
    finally:
        game_service.manager.disconnect(pin, websocket)
        db.close()
