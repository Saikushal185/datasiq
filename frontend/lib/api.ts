import * as Sentry from "@sentry/nextjs";

export type FlashcardReviewRating = "forgot" | "hard" | "okay" | "easy";
export type FlashcardCardType = "recall" | "mcq" | "fill_blank";
export type FlashcardDifficulty = "easy" | "medium" | "hard";

export type FlashcardOptionResponse = {
  id: string;
  text: string;
};

export type FlashcardReviewStateResponse = {
  dueNow: boolean;
  streakBonus: boolean;
  ratingOptions: FlashcardReviewRating[];
};

export type FlashcardCardResponse = {
  id: string;
  topicId: string;
  topicTitle: string;
  cardType: FlashcardCardType;
  difficulty: FlashcardDifficulty;
  front: string;
  back: string;
  hint?: string | null;
  options: FlashcardOptionResponse[];
  xpReward: number;
  reviewState?: FlashcardReviewStateResponse | null;
};

export type FlashcardsDueResponse = {
  cards: FlashcardCardResponse[];
  totalDue: number;
  sessionFocus: string;
};

export type FlashcardsBlitzResponse = {
  topicId: string;
  durationSeconds: number;
  streakMultiplier: number;
  cards: FlashcardCardResponse[];
};

export type FlashcardTopicSummaryResponse = {
  id: string;
  title: string;
  completed: boolean;
};

export type QuizQuestionType = "mcq" | "code_output" | "fill_blank";

export type QuizOptionResponse = {
  id: string;
  text: string;
};

export type QuizTopicResponse = {
  id: string;
  title: string;
  estimatedMinutes: number;
};

export type QuizQuestionResponse = {
  id: string;
  questionType: QuizQuestionType;
  prompt: string;
  options: QuizOptionResponse[];
  codeSnippet: string | null;
  hint: string | null;
};

export type QuizResponse = {
  id: string;
  title: string;
  topic: QuizTopicResponse;
  passThreshold: number;
  questions: QuizQuestionResponse[];
};

export type QuizRecommendedAction = "unlock_next_topic" | "review_flashcards";

export type QuizSubmissionRequest = {
  answers: Record<string, string>;
};

export type QuizSubmissionBreakdownResponse = {
  questionId: string;
  selectedOptionId: string;
  correctOptionId: string;
  isCorrect: boolean;
  explanation: string;
};

export type QuizSubmissionResponse = {
  quizId: string;
  score: number;
  passed: boolean;
  masteryDelta: number;
  recommendedAction: QuizRecommendedAction;
  breakdown: QuizSubmissionBreakdownResponse[];
};

export type FlashcardsBossResponse = {
  topic: FlashcardTopicSummaryResponse;
  passThreshold: number;
  cards: FlashcardCardResponse[];
  revisitConcepts: string[];
};

export type FlashcardReviewRequest = {
  cardId: string;
  rating: FlashcardReviewRating;
  elapsedMs?: number;
};

export type FlashcardReviewResponse = {
  cardId: string;
  rating: FlashcardReviewRating;
  nextReviewAt: string;
  intervalDays: number;
  celebrate: boolean;
  xpAwarded: number;
  reviewsCompletedThisSession: number | null;
};

export type TopicProgressStatus = "locked" | "available" | "in_progress" | "completed";

export type WeeklyBarState = "done" | "today" | "warning" | "idle";

export type StreakGraceWindowResponse = {
  active: boolean;
  expiresAt: string | null;
  missedDate: string | null;
};

export type StreakRecoveryResponse = {
  eligible: boolean;
  thresholdMet: boolean;
  applied: boolean;
  reviewsRequired: number;
  reviewsCompleted: number;
  reviewsRemaining: number;
};

export type StreakRageModalResponse = {
  show: boolean;
  reason: string;
  cta: string;
};

export type WeeklyBarDayResponse = {
  date: string;
  label: string;
  state: WeeklyBarState;
};

export type StreakResponse = {
  currentStreak: number;
  longestStreak: number;
  freezeTokensRemaining: number;
  freezeApplied: boolean;
  todayCompleted: boolean;
  lastActivityDate: string | null;
  protectedStreakDate: string | null;
  graceWindow: StreakGraceWindowResponse;
  recovery: StreakRecoveryResponse;
  rageModal: StreakRageModalResponse;
  weeklyBar: WeeklyBarDayResponse[];
};

export type StreakAction = "freeze" | "recover";

export type StreakRecoverRequest = {
  reviewsCompleted: number;
};

export type StreakActionResponse = {
  action: StreakAction;
  message: string;
  streak: StreakResponse;
};

export type ProgressStatsTopicResponse = {
  topicId: string;
  title: string;
  masteryScore: number;
  status: TopicProgressStatus;
};

export type ProgressStatsResponse = {
  currentStreak: number;
  longestStreak: number;
  cardsDueToday: number;
  topics: ProgressStatsTopicResponse[];
};

