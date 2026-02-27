"""Сервис игры."""

import asyncio
import random
import string
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Game, Player, Question, User
from app.schemas import (
    GameStateOut,
    PlayerOut,
    QuestionPublic,
    RatingResponse,
    RatingRow,
    TeammateStat,
    TeamStats,
    UserProfileStatsResponse,
)
from app.services.ai_service import generate_questions

BASE_QUESTION_TIMEOUT = {"easy": 35, "medium": 30, "hard": 25}


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
        self.votes: dict[str, dict[int, str]] = defaultdict(dict)
        self.team_stats: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: {
                "A": {"correct": 0, "incorrect": 0, "timeout": 0, "speed_bonus": 0},
                "B": {"correct": 0, "incorrect": 0, "timeout": 0, "speed_bonus": 0},
            }
        )
        self.paused_remaining: dict[str, int] = {}
        self.paused_elapsed: dict[str, int] = {}

    def generate_pin(self, db: Session) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            pin = "".join(random.choices(alphabet, k=6))
            if not db.query(Game).filter(Game.pin == pin, Game.status != "finished").first():
                return pin

    def create_game(
            self,
            db: Session,
            host_name: str,
            topic: str,
            questions_per_team: int,
            user_id: int | None,
            difficulty: str = "medium",
    ) -> tuple[Game, Player]:
        pin = self.generate_pin(db)
        game = Game(pin=pin, topic=topic, questions_per_team=questions_per_team, status="waiting",
                    difficulty=difficulty, phase="gathering")
        db.add(game)
        db.flush()

        host = Player(game_id=game.id, user_id=user_id, name=host_name, team=None, is_host=True, is_captain=False,
                      active=True)
        db.add(host)

        # --- ОДИН ЗАПРОС НА ВСЕ КОМАНДЫ ---
        total_count = questions_per_team * 2
        all_generated = generate_questions(topic, total_count, difficulty=difficulty)

        # Перемешиваем, чтобы распределение было случайным
        random.shuffle(all_generated)

        # Распределяем: первые N — команде A, остальные — команде B
        for i, q_data in enumerate(all_generated):
            team_label = "A" if i < questions_per_team else "B"
            order_idx = i if team_label == "A" else i - questions_per_team
            correct_idx = int(q_data["correct_option"]) - 1

            db.add(Question(
                game_id=game.id,
                team=team_label,
                order_index=order_idx,
                text=q_data["text"],
                option_1=q_data["options"][0],
                option_2=q_data["options"][1],
                option_3=q_data["options"][2],
                option_4=q_data["options"][3],
                correct_option=correct_idx
            ))
        # ----------------------------------

        db.commit()
        db.refresh(game)
        db.refresh(host)
        return game, host

    def _assign_teams_and_captains(self, db: Session, game: Game) -> None:
        players = db.query(Player).filter(Player.game_id == game.id, Player.active.is_(True)).order_by(Player.joined_at.asc()).all()
        shuffled = players[:]
        random.shuffle(shuffled)
        for idx, player in enumerate(shuffled):
            player.team = "A" if idx % 2 == 0 else "B"
            player.is_captain = False
        for team in ("A", "B"):
            first = next((p for p in players if p.team == team), None)
            if first:
                first.is_captain = True
        db.commit()

    def join_game(self, db: Session, pin: str, name: str, user_id: int | None) -> Player:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.status != "waiting":
            raise HTTPException(status_code=400, detail="Game already started")

        duplicate_player = None
        if user_id is not None:
            duplicate_player = (
                db.query(Player)
                .filter(
                    Player.game_id == game.id,
                    Player.active.is_(True),
                    Player.user_id == user_id,
                )
                .first()
            )
        if duplicate_player is None:
            duplicate_player = (
                db.query(Player)
                .filter(
                    Player.game_id == game.id,
                    Player.active.is_(True),
                    Player.name == name,
                )
                .first()
            )
        if duplicate_player:
            raise HTTPException(status_code=400, detail="Вы уже в этой комнате")

        player = Player(game_id=game.id, user_id=user_id, name=name, team=None, is_host=False, is_captain=False, active=True)
        db.add(player)
        db.commit()
        db.refresh(player)
        return player

    def get_game(self, db: Session, pin: str) -> Game:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game

    def get_current_question(self, db: Session, game: Game) -> Question | None:
        if game.status != "in_progress" or game.phase != "question" or not game.current_team:
            return None
        index = game.current_index_a if game.current_team == "A" else game.current_index_b
        return db.query(Question).filter(Question.game_id == game.id, Question.team == game.current_team, Question.order_index == index).first()

    def _vote_percentages(self, db: Session, game: Game) -> dict[str, int]:
        votes = list(self.votes[game.pin].values())
        if not votes:
            return {}
        total = len(votes)
        counter = Counter(votes)
        return {key: int((val / total) * 100) for key, val in counter.items()}

    def to_state(self, db: Session, game: Game) -> GameStateOut:
        players = db.query(Player).filter(Player.game_id == game.id, Player.active.is_(True)).order_by(Player.joined_at.asc()).all()
        current_question = self.get_current_question(db, game)
        question_seconds_left = None
        if game.status == "in_progress":
            if game.phase == "question" and game.question_started_at:
                elapsed = max(0, int((datetime.now(timezone.utc) - game.question_started_at.replace(tzinfo=timezone.utc)).total_seconds()))
                question_seconds_left = max(0, BASE_QUESTION_TIMEOUT.get(game.difficulty, 30) - elapsed)
            elif game.phase == "paused":
                question_seconds_left = self.paused_remaining.get(game.pin)

        winner = None
        if game.status == "finished":
            winner = "A" if game.score_a > game.score_b else "B" if game.score_b > game.score_a else "draw"
        return GameStateOut(
            pin=game.pin,
            topic=game.topic,
            difficulty=game.difficulty,
            status=game.status,
            phase=game.phase,
            countdown_seconds=0,
            questions_per_team=game.questions_per_team,
            current_team=game.current_team,
            score_a=game.score_a,
            score_b=game.score_b,
            current_question=QuestionPublic(id=current_question.id, team=current_question.team, order_index=current_question.order_index, text=current_question.text, options=[current_question.option_1, current_question.option_2, current_question.option_3, current_question.option_4]) if current_question else None,
            players=[PlayerOut(id=p.id, name=p.name, team=p.team, is_host=p.is_host, is_captain=p.is_captain) for p in players],
            winner=winner,
            team_stats={
                "A": TeamStats(**self.team_stats[game.pin]["A"]),
                "B": TeamStats(**self.team_stats[game.pin]["B"]),
            },
            vote_percentages=self._vote_percentages(db, game),
            question_seconds_left=question_seconds_left,
        )

    async def broadcast_state(self, db: Session, game: Game) -> None:
        await self.manager.broadcast(game.pin, {"type": "state", "data": self.to_state(db, game).model_dump()})

    async def start_game(self, db: Session, pin: str, host_player_id: int) -> Game:
        game = self.get_game(db, pin)
        host = db.query(Player).filter(Player.id == host_player_id, Player.game_id == game.id, Player.active.is_(True)).first()
        if not host or not host.is_host:
            raise HTTPException(status_code=403, detail="Only host can start game")
        if game.status != "waiting":
            raise HTTPException(status_code=400, detail="Game already started")

        players = (
            db.query(Player)
            .filter(Player.game_id == game.id, Player.active.is_(True))
            .all()
        )
        if len(players) < 2:
            raise HTTPException(
                status_code=400,
                detail="Для старта нужен минимум 1 игрок в каждой команде",
            )

        self._assign_teams_and_captains(db, game)
        players = (
            db.query(Player)
            .filter(Player.game_id == game.id, Player.active.is_(True))
            .all()
        )
        teams = Counter([p.team for p in players])
        if teams.get("A", 0) == 0 or teams.get("B", 0) == 0:
            raise HTTPException(status_code=400, detail="Для старта нужен минимум 1 игрок в каждой команде")

        game.status = "in_progress"
        game.phase = "countdown"
        game.current_team = "A"
        game.current_index_a = 0
        game.current_index_b = 0
        db.commit()
        db.refresh(game)

        self.paused_remaining.pop(game.pin, None)
        self.paused_elapsed.pop(game.pin, None)

        for sec in [3, 2, 1]:
            payload = self.to_state(db, game).model_dump()
            payload["countdown_seconds"] = sec
            await self.manager.broadcast(game.pin, {"type": "state", "data": payload})
            await asyncio.sleep(1)

        game.phase = "question"
        game.question_started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(game)
        await self.broadcast_state(db, game)
        await self.start_timer(game.pin, game.difficulty)
        return game

    async def start_timer(self, pin: str, difficulty: str, remaining_seconds: int | None = None) -> None:
        existing = self.timer_tasks.get(pin)
        if existing and not existing.done():
            existing.cancel()

        async def timer_coroutine() -> None:
            try:
                sleep_seconds = remaining_seconds if remaining_seconds is not None else BASE_QUESTION_TIMEOUT.get(difficulty, 30)
                await asyncio.sleep(max(1, sleep_seconds))
                local_db = SessionLocal()
                try:
                    game = self.get_game(local_db, pin)
                    if game.status == "in_progress" and game.phase == "question":
                        await self.process_answer(local_db, pin, player_id=None, option_index=None, timeout=True)
                finally:
                    local_db.close()
            except asyncio.CancelledError:
                return

        self.timer_tasks[pin] = asyncio.create_task(timer_coroutine())

    async def cast_vote(self, db: Session, pin: str, player_id: int, choice: str) -> None:
        game = self.get_game(db, pin)
        if game.status != "in_progress" or game.phase != "question":
            return
        player = db.query(Player).filter(Player.id == player_id, Player.game_id == game.id, Player.active.is_(True)).first()
        if not player or player.team != game.current_team:
            return
        self.votes[pin][player_id] = choice
        await self.broadcast_state(db, game)

    async def transfer_captain(self, db: Session, pin: str, from_player_id: int, to_player_id: int) -> None:
        game = self.get_game(db, pin)
        frm = db.query(Player).filter(Player.id == from_player_id, Player.game_id == game.id).first()
        to = db.query(Player).filter(Player.id == to_player_id, Player.game_id == game.id).first()
        if not frm or not to or not frm.is_captain or frm.team != to.team:
            raise HTTPException(status_code=400, detail="Invalid captain transfer")
        frm.is_captain = False
        to.is_captain = True
        db.commit()
        await self.broadcast_state(db, game)

    async def process_answer(
        self,
        db: Session,
        pin: str,
        player_id: int | None,
        option_index: int | None,
        timeout: bool = False,
        skip: bool = False,
        system_action: bool = False,
    ) -> None:
        game = self.get_game(db, pin)
        if game.status != "in_progress" or game.phase != "question":
            return
        question = self.get_current_question(db, game)
        if not question or question.answered:
            return
        if not timeout and not system_action:
            player = db.query(Player).filter(Player.id == player_id, Player.game_id == game.id, Player.active.is_(True)).first()
            if not player:
                raise HTTPException(status_code=404, detail="Player not found")
            if player.team != game.current_team:
                raise HTTPException(status_code=400, detail="Not your team's turn")
            if not player.is_captain:
                raise HTTPException(status_code=400, detail="Только капитан может подтвердить")

        is_correct = (not timeout and not skip and option_index == question.correct_option)
        question.answered = True

        elapsed = 0
        if game.question_started_at:
            elapsed = max(0, int((datetime.now(timezone.utc) - game.question_started_at.replace(tzinfo=timezone.utc)).total_seconds()))

        team_key = game.current_team
        if timeout:
            self.team_stats[pin][team_key]["timeout"] += 1
        elif skip:
            self.team_stats[pin][team_key]["incorrect"] += 1
        elif is_correct:
            bonus = 2 if elapsed <= 8 else 1 if elapsed <= 15 else 0
            if team_key == "A":
                game.score_a += 1 + bonus
            else:
                game.score_b += 1 + bonus
            self.team_stats[pin][team_key]["correct"] += 1
            self.team_stats[pin][team_key]["speed_bonus"] += bonus
        else:
            self.team_stats[pin][team_key]["incorrect"] += 1

        if game.current_team == "A":
            game.current_index_a += 1
            game.current_team = "B"
        else:
            game.current_index_b += 1
            game.current_team = "A"

        self.votes[pin] = {}
        self.paused_remaining.pop(pin, None)
        self.paused_elapsed.pop(pin, None)

        if game.current_index_a >= game.questions_per_team and game.current_index_b >= game.questions_per_team:
            game.status = "finished"
            game.phase = "results"
            game.current_team = None
        else:
            game.phase = "question"
            game.question_started_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(game)
        await self.manager.broadcast(pin, {"type": "answer_result", "data": {"timeout": timeout, "skip": skip, "correct": is_correct, "correct_option": question.correct_option, "team": question.team, "question_id": question.id}})
        await self.broadcast_state(db, game)
        if game.status == "in_progress":
            await self.start_timer(pin, game.difficulty)

    async def host_control(
        self,
        db: Session,
        pin: str,
        host_player_id: int,
        action: str,
        target_player_id: int | None = None,
        topic: str | None = None,
        difficulty: str | None = None,
    ) -> None:
        game = self.get_game(db, pin)
        host = db.query(Player).filter(Player.id == host_player_id, Player.game_id == game.id).first()
        if not host or not host.is_host:
            raise HTTPException(status_code=403, detail="Only host")
        if action == "pause":
            if game.status == "in_progress" and game.phase == "question":
                elapsed = 0
                if game.question_started_at:
                    elapsed = max(0, int((datetime.now(timezone.utc) - game.question_started_at.replace(tzinfo=timezone.utc)).total_seconds()))
                timeout_seconds = BASE_QUESTION_TIMEOUT.get(game.difficulty, 30)
                self.paused_elapsed[pin] = elapsed
                self.paused_remaining[pin] = max(1, timeout_seconds - elapsed)
                game.phase = "paused"
                task = self.timer_tasks.get(pin)
                if task and not task.done():
                    task.cancel()
        elif action == "resume":
            if game.status == "in_progress" and game.phase == "paused":
                elapsed_before_pause = self.paused_elapsed.pop(pin, 0)
                remaining_seconds = self.paused_remaining.pop(pin, None)
                game.phase = "question"
                game.question_started_at = datetime.now(timezone.utc) - timedelta(seconds=elapsed_before_pause)
                await self.start_timer(pin, game.difficulty, remaining_seconds=remaining_seconds)
        elif action == "next_question":
            await self.process_answer(
                db,
                pin,
                player_id=host_player_id,
                option_index=None,
                skip=True,
                system_action=True,
            )
            return
        elif action == "kick" and target_player_id:
            target = db.query(Player).filter(Player.id == target_player_id, Player.game_id == game.id).first()
            if target:
                target.active = False
        elif action == "restart":
            if game.status != "finished":
                raise HTTPException(status_code=400, detail="Restart available only after game end")
            if topic and topic.strip():
                game.topic = topic.strip()
            if difficulty in {"easy", "medium", "hard"}:
                game.difficulty = difficulty

            db.query(Question).filter(Question.game_id == game.id).delete()

            # --- ОДИН ЗАПРОС ПРИ РЕСТАРТЕ ---
            total_count = game.questions_per_team * 2
            all_generated = generate_questions(game.topic, total_count, difficulty=game.difficulty)
            random.shuffle(all_generated)

            for i, q_data in enumerate(all_generated):
                team_label = "A" if i < game.questions_per_team else "B"
                order_idx = i if team_label == "A" else i - game.questions_per_team
                correct_idx = int(q_data["correct_option"]) - 1

                db.add(Question(
                    game_id=game.id,
                    team=team_label,
                    order_index=order_idx,
                    text=q_data["text"],
                    option_1=q_data["options"][0],
                    option_2=q_data["options"][1],
                    option_3=q_data["options"][2],
                    option_4=q_data["options"][3],
                    correct_option=correct_idx,
                ))

            game.status = "waiting"
            game.phase = "gathering"
            game.current_team = None
            game.current_index_a = 0
            game.current_index_b = 0
            game.score_a = 0
            game.score_b = 0
            game.question_started_at = None
            self.votes[pin] = {}
            self.team_stats[pin] = {
                "A": {"correct": 0, "incorrect": 0, "timeout": 0, "speed_bonus": 0},
                "B": {"correct": 0, "incorrect": 0, "timeout": 0, "speed_bonus": 0},
            }
            active_players = db.query(Player).filter(Player.game_id == game.id, Player.active.is_(True)).all()
            for pl in active_players:
                pl.team = None
                pl.is_captain = False
        db.commit()
        await self.broadcast_state(db, game)

    async def remove_player(self, db: Session, pin: str, player_id: int) -> None:
        game = db.query(Game).filter(Game.pin == pin).first()
        if not game:
            return
        player = db.query(Player).filter(Player.id == player_id, Player.game_id == game.id).first()
        if not player:
            return
        was_captain = player.is_captain
        team = player.team
        player.active = False
        player.is_captain = False
        db.commit()
        if was_captain and team:
            replacement = db.query(Player).filter(Player.game_id == game.id, Player.team == team, Player.active.is_(True)).order_by(Player.joined_at.asc()).first()
            if replacement:
                replacement.is_captain = True
                db.commit()
        await self.broadcast_state(db, game)

    def get_user_stats(self, db: Session, user_id: int, username: str) -> UserProfileStatsResponse:
        player_rows = db.query(Player).filter(Player.user_id == user_id).all()
        game_ids = sorted({p.game_id for p in player_rows})
        if not game_ids:
            return UserProfileStatsResponse(username=username, games_played=0, games_finished=0, wins=0, win_rate=0.0, average_team_score=0.0, recent_topics=[], favorite_team=None, frequent_teammates=[])
        games = db.query(Game).filter(Game.id.in_(game_ids)).order_by(Game.created_at.desc()).all()
        by_game = {p.game_id: p for p in player_rows}
        wins = 0
        finished = 0
        team_scores: list[int] = []
        teams = Counter()
        teammate_counter = Counter()
        for game in games:
            me = by_game.get(game.id)
            if not me or not me.team:
                continue
            teams[me.team] += 1
            team_scores.append(game.score_a if me.team == "A" else game.score_b)
            if game.status == "finished":
                finished += 1
                if (me.team == "A" and game.score_a > game.score_b) or (me.team == "B" and game.score_b > game.score_a):
                    wins += 1
            for t in db.query(Player).filter(Player.game_id == game.id, Player.id != me.id, Player.team == me.team).all():
                teammate_counter[t.name] += 1
        return UserProfileStatsResponse(
            username=username,
            games_played=len(game_ids),
            games_finished=finished,
            wins=wins,
            win_rate=round((wins / finished * 100.0), 1) if finished else 0.0,
            average_team_score=round(sum(team_scores) / len(team_scores), 2) if team_scores else 0.0,
            recent_topics=[g.topic for g in games[:5]],
            favorite_team=teams.most_common(1)[0][0] if teams else None,
            frequent_teammates=[TeammateStat(name=name, games_together=count) for name, count in teammate_counter.most_common(5)],
        )

    def get_rating(self, db: Session) -> RatingResponse:
        users = db.query(User).all()
        rows: list[RatingRow] = []
        for user in users:
            stats = self.get_user_stats(db, user.id, user.username)
            rows.append(RatingRow(user_id=user.id, username=user.username, wins=stats.wins, games_finished=stats.games_finished))
        rows.sort(key=lambda r: (r.wins, r.games_finished), reverse=True)
        return RatingResponse(rows=rows[:20])


game_service = GameService()
