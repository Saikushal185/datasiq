from uuid import UUID

from sqlalchemy import UniqueConstraint

from backend.app.models.db import (
    Base,
    FlashcardCardType,
    FlashcardDifficulty,
    FlashcardReviewRating,
    QuizQuestionType,
    StreakEventType,
    TopicDifficulty,
    TopicProgressStatus,
)


def _enum_values(enum_cls: type) -> set[str]:
    return {member.value for member in enum_cls}


def _column_names(table_name: str) -> set[str]:
    return set(Base.metadata.tables[table_name].columns.keys())


def _foreign_key_targets(table_name: str, column_name: str) -> set[str]:
    column = Base.metadata.tables[table_name].c[column_name]
    return {foreign_key.target_fullname for foreign_key in column.foreign_keys}


def _unique_constraint_sets(table_name: str) -> set[frozenset[str]]:
    table = Base.metadata.tables[table_name]
    constraint_sets: set[frozenset[str]] = set()
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            constraint_sets.add(frozenset(column.name for column in constraint.columns))
    return constraint_sets


def _column_default(table_name: str, column_name: str) -> object | None:
    default = Base.metadata.tables[table_name].c[column_name].default
    if default is None:
        return None
    return default.arg


def test_expected_tables_exist() -> None:
    table_names = set(Base.metadata.tables.keys())

    assert table_names == {
        "users",
        "topics",
        "user_topic_progress",
        "flashcards",
        "flashcard_options",
        "flashcard_reviews",
        "quizzes",
        "quiz_questions",
        "quiz_attempts",
        "streak_events",
    }


def test_expected_enum_domains_are_covered() -> None:
    assert _enum_values(TopicDifficulty) == {"beginner", "intermediate", "advanced"}
    assert _enum_values(TopicProgressStatus) == {
        "locked",
        "available",
        "in_progress",
        "completed",
    }
    assert _enum_values(FlashcardCardType) == {"recall", "mcq", "fill_blank"}
    assert _enum_values(FlashcardDifficulty) == {"easy", "medium", "hard"}
    assert _enum_values(FlashcardReviewRating) == {"forgot", "hard", "okay", "easy"}
    assert _enum_values(QuizQuestionType) == {"mcq", "code_output", "fill_blank"}
    assert _enum_values(StreakEventType) == {"maintained", "broken", "frozen", "recovered"}

    topics = Base.metadata.tables["topics"]
    progress = Base.metadata.tables["user_topic_progress"]
    flashcards = Base.metadata.tables["flashcards"]
    reviews = Base.metadata.tables["flashcard_reviews"]
    questions = Base.metadata.tables["quiz_questions"]
    events = Base.metadata.tables["streak_events"]

    assert topics.c.difficulty.type.enum_class is TopicDifficulty
    assert progress.c.status.type.enum_class is TopicProgressStatus
    assert flashcards.c.card_type.type.enum_class is FlashcardCardType
    assert flashcards.c.difficulty.type.enum_class is FlashcardDifficulty
    assert reviews.c.rating.type.enum_class is FlashcardReviewRating
    assert questions.c.question_type.type.enum_class is QuizQuestionType
    assert events.c.event_type.type.enum_class is StreakEventType


def test_expected_columns_and_defaults_match_spec() -> None:
    assert _column_names("users") == {
        "id",
        "clerk_id",
        "email",
        "current_streak",
        "longest_streak",
        "freeze_tokens_remaining",
        "last_activity_date",
        "created_at",
    }
    assert _column_names("topics") == {
        "id",
        "parent_topic_id",
        "title",
        "description",
        "order_index",
        "difficulty",
    }
    assert _column_names("user_topic_progress") == {
        "id",
        "user_id",
        "topic_id",
        "status",
        "mastery_score",
        "last_studied_at",
    }
    assert _column_names("flashcards") == {
        "id",
        "topic_id",
        "card_type",
        "difficulty",
        "front",
        "back",
        "created_at",
    }
    assert _column_names("flashcard_options") == {
        "id",
        "card_id",
        "option_text",
        "is_correct",
    }
    assert _column_names("flashcard_reviews") == {
        "id",
        "user_id",
        "card_id",
        "rating",
        "interval_days",
        "stability",
        "difficulty_fsrs",
        "reviewed_at",
        "next_review_at",
    }
    assert _column_names("quizzes") == {
        "id",
        "topic_id",
        "title",
        "pass_threshold",
    }
    assert _column_names("quiz_questions") == {
        "id",
        "quiz_id",
        "question_type",
        "question_text",
        "correct_answer",
        "explanation",
    }
    assert _column_names("quiz_attempts") == {
        "id",
        "user_id",
        "quiz_id",
        "score",
        "passed",
        "attempted_at",
    }
    assert _column_names("streak_events") == {
        "id",
        "user_id",
        "event_type",
        "event_date",
        "streak_value_at_event",
    }

    users = Base.metadata.tables["users"]
    quizzes = Base.metadata.tables["quizzes"]
    progress = Base.metadata.tables["user_topic_progress"]

    assert users.c.email.nullable is True
    assert _column_default("users", "freeze_tokens_remaining") == 1
    assert _column_default("quizzes", "pass_threshold") == 0.7
    assert _column_default("user_topic_progress", "status") is TopicProgressStatus.LOCKED
    assert _column_default("user_topic_progress", "mastery_score") == 0.0

    assert quizzes.c.topic_id.unique is None


def test_expected_primary_and_foreign_keys_exist() -> None:
    for table_name in Base.metadata.tables:
        id_column = Base.metadata.tables[table_name].c.id
        assert id_column.primary_key is True
        assert id_column.type.python_type is UUID

    assert _foreign_key_targets("topics", "parent_topic_id") == {"topics.id"}
    assert _foreign_key_targets("user_topic_progress", "user_id") == {"users.id"}
    assert _foreign_key_targets("user_topic_progress", "topic_id") == {"topics.id"}
    assert _foreign_key_targets("flashcards", "topic_id") == {"topics.id"}
    assert _foreign_key_targets("flashcard_options", "card_id") == {"flashcards.id"}
    assert _foreign_key_targets("flashcard_reviews", "user_id") == {"users.id"}
    assert _foreign_key_targets("flashcard_reviews", "card_id") == {"flashcards.id"}
    assert _foreign_key_targets("quizzes", "topic_id") == {"topics.id"}
    assert _foreign_key_targets("quiz_questions", "quiz_id") == {"quizzes.id"}
    assert _foreign_key_targets("quiz_attempts", "user_id") == {"users.id"}
    assert _foreign_key_targets("quiz_attempts", "quiz_id") == {"quizzes.id"}
    assert _foreign_key_targets("streak_events", "user_id") == {"users.id"}

    assert Base.metadata.tables["users"].c.clerk_id.unique is True
    assert frozenset({"user_id", "topic_id"}) in _unique_constraint_sets("user_topic_progress")
