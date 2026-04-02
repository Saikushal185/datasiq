"use client";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  fetchProgressPath,
  fetchProgressStats,
  fetchQuiz,
  fetchStreak,
  fetchBlitzFlashcards,
  fetchBossRoundFlashcards,
  fetchDueFlashcards,
  freezeStreak,
  recoverStreak,
  submitQuiz,
  submitFlashcardReview,
  ApiError,
  type FlashcardReviewRating,
  type FlashcardReviewRequest,
  type FlashcardReviewResponse,
  type ProgressPathResponse,
  type ProgressPathTopicResponse,
  type QuizResponse,
  type QuizSubmissionRequest,
  type QuizSubmissionResponse,
  type ProgressStatsResponse,
  type StreakActionResponse,
  type StreakRecoverRequest,
  type StreakResponse
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth";

const flashcardRootKey = ["flashcards"] as const;
const streakRootKey = ["streak"] as const;
const progressRootKey = ["progress"] as const;
const quizRootKey = ["quiz"] as const;

export const flashcardQueryKeys = {
  root: flashcardRootKey,
  due: [...flashcardRootKey, "due"] as const,
  blitz: [...flashcardRootKey, "blitz"] as const,
  boss: (topicId: string) => [...flashcardRootKey, "boss", topicId] as const
};

export const streakQueryKeys = {
  root: streakRootKey,
  detail: [...streakRootKey, "detail"] as const
};

export const progressQueryKeys = {
  root: progressRootKey,
  stats: [...progressRootKey, "stats"] as const,
  path: [...progressRootKey, "path"] as const
};

export const quizQueryKeys = {
  root: quizRootKey,
  detail: (topicId: string) => [...quizRootKey, "detail", topicId] as const
};

type AuthTokenSource = {
  getToken: () => Promise<string | null>;
  isLoaded: boolean | undefined;
  isSignedIn: boolean | undefined;
};

function getProgressPathQueryOptions(getToken: AuthTokenSource["getToken"]) {
  return {
    queryKey: progressQueryKeys.path,
    queryFn: async ({ signal }: { signal?: AbortSignal }) => {
      const token = await getToken();
      return fetchProgressPath({ signal, token });
    },
    staleTime: 30_000
  };
}

export async function prefetchProgressPathQuery(queryClient: QueryClient, auth: AuthTokenSource) {
  if (!auth.isLoaded || !auth.isSignedIn) {
    return;
  }

  await queryClient.prefetchQuery(getProgressPathQueryOptions(auth.getToken));
}

export function useDueFlashcardsQuery() {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: flashcardQueryKeys.due,
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchDueFlashcards({ signal, token });
    },
    staleTime: 30_000
  });
}

export function useBlitzFlashcardsQuery() {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: flashcardQueryKeys.blitz,
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchBlitzFlashcards({ signal, token });
    },
    staleTime: 30_000
  });
}

export function useBossRoundFlashcardsQuery(topicId: string) {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: flashcardQueryKeys.boss(topicId),
    enabled: isLoaded && isSignedIn && topicId.length > 0,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchBossRoundFlashcards(topicId, { signal, token });
    },
    staleTime: 30_000
  });
}

export function useSubmitFlashcardReviewMutation() {
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useMutation<FlashcardReviewResponse, ApiError, FlashcardReviewRequest>({
    mutationFn: async (payload) => {
      if (!isLoaded || !isSignedIn) {
        throw new Error("You must be signed in to review flashcards.");
      }

      const token = await getToken();
      return submitFlashcardReview(payload, { token });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: flashcardQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: streakQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: progressQueryKeys.root })
      ]);
    }
  });
}

export function useStreakQuery() {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: streakQueryKeys.detail,
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchStreak({ signal, token });
    },
    staleTime: 30_000
  });
}

export function useFreezeStreakMutation() {
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useMutation<StreakActionResponse, ApiError, void>({
    mutationFn: async () => {
      if (!isLoaded || !isSignedIn) {
        throw new Error("You must be signed in to protect your streak.");
      }

      const token = await getToken();
      return freezeStreak({ token });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: streakQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: progressQueryKeys.root })
      ]);
    }
  });
}

export function useRecoverStreakMutation() {
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useMutation<StreakActionResponse, ApiError, StreakRecoverRequest>({
    mutationFn: async (payload) => {
      if (!isLoaded || !isSignedIn) {
        throw new Error("You must be signed in to recover your streak.");
      }

      const token = await getToken();
      return recoverStreak(payload, { token });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: streakQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: progressQueryKeys.root })
      ]);
    }
  });
}

export function useProgressStatsQuery() {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: progressQueryKeys.stats,
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchProgressStats({ signal, token });
    },
    staleTime: 30_000
  });
}

export function useProgressPathQuery() {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    ...getProgressPathQueryOptions(getToken),
    enabled: isLoaded && isSignedIn
  });
}

export function useQuizQuery(topicId: string) {
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useQuery({
    queryKey: quizQueryKeys.detail(topicId),
    enabled: isLoaded && isSignedIn && topicId.trim().length > 0,
    queryFn: async ({ signal }) => {
      const token = await getToken();
      return fetchQuiz(topicId, { signal, token });
    },
    staleTime: 30_000
  });
}

export function useSubmitQuizMutation(quizId: string) {
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn } = useAppAuth();

  return useMutation<QuizSubmissionResponse, ApiError, QuizSubmissionRequest>({
    mutationFn: async (payload) => {
      if (!isLoaded || !isSignedIn) {
        throw new Error("You must be signed in to submit a quiz.");
      }

      if (!quizId.trim()) {
        throw new Error("Quiz ID is required before submission.");
      }

      const token = await getToken();
      return submitQuiz(quizId, payload, { token });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: quizQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: progressQueryKeys.root }),
        queryClient.invalidateQueries({ queryKey: streakQueryKeys.root })
      ]);
    }
  });
}

export type {
  ApiError,
  FlashcardReviewRating,
  FlashcardReviewRequest,
  FlashcardReviewResponse,
  ProgressPathResponse,
  ProgressPathTopicResponse,
  ProgressStatsResponse,
  QuizResponse,
  QuizSubmissionRequest,
  QuizSubmissionResponse,
  StreakActionResponse,
  StreakRecoverRequest,
  StreakResponse
};