export type ProgressPathTopicResponse = {
  id: string;
  title: string;
  orderIndex: number;
  difficulty: "beginner" | "intermediate" | "advanced";
  status: TopicProgressStatus;
  masteryScore: number;
  lastStudiedAt: string | null;
};

export type ProgressPathResponse = {
  currentTopicId: string | null;
  topics: ProgressPathTopicResponse[];
};

export class ApiError extends Error {
  public readonly status: number;
  public readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export type ApiOptions = {
  token?: string | null;
  signal?: AbortSignal;
};

const API_PREFIX = "/api/v1";

function getApiBaseUrl(): string {
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return rawBaseUrl.endsWith("/") ? rawBaseUrl.slice(0, -1) : rawBaseUrl;
}

function reportApiError(error: unknown, context: { path: string; method: string }): void {
  if (error instanceof ApiError && error.status < 500) {
    return;
  }
  if (error instanceof Error && error.name === "AbortError") {
    return;
  }

  Sentry.withScope((scope) => {
    scope.setTag("api.path", context.path);
    scope.setTag("api.method", context.method);
    scope.setTag("api.base_url", getApiBaseUrl());

    if (error instanceof ApiError) {
      scope.setTag("api.status", String(error.status));
      scope.setExtra("api.payload", error.payload);
    }

    scope.setLevel("error");
    Sentry.captureException(error instanceof Error ? error : new Error("Unknown API failure."));
  });
}

async function apiFetch<T>(path: string, init: RequestInit, options?: ApiOptions): Promise<T> {
  const method = init.method ?? "GET";

  try {
    const response = await fetch(new URL(`${API_PREFIX}${path}`, getApiBaseUrl()), {
      ...init,
      signal: options?.signal,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
        ...(options?.token ? { Authorization: `Bearer ${options.token}` } : {})
      }
    });

    if (!response.ok) {
      const responseClone = response.clone();
      const contentType = response.headers.get("content-type") ?? "";
      let payload: unknown = null;

      try {
        payload = contentType.includes("application/json") ? await response.json() : await response.text();
      } catch {
        payload = await responseClone.text().catch(() => null);
      }

      const message =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : `Request failed with status ${response.status}`;
      const apiError = new ApiError(message, response.status, payload);
      reportApiError(apiError, { path, method });
      throw apiError;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    reportApiError(error, { path, method });
    throw error;
  }
}

export async function fetchDueFlashcards(options?: ApiOptions): Promise<FlashcardsDueResponse> {
  return apiFetch<FlashcardsDueResponse>("/flashcards/due", { method: "GET" }, options);
}

export async function fetchBlitzFlashcards(options?: ApiOptions): Promise<FlashcardsBlitzResponse> {
  return apiFetch<FlashcardsBlitzResponse>("/flashcards/blitz", { method: "GET" }, options);
}

export async function fetchBossRoundFlashcards(topicId: string, options?: ApiOptions): Promise<FlashcardsBossResponse> {
  return apiFetch<FlashcardsBossResponse>(`/flashcards/boss/${encodeURIComponent(topicId)}`, { method: "GET" }, options);
}

export async function submitFlashcardReview(payload: FlashcardReviewRequest, options?: ApiOptions): Promise<FlashcardReviewResponse> {
  return apiFetch<FlashcardReviewResponse>(
    "/flashcards/review",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        cardId: payload.cardId,
        rating: payload.rating,
        elapsedMs: payload.elapsedMs ?? 0
      })
    },
    options
  );
}

export async function fetchStreak(options?: ApiOptions): Promise<StreakResponse> {
  return apiFetch<StreakResponse>("/streak", { method: "GET" }, options);
}

export async function freezeStreak(options?: ApiOptions): Promise<StreakActionResponse> {
  return apiFetch<StreakActionResponse>(
    "/streak/freeze",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    },
    options
  );
}

export async function recoverStreak(payload: StreakRecoverRequest, options?: ApiOptions): Promise<StreakActionResponse> {
  return apiFetch<StreakActionResponse>(
    "/streak/recover",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    },
    options
  );
}

export async function fetchProgressStats(options?: ApiOptions): Promise<ProgressStatsResponse> {
  return apiFetch<ProgressStatsResponse>("/progress/stats", { method: "GET" }, options);
}

export async function fetchProgressPath(options?: ApiOptions): Promise<ProgressPathResponse> {
  return apiFetch<ProgressPathResponse>("/progress/path", { method: "GET" }, options);
}

export async function fetchQuiz(topicId: string, options?: ApiOptions): Promise<QuizResponse> {
  return apiFetch<QuizResponse>(`/quiz/${encodeURIComponent(topicId)}`, { method: "GET" }, options);
}

export async function submitQuiz(
  quizId: string,
  payload: QuizSubmissionRequest,
  options?: ApiOptions
): Promise<QuizSubmissionResponse> {
  return apiFetch<QuizSubmissionResponse>(
    `/quiz/${encodeURIComponent(quizId)}/submit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    },
    options
  );
}
