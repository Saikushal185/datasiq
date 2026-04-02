from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from json import JSONDecodeError
import random
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.models.db import Quiz, QuizAttempt, QuizQuestion, QuizQuestionType, Topic, TopicProgressStatus, User, UserTopicProgress
from backend.app.schemas.quiz import (
    QuizOptionResponse,
    QuizQuestionBreakdownResponse,
    QuizQuestionResponse,
    QuizResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizTopicSummaryResponse,
)
from backend.app.services.adaptive_service import TopicProgressSnapshot, evaluate_quiz_attempt
from backend.app.services.streak_service import apply_study_activity, evaluate_streak


router = APIRouter(prefix="/quiz", tags=["quiz"])


@dataclass(frozen=True, slots=True)
class ParsedQuestion:
    prompt: str
    code_snippet: str | None
    options: list[QuizOptionResponse]
    correct_answer: str


@router.get("/{topicId}", response_model=QuizResponse)
async def get_quiz(
    topicId: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QuizResponse:
    del current_user
    topic_id = _parse_uuid(topicId, detail="Invalid topic id.")
    quiz = await _load_quiz_for_topic(session, topic_id=topic_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    return QuizResponse(
        id=str(quiz.id),
        title=quiz.title,
        topic=QuizTopicSummaryResponse(
            id=str(quiz.topic.id),
            title=quiz.topic.title,
            estimatedMinutes=max(5, len(quiz.questions) * 2),
        ),
        passThreshold=quiz.pass_threshold,
        questions=[_build_question_response(question) for question in _ordered_questions(quiz.questions)],
    )


@router.post("/{quizId}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    quizId: str,
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QuizSubmitResponse:
    quiz_id = _parse_uuid(quizId, detail="Invalid quiz id.")
    quiz = await _load_quiz_for_id(session, quiz_id=quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    questions = _ordered_questions(quiz.questions)
    missing_answers = [str(question.id) for question in questions if not payload.answers.get(str(question.id), "").strip()]
    if missing_answers:
        missing_list = ", ".join(missing_answers)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Missing quiz answers for: {missing_list}",
        )

    breakdown: list[QuizQuestionBreakdownResponse] = []
    for question in questions:
        parsed_question = _parse_question(question)
        selected_answer = payload.answers[str(question.id)]
        breakdown.append(
            QuizQuestionBreakdownResponse(
                questionId=str(question.id),
                selectedOptionId=selected_answer,
                correctOptionId=parsed_question.correct_answer,
                isCorrect=selected_answer == parsed_question.correct_answer,
                explanation=question.explanation or "",
            )
        )

    correct_answers = sum(1 for item in breakdown if item.isCorrect)
    score = correct_answers / len(breakdown)
    passed = score >= quiz.pass_threshold
    attempted_at = _utcnow()
    streak_state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining,
        now_utc=attempted_at,
        recovery_reviews_completed=0,
    )
    current_progress = await _get_or_create_topic_progress(
        session,
        user_id=current_user.id,
        topic_id=quiz.topic_id,
        default_status=TopicProgressStatus.IN_PROGRESS,
    )
    previous_mastery = current_progress.mastery_score
    previous_scores = await _load_topic_scores(session, user_id=current_user.id, topic_id=quiz.topic_id)
    ordered_topic_snapshots = await _load_topic_snapshots(session, user_id=current_user.id)
    adaptive_outcome = evaluate_quiz_attempt(
        topic_id=quiz.topic_id,
        current_status=current_progress.status,
        current_order_index=quiz.topic.order_index,
        quiz_scores=[*previous_scores, score],
        ordered_topics=ordered_topic_snapshots,
    )

    current_progress.status = adaptive_outcome.updated_status
    current_progress.mastery_score = adaptive_outcome.mastery_score
    current_progress.last_studied_at = attempted_at
    if adaptive_outcome.should_unlock_next_topic and adaptive_outcome.next_topic is not None:
        next_progress = await _get_or_create_topic_progress(
            session,
            user_id=current_user.id,
            topic_id=adaptive_outcome.next_topic.topic_id,
            default_status=TopicProgressStatus.LOCKED,
        )
        if next_progress.status == TopicProgressStatus.LOCKED:
            next_progress.status = TopicProgressStatus.AVAILABLE

    if not streak_state.grace_window.active:
        activity = apply_study_activity(
            current_streak=user.current_streak,
            longest_streak=user.longest_streak,
            last_activity_at=user.last_activity_date,
            now_utc=attempted_at,
        )
        user.current_streak = activity.current_streak
        user.longest_streak = activity.longest_streak
        user.last_activity_date = activity.last_activity_date

    session.add(
        QuizAttempt(
            user_id=current_user.id,
            quiz_id=quiz.id,
            score=score,
            passed=passed,
            attempted_at=attempted_at,
        )
    )
    await session.commit()

    return QuizSubmitResponse(
        quizId=str(quiz.id),
        score=score,
        passed=passed,
        masteryDelta=adaptive_outcome.mastery_score - previous_mastery,
        recommendedAction="unlock_next_topic" if adaptive_outcome.should_unlock_next_topic else "review_flashcards",
        breakdown=breakdown,
    )


async def _load_quiz_for_topic(session: AsyncSession, *, topic_id: UUID) -> Quiz | None:
    statement = (
        select(Quiz)
        .options(joinedload(Quiz.topic), selectinload(Quiz.questions))
        .where(Quiz.topic_id == topic_id)
    )
    return await session.scalar(statement)


async def _load_quiz_for_id(session: AsyncSession, *, quiz_id: UUID) -> Quiz | None:
    statement = (
        select(Quiz)
        .options(joinedload(Quiz.topic), selectinload(Quiz.questions))
        .where(Quiz.id == quiz_id)
    )
    return await session.scalar(statement)


async def _load_topic_scores(session: AsyncSession, *, user_id: UUID, topic_id: UUID) -> list[float]:
    statement = (
        select(QuizAttempt.score)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .where(
            QuizAttempt.user_id == user_id,
            Quiz.topic_id == topic_id,
        )
        .order_by(QuizAttempt.attempted_at)
    )
    return list(await session.scalars(statement))


async def _load_topic_snapshots(session: AsyncSession, *, user_id: UUID) -> list[TopicProgressSnapshot]:
    topics = list(await session.scalars(select(Topic).order_by(Topic.order_index)))
    progress_entries = list(
        await session.scalars(select(UserTopicProgress).where(UserTopicProgress.user_id == user_id))
    )
    progress_by_topic_id = {entry.topic_id: entry for entry in progress_entries}
    return [
        TopicProgressSnapshot(
            topic_id=topic.id,
            order_index=topic.order_index,
            status=progress_by_topic_id.get(topic.id, _locked_progress_snapshot()).status,
        )
        for topic in topics
    ]


async def _get_or_create_topic_progress(
    session: AsyncSession,
    *,
    user_id: UUID,
    topic_id: UUID,
    default_status: TopicProgressStatus,
) -> UserTopicProgress:
    progress = await session.scalar(
        select(UserTopicProgress).where(
            UserTopicProgress.user_id == user_id,
            UserTopicProgress.topic_id == topic_id,
        )
    )
    if progress is not None:
        return progress

    progress = UserTopicProgress(
        user_id=user_id,
        topic_id=topic_id,
        status=default_status,
        mastery_score=0.0,
    )
    session.add(progress)
    await session.flush()
    return progress


def _build_question_response(question: QuizQuestion) -> QuizQuestionResponse:
    parsed_question = _parse_question(question)
    return QuizQuestionResponse(
        id=str(question.id),
        questionType=question.question_type,
        prompt=parsed_question.prompt,
        options=_shuffle_options(question.id, parsed_question.options),
        codeSnippet=parsed_question.code_snippet,
        hint=question.explanation,
    )


def _parse_question(question: QuizQuestion) -> ParsedQuestion:
    if question.question_type in {QuizQuestionType.MCQ, QuizQuestionType.CODE_OUTPUT}:
        data = _parse_answer_payload(question.correct_answer)
        prompt = question.question_text
        code_snippet = None
        if question.question_type == QuizQuestionType.CODE_OUTPUT:
            prompt = "What does this code output?"
            code_snippet = question.question_text
        return ParsedQuestion(
            prompt=prompt,
            code_snippet=code_snippet,
            options=[
                QuizOptionResponse(id=str(option["id"]), text=str(option["text"]))
                for option in data["options"]
            ],
            correct_answer=str(data["correctOptionId"]),
        )

    return ParsedQuestion(
        prompt=question.question_text,
        code_snippet=None,
        options=[],
        correct_answer=question.correct_answer,
    )


def _parse_answer_payload(raw_value: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_value)
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz question answer payload is invalid.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz question answer payload is invalid.",
        )
    correct_option_id = payload.get("correctOptionId")
    options = payload.get("options")
    if not isinstance(correct_option_id, str) or not isinstance(options, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz question answer payload is invalid.",
        )
    return {"correctOptionId": correct_option_id, "options": options}


def _shuffle_options(question_id: UUID, options: list[QuizOptionResponse]) -> list[QuizOptionResponse]:
    if len(options) < 2:
        return options
    randomizer = random.Random(str(question_id))
    return randomizer.sample(options, k=len(options))


def _ordered_questions(questions: list[QuizQuestion]) -> list[QuizQuestion]:
    question_type_order = {
        QuizQuestionType.MCQ: 0,
        QuizQuestionType.CODE_OUTPUT: 1,
        QuizQuestionType.FILL_BLANK: 2,
    }
    return sorted(
        questions,
        key=lambda question: (
            question_type_order.get(question.question_type, len(question_type_order)),
            question.question_text,
            str(question.id),
        ),
    )


def _parse_uuid(raw_value: str, *, detail: str) -> UUID:
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc


def _locked_progress_snapshot() -> TopicProgressSnapshot:
    return TopicProgressSnapshot(topic_id=UUID(int=0), order_index=0, status=TopicProgressStatus.LOCKED)


def _utcnow() -> Any:
    return datetime.now(timezone.utc)
