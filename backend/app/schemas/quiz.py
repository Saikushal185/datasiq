from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.models.db import QuizQuestionType


class QuizTopicSummaryResponse(BaseModel):
    id: str
    title: str
    estimatedMinutes: int


class QuizOptionResponse(BaseModel):
    id: str
    text: str


class QuizQuestionResponse(BaseModel):
    id: str
    questionType: QuizQuestionType
    prompt: str
    options: list[QuizOptionResponse]
    codeSnippet: str | None = None
    hint: str | None = None


class QuizResponse(BaseModel):
    id: str
    title: str
    topic: QuizTopicSummaryResponse
    passThreshold: float
    questions: list[QuizQuestionResponse]


class QuizSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_required_answers(self) -> "QuizSubmitRequest":
        missing_or_empty = [question_id for question_id, answer in self.answers.items() if not answer.strip()]
        if missing_or_empty:
            missing_list = ", ".join(missing_or_empty)
            raise ValueError(f"Missing quiz answers for: {missing_list}")
        return self


class QuizQuestionBreakdownResponse(BaseModel):
    questionId: str
    selectedOptionId: str
    correctOptionId: str
    isCorrect: bool
    explanation: str


class QuizSubmitResponse(BaseModel):
    quizId: str
    score: float
    passed: bool
    masteryDelta: float
    recommendedAction: Literal["unlock_next_topic", "review_flashcards"]
    breakdown: list[QuizQuestionBreakdownResponse]
