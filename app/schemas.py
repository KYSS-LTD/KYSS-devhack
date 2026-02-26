"""
Схемы данных для приложения QuizBattle.

Определяет Pydantic схемы для валидации и сериализации данных,
используемые в API эндпоинтах.
"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """
    Схема запроса для регистрации пользователя.

    Атрибуты:
        username (str): Имя пользователя (от 3 до 50 символов)
        password (str): Пароль пользователя (от 6 до 128 символов)
    """

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """
    Схема запроса для входа пользователя.

    Атрибуты:
        username (str): Имя пользователя (от 3 до 50 символов)
        password (str): Пароль пользователя (от 6 до 128 символов)
    """

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class AuthResponse(BaseModel):
    """
    Схема ответа для аутентификации.

    Атрибуты:
        user_id (int): Идентификатор пользователя
        username (str): Имя пользователя
    """

    user_id: int
    username: str


class CreateGameRequest(BaseModel):
    """
    Схема запроса для создания новой игры.

    Атрибуты:
        host_name (str): Имя хоста игры (от 1 до 80 символов)
        topic (str): Тема игры (от 2 до 255 символов)
        questions_per_team (int): Количество вопросов на команду (от 5 до 7)
        user_id (int | None): Идентификатор пользователя-хоста (если зарегистрирован)
    """

    host_name: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=2, max_length=255)
    questions_per_team: int = Field(ge=5, le=7)
    user_id: int | None = None


class JoinGameRequest(BaseModel):
    """
    Схема запроса для присоединения к игре.

    Атрибуты:
        name (str): Имя игрока (от 1 до 80 символов)
        user_id (int | None): Идентификатор зарегистрированного пользователя
    """

    name: str = Field(min_length=1, max_length=80)
    user_id: int | None = None


class StartGameRequest(BaseModel):
    """
    Схема запроса для начала игры.

    Атрибуты:
        host_player_id (int): Идентификатор игрока-хоста
    """

    host_player_id: int


class PlayerOut(BaseModel):
    """
    Схема для отображения информации об игроке.

    Атрибуты:
        id (int): Идентификатор игрока
        name (str): Имя игрока
        team (str): Команда игрока (A или B)
        is_host (bool): Является ли игрок хостом
    """

    id: int
    name: str
    team: str
    is_host: bool


class QuestionPublic(BaseModel):
    """
    Схема для отображения публичной информации о вопросе.

    Атрибуты:
        id (int): Идентификатор вопроса
        team (str): Команда, которой предназначен вопрос
        order_index (int): Порядковый номер вопроса
        text (str): Текст вопроса
        options (list[str]): Варианты ответов
    """

    id: int
    team: str
    order_index: int
    text: str
    options: list[str]


class GameStateOut(BaseModel):
    """
    Схема для отображения состояния игры.

    Атрибуты:
        pin (str): 6-символьный код игры
        topic (str): Тема игры
        status (str): Статус игры
        questions_per_team (int): Количество вопросов на команду
        current_team (str | None): Текущая команда
        score_a (int): Счет команды A
        score_b (int): Счет команды B
        current_question (QuestionPublic | None): Текущий вопрос
        players (list[PlayerOut]): Список игроков
        winner (str | None): Победитель игры
    """

    pin: str
    topic: str
    status: str
    questions_per_team: int
    current_team: str | None
    score_a: int
    score_b: int
    current_question: QuestionPublic | None
    players: list[PlayerOut]
    winner: str | None


class CreateGameResponse(BaseModel):
    """
    Схема ответа для создания игры.

    Атрибуты:
        pin (str): 6-символьный код игры
        host_player_id (int): Идентификатор игрока-хоста
        state (GameStateOut): Состояние игры
    """

    pin: str
    host_player_id: int
    state: GameStateOut


class JoinGameResponse(BaseModel):
    """
    Схема ответа для присоединения к игре.

    Атрибуты:
        player_id (int): Идентификатор игрока
        state (GameStateOut): Состояние игры
    """

    player_id: int
    state: GameStateOut


class TeammateStat(BaseModel):
    """
    Схема для статистики teammate.

    Атрибуты:
        name (str): Имя игрока
        games_together (int): Количество игр вместе
    """

    name: str
    games_together: int


class UserProfileStatsResponse(BaseModel):
    """
    Схема ответа для статистики пользователя.

    Атрибуты:
        username (str): Имя пользователя
        games_played (int): Количество сыгранных игр
        games_finished (int): Количество завершенных игр
        wins (int): Количество побед
        win_rate (float): Процент побед
        average_team_score (float): Средний счет команды
        recent_topics (list[str]): Недавние темы игр
        favorite_team (str | None): Предпочитаемая команда
        frequent_teammates (list[TeammateStat]): Частые напарники
    """

    username: str
    games_played: int
    games_finished: int
    wins: int
    win_rate: float
    average_team_score: float
    recent_topics: list[str]
    favorite_team: str | None
    frequent_teammates: list[TeammateStat]
