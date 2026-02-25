from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.schemas import (
    AuthResponse,
    CreateGameRequest,
    CreateGameResponse,
    GameStateOut,
    JoinGameRequest,
    JoinGameResponse,
    LoginRequest,
    RegisterRequest,
    StartGameRequest,
)
from app.services.auth_service import auth_service
from app.services.game_service import game_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="QuizBattle Backend", version="1.1.0", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/game/{pin}", response_class=HTMLResponse)
def game_page(request: Request, pin: str):
    return templates.TemplateResponse("game.html", {"request": request, "pin": pin.upper()})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(db, payload.username.strip(), payload.password)
    return AuthResponse(user_id=user.id, username=user.username)


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.login(db, payload.username.strip(), payload.password)
    return AuthResponse(user_id=user.id, username=user.username)


@app.post("/games", response_model=CreateGameResponse)
def create_game(payload: CreateGameRequest, db: Session = Depends(get_db)):
    game, host = game_service.create_game(
        db,
        host_name=payload.host_name,
        topic=payload.topic,
        questions_per_team=payload.questions_per_team,
    )
    state = game_service.to_state(db, game)
    return CreateGameResponse(pin=game.pin, host_player_id=host.id, state=state)


@app.post("/games/{pin}/join", response_model=JoinGameResponse)
async def join_game(pin: str, payload: JoinGameRequest, db: Session = Depends(get_db)):
    player = game_service.join_game(db, pin.upper(), payload.name)
    game = game_service.get_game(db, pin.upper())
    await game_service.broadcast_state(db, game)
    return JoinGameResponse(player_id=player.id, state=game_service.to_state(db, game))


@app.post("/games/{pin}/start", response_model=GameStateOut)
async def start_game(pin: str, payload: StartGameRequest, db: Session = Depends(get_db)):
    game = await game_service.start_game(db, pin.upper(), payload.host_player_id)
    return game_service.to_state(db, game)


@app.get("/games/{pin}", response_model=GameStateOut)
def game_state(pin: str, db: Session = Depends(get_db)):
    game = game_service.get_game(db, pin.upper())
    return game_service.to_state(db, game)


@app.websocket("/ws/{pin}/{player_id}")
async def game_socket(websocket: WebSocket, pin: str, player_id: int):
    pin = pin.upper()
    db = SessionLocal()
    try:
        game_service.get_game(db, pin)
        await game_service.manager.connect(pin, websocket)
        await game_service.broadcast_state(db, game_service.get_game(db, pin))

        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            if action == "answer":
                option_index = int(message.get("option_index"))
                await game_service.process_answer(db, pin, player_id=player_id, option_index=option_index)
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        game_service.manager.disconnect(pin, websocket)
        await game_service.remove_player(db, pin, player_id)
        db.close()
