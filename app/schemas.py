"""Схемы данных для приложения QuizBattle."""

import re

from pydantic import BaseModel, Field, field_validator

DISALLOWED_INPUT_CHARS_RE = re.compile(r"[<>]")
SQLI_PATTERN_RE = re.compile(r"(?i)(--|/\*|\*/|;|\b(select|union|insert|update|delete|drop|alter|truncate)\b)")
PIN_RE = re.compile(r"^[A-Z0-9]{6}$")


def _validate_safe_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is empty")
    if DISALLOWED_INPUT_CHARS_RE.search(cleaned):
        raise ValueError(f"{field_name} contains forbidden characters")
    if SQLI_PATTERN_RE.search(cleaned):
        raise ValueError(f"{field_name} contains suspicious SQL patterns")
    return cleaned


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_safe_text(value, "username")


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_safe_text(value, "username")


class AuthResponse(BaseModel):
    user_id: int
    username: str


class CreateGameRequest(BaseModel):
    host_name: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=2, max_length=255)
    questions_per_team: int = Field(ge=5, le=7)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    user_id: int | None = None

    @field_validator("host_name")
    @classmethod
    def validate_host_name(cls, value: str) -> str:
        return _validate_safe_text(value, "host_name")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        return _validate_safe_text(value, "topic")


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    user_id: int | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_safe_text(value, "name")


class StartGameRequest(BaseModel):
    host_player_id: int


class PlayerOut(BaseModel):
    id: int
    name: str
    team: str | None
    is_host: bool
    is_captain: bool


class QuestionPublic(BaseModel):
    id: int
    team: str
    order_index: int
    text: str
    options: list[str]


class TeamStats(BaseModel):
    correct: int
    incorrect: int
    timeout: int
    speed_bonus: int


class GameStateOut(BaseModel):
    pin: str
    topic: str
    difficulty: str
    status: str
    phase: str
    countdown_seconds: int
    questions_per_team: int
    current_team: str | None
    score_a: int
    score_b: int
    current_question: QuestionPublic | None
    players: list[PlayerOut]
    winner: str | None
    team_stats: dict[str, TeamStats]
    vote_percentages: dict[str, int]
    question_seconds_left: int | None = None


class CreateGameResponse(BaseModel):
    pin: str
    host_player_id: int
    state: GameStateOut


class JoinGameResponse(BaseModel):
    player_id: int
    state: GameStateOut


class TeammateStat(BaseModel):
    name: str
    games_together: int


class UserProfileStatsResponse(BaseModel):
    username: str
    games_played: int
    games_finished: int
    wins: int
    win_rate: float
    average_team_score: float
    recent_topics: list[str]
    favorite_team: str | None
    frequent_teammates: list[TeammateStat]


class RatingRow(BaseModel):
    user_id: int
    username: str
    wins: int
    games_finished: int


class RatingResponse(BaseModel):
    rows: list[RatingRow]
