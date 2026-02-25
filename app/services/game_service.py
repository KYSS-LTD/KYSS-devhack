import asyncio
import random
import string
from collections import defaultdict

from fastapi import HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Game, Player, Question
from app.schemas import GameStateOut, PlayerOut, QuestionPublic
from app.services.ai_service import generate_questions

QUESTION_TIMEOUT_SECONDS = 30


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, game_pin: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[game_pin].add(websocket)

    def disconnect(self, game_pin: str, websocket: WebSocket) -> None:
        if game_pin in self.connections:
            self.connections[game_pin].discard(websocket)
            if not self.connections[game_pin]:
                self.connections.pop(game_pin, None)

    async def broadcast(self, game_pin: str, payload: dict) -> None:
        sockets = list(self.connections.get(game_pin, set()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(game_pin, ws)


class GameService:
    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self.timer_tasks: dict[str, asyncio.Task] = {}

    def generate_pin(self, db: Session) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            pin = "".join(random.choices(alphabet, k=6))
            existing = db.query(Game).filter(Game.pin == pin, Game.status != "finished").first()
            if not existing:
                return pin

    def create_game(self, db: Session, host_name: str, topic: str, questions_per_team: int) -> tuple[Game, Player]:
        pin = self.generate_pin(db)
        game = Game(pin=pin, topic=topic, questions_per_team=questions_per_team, status="waiting")
        db.add(game)
        db.flush()

        host = Player(game_id=game.id, name=host_name, team="A", is_host=True)
        db.add(host)

        for team in ("A", "B"):
            generated = generate_questions(topic, questions_per_team)
            for idx, q in enumerate(generated):
                question = Question(
                    game_id=game.id,
                    team=team,
                    order_index=idx,
                    text=q["text"],
                    option_1=q["options"][0],
                    option_2=q["options"][1],
                    option_3=q["options"][2],
                    option_4=q["options"][3],
                    correct_option=q["correct_option"],
                )
                db.add(question)

        db.commit()
        db.refresh(game)
        db.refresh(host)
        return game, host

    def rebalance_teams(self, db: Session, game: Game) -> None:
        players = db.query(Player).filter(Player.game_id == game.id).order_by(Player.joined_at.asc()).all()
        shuffled = players[:]
        random.shuffle(shuffled)
        for idx, player in enumerate(shuffled):
            player.team = "A" if idx % 2 == 0 else "B"
        db.commit()

    def join_game(self, db: Session, pin: str, name: str) -> Player:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.status != "waiting":
            raise HTTPException(status_code=400, detail="Game already started")

        player = Player(game_id=game.id, name=name, team="A", is_host=False)
        db.add(player)
        db.commit()
        db.refresh(player)

        self.rebalance_teams(db, game)
        db.refresh(player)
        return player

    def get_game(self, db: Session, pin: str) -> Game:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game

    def get_current_question(self, db: Session, game: Game) -> Question | None:
        if game.status != "in_progress" or not game.current_team:
            return None
        index = game.current_index_a if game.current_team == "A" else game.current_index_b
        question = (
            db.query(Question)
            .filter(
                Question.game_id == game.id,
                Question.team == game.current_team,
                Question.order_index == index,
            )
            .first()
        )
        return question

    def to_state(self, db: Session, game: Game) -> GameStateOut:
        players = db.query(Player).filter(Player.game_id == game.id).order_by(Player.joined_at.asc()).all()
        current_question = self.get_current_question(db, game)

        winner = None
        if game.status == "finished":
            if game.score_a > game.score_b:
                winner = "A"
            elif game.score_b > game.score_a:
                winner = "B"
            else:
                winner = "draw"

        return GameStateOut(
            pin=game.pin,
            topic=game.topic,
            status=game.status,
            questions_per_team=game.questions_per_team,
            current_team=game.current_team,
            score_a=game.score_a,
            score_b=game.score_b,
            current_question=QuestionPublic(
                id=current_question.id,
                team=current_question.team,
                order_index=current_question.order_index,
                text=current_question.text,
                options=[
                    current_question.option_1,
                    current_question.option_2,
                    current_question.option_3,
                    current_question.option_4,
                ],
            )
            if current_question
            else None,
            players=[PlayerOut(id=p.id, name=p.name, team=p.team, is_host=p.is_host) for p in players],
            winner=winner,
        )

    async def broadcast_state(self, db: Session, game: Game) -> None:
        await self.manager.broadcast(game.pin, {"type": "state", "data": self.to_state(db, game).model_dump()})

    async def start_game(self, db: Session, pin: str, host_player_id: int) -> Game:
        game = self.get_game(db, pin)
        host = db.query(Player).filter(Player.id == host_player_id, Player.game_id == game.id).first()
        if not host or not host.is_host:
            raise HTTPException(status_code=403, detail="Only host can start game")
        if game.status != "waiting":
            raise HTTPException(status_code=400, detail="Game already started")

        game.status = "in_progress"
        game.current_team = "A"
        game.current_index_a = 0
        game.current_index_b = 0
        db.commit()
        db.refresh(game)

        await self.broadcast_state(db, game)
        await self.start_timer(db, game.pin)
        return game

    async def start_timer(self, _db: Session, pin: str) -> None:
        existing = self.timer_tasks.get(pin)
        if existing and not existing.done():
            existing.cancel()

        async def timer_coroutine() -> None:
            try:
                await asyncio.sleep(QUESTION_TIMEOUT_SECONDS)
                local_db = SessionLocal()
                try:
                    game = self.get_game(local_db, pin)
                    if game.status != "in_progress":
                        return
                    await self.process_answer(local_db, pin, player_id=None, option_index=None, timeout=True)
                finally:
                    local_db.close()
            except asyncio.CancelledError:
                return

        self.timer_tasks[pin] = asyncio.create_task(timer_coroutine())

    async def process_answer(
        self,
        db: Session,
        pin: str,
        player_id: int | None,
        option_index: int | None,
        timeout: bool = False,
    ) -> None:
        game = self.get_game(db, pin)
        if game.status != "in_progress":
            return

        question = self.get_current_question(db, game)
        if not question or question.answered:
            return

        if not timeout:
            player = db.query(Player).filter(Player.id == player_id, Player.game_id == game.id).first()
            if not player:
                raise HTTPException(status_code=404, detail="Player not found")
            if player.team != game.current_team:
                raise HTTPException(status_code=400, detail="Not your team's turn")
            if option_index is None or option_index not in [1, 2, 3, 4]:
                raise HTTPException(status_code=400, detail="Invalid option")

        is_correct = (not timeout) and option_index == question.correct_option
        question.answered = True
        if is_correct:
            if game.current_team == "A":
                game.score_a += 1
            else:
                game.score_b += 1

        if game.current_team == "A":
            game.current_index_a += 1
            game.current_team = "B"
        else:
            game.current_index_b += 1
            game.current_team = "A"

        if game.current_index_a >= game.questions_per_team and game.current_index_b >= game.questions_per_team:
            game.status = "finished"
            game.current_team = None

        db.commit()
        db.refresh(game)

        await self.manager.broadcast(
            pin,
            {
                "type": "answer_result",
                "data": {
                    "timeout": timeout,
                    "correct": is_correct,
                    "correct_option": question.correct_option,
                    "team": question.team,
                    "question_id": question.id,
                },
            },
        )
        await self.broadcast_state(db, game)

        if game.status == "in_progress":
            await self.start_timer(db, pin)

    async def remove_player(self, db: Session, pin: str, player_id: int) -> None:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            return
        player = db.query(Player).filter(Player.id == player_id, Player.game_id == game.id).first()
        if not player:
            return
        db.delete(player)
        db.commit()

        players_left = db.query(Player).filter(Player.game_id == game.id).count()
        if players_left == 0:
            game.status = "finished"
            game.current_team = None
            db.commit()

        await self.broadcast_state(db, game)


game_service = GameService()
