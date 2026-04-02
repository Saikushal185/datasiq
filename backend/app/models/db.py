from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, MetaData, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TopicDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TopicProgressStatus(str, Enum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class FlashcardCardType(str, Enum):
    RECALL = "recall"
    MCQ = "mcq"
    FILL_BLANK = "fill_blank"


class FlashcardDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class FlashcardReviewRating(str, Enum):
    FORGOT = "forgot"
    HARD = "hard"
    OKAY = "okay"
    EASY = "easy"


class QuizQuestionType(str, Enum):
    MCQ = "mcq"
    CODE_OUTPUT = "code_output"
    FILL_BLANK = "fill_blank"


class StreakEventType(str, Enum):
    MAINTAINED = "maintained"
    BROKEN = "broken"
    FROZEN = "frozen"
    RECOVERED = "recovered"


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    freeze_tokens_remaining: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    topic_progress_entries: Mapped[list[UserTopicProgress]] = relationship(back_populates="user")
    flashcard_reviews: Mapped[list[FlashcardReview]] = relationship(back_populates="user")
    quiz_attempts: Mapped[list[QuizAttempt]] = relationship(back_populates="user")
    streak_events: Mapped[list[StreakEvent]] = relationship(back_populates="user")


class Topic(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "topics"

    parent_topic_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[TopicDifficulty] = mapped_column(SqlEnum(TopicDifficulty, name="topic_difficulty"), nullable=False)

    parent: Mapped[Topic | None] = relationship(remote_side="Topic.id", back_populates="children")
    children: Mapped[list[Topic]] = relationship(back_populates="parent")
    user_progress_entries: Mapped[list[UserTopicProgress]] = relationship(back_populates="topic")
    flashcards: Mapped[list[Flashcard]] = relationship(back_populates="topic")
    quizzes: Mapped[list[Quiz]] = relationship(back_populates="topic")


class UserTopicProgress(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_topic_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[TopicProgressStatus] = mapped_column(
        SqlEnum(TopicProgressStatus, name="topic_progress_status"),
        default=TopicProgressStatus.LOCKED,
        nullable=False,
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="topic_progress_entries")
    topic: Mapped[Topic] = relationship(back_populates="user_progress_entries")


class Flashcard(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "flashcards"

    topic_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_type: Mapped[FlashcardCardType] = mapped_column(
        SqlEnum(FlashcardCardType, name="flashcard_card_type"),
        nullable=False,
    )
    difficulty: Mapped[FlashcardDifficulty] = mapped_column(
        SqlEnum(FlashcardDifficulty, name="flashcard_difficulty"),
        nullable=False,
    )
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="flashcards")
    options: Mapped[list[FlashcardOption]] = relationship(back_populates="card")
    reviews: Mapped[list[FlashcardReview]] = relationship(back_populates="card")


class FlashcardOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "flashcard_options"

    card_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False,
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    card: Mapped[Flashcard] = relationship(back_populates="options")


class FlashcardReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "flashcard_reviews"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[FlashcardReviewRating] = mapped_column(
        SqlEnum(FlashcardReviewRating, name="flashcard_review_rating"),
        nullable=False,
    )
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    difficulty_fsrs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="flashcard_reviews")
    card: Mapped[Flashcard] = relationship(back_populates="reviews")


class Quiz(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quizzes"

    topic_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    pass_threshold: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="quizzes")
    questions: Mapped[list[QuizQuestion]] = relationship(back_populates="quiz")
    attempts: Mapped[list[QuizAttempt]] = relationship(back_populates="quiz")


class QuizQuestion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_type: Mapped[QuizQuestionType] = mapped_column(
        SqlEnum(QuizQuestionType, name="quiz_question_type"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")


class QuizAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quiz_attempts"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="quiz_attempts")
    quiz: Mapped[Quiz] = relationship(back_populates="attempts")


class StreakEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "streak_events"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[StreakEventType] = mapped_column(
        SqlEnum(StreakEventType, name="streak_event_type"),
        nullable=False,
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    streak_value_at_event: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped[User] = relationship(back_populates="streak_events")


__all__ = [
    "Base",
    "Flashcard",
    "FlashcardCardType",
    "FlashcardDifficulty",
    "FlashcardOption",
    "FlashcardReview",
    "FlashcardReviewRating",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "QuizQuestionType",
    "StreakEvent",
    "StreakEventType",
    "Topic",
    "TopicDifficulty",
    "TopicProgressStatus",
    "User",
    "UserTopicProgress",
]
