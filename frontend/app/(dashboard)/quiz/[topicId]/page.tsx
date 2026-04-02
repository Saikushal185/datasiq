"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Controller, type Path, type Resolver, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock3, RefreshCcw, Sparkles } from "lucide-react";
import { z } from "zod";

import CodeQuestion from "@/components/quiz/CodeQuestion";
import MCQQuestion from "@/components/quiz/MCQQuestion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppAuth } from "@/lib/auth";
import type {
  QuizQuestionResponse,
  QuizResponse,
  QuizSubmissionBreakdownResponse,
  QuizSubmissionResponse
} from "@/lib/api";
import { useQuizQuery, useSubmitQuizMutation } from "@/lib/queries";
import { cn } from "@/lib/utils";

type RouteParams = {
  topicId?: string | string[];
};

type QuizFormValues = {
  answers: Record<string, string>;
};

function getRouteTopicId(topicIdParam: RouteParams["topicId"]): string {
  if (Array.isArray(topicIdParam)) {
    return topicIdParam[0] ?? "";
  }

  return topicIdParam ?? "";
}

function normalizePercent(value: number): number {
  const magnitude = Math.abs(value);
  return magnitude <= 1 ? magnitude * 100 : magnitude;
}

function formatPercent(value: number): string {
  return `${Math.round(normalizePercent(value))}%`;
}

function formatSignedPercent(value: number): string {
  const magnitude = Math.round(normalizePercent(value));
  const prefix = value < 0 ? "-" : "+";
  return `${prefix}${magnitude}%`;
}

function buildDefaultAnswers(questions: QuizQuestionResponse[]): Record<string, string> {
  return Object.fromEntries(questions.map((question) => [question.id, ""])) as Record<string, string>;
}

function buildQuizSchema(questions: QuizQuestionResponse[]) {
  const answerShape: z.ZodRawShape = Object.fromEntries(
    questions.map((question) => [
      question.id,
      z.string().trim().min(1, "Pick or enter an answer before submitting.")
    ])
  );

  return z.object({
    answers: z.object(answerShape)
  });
}

function getQuestionTypeLabel(questionType: QuizQuestionResponse["questionType"]): string {
  switch (questionType) {
    case "mcq":
      return "Multiple choice";
    case "code_output":
      return "Code output";
    case "fill_blank":
      return "Fill in the blank";
  }
}

function resolveAnswerText(question: QuizQuestionResponse, answerId: string): string {
  if (!answerId) {
    return "No answer";
  }

  return question.options.find((option) => option.id === answerId)?.text ?? answerId;
}

function getBreakdownMap(submission: QuizSubmissionResponse | null): Map<string, QuizSubmissionBreakdownResponse> {
  return new Map((submission?.breakdown ?? []).map((item) => [item.questionId, item] as const));
}

function QuizLoadingState() {
  return (
    <main className="page-shell">
      <section className="space-y-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-10 w-72 max-w-full" />
        <Skeleton className="h-4 w-[28rem] max-w-full" />
      </section>
      <div className="mt-6 space-y-4">
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-[22rem] w-full rounded-[1.75rem]" />
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-16 rounded-[1.25rem]" />
          <Skeleton className="h-16 rounded-[1.25rem]" />
        </div>
      </div>
    </main>
  );
}

function QuizErrorState({
  title,
  message,
  onRetry,
  retryLabel
}: {
  title: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <main className="page-shell">
      <div className="error-state mx-auto mt-8 max-w-xl">
        <AlertTriangle className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {onRetry ? (
            <Button type="button" variant="outline" onClick={onRetry}>
              {retryLabel ?? "Retry"}
            </Button>
          ) : null}
          <Button asChild variant="secondary">
            <Link href="/dashboard">
              <ArrowLeft className="h-4 w-4" />
              Back to dashboard
            </Link>
          </Button>
        </div>
      </div>
    </main>
  );
}

function QuizEmptyState({
  title,
  message,
  onRetry
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <main className="page-shell">
      <div className="empty-state mx-auto mt-8 max-w-xl">
        <Sparkles className="h-10 w-10 text-primary" />
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <Button type="button" variant="outline" onClick={onRetry}>
          <RefreshCcw className="h-4 w-4" />
          Refresh quiz
        </Button>
      </div>
    </main>
  );
}

function QuizSummaryBreakdown({
  quiz,
  submission
}: {
  quiz: QuizResponse;
  submission: QuizSubmissionResponse;
}) {
  const breakdownMap = getBreakdownMap(submission);

  return (
    <div className="space-y-4">
      {quiz.questions.map((question) => {
        const result = breakdownMap.get(question.id);
        const statusIsCorrect = result?.isCorrect ?? false;

        return (
          <Card key={question.id} className="overflow-hidden">
            <CardContent className="space-y-4 pt-6">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{getQuestionTypeLabel(question.questionType)}</Badge>
                <Badge variant={statusIsCorrect ? "success" : "danger"}>{statusIsCorrect ? "Correct" : "Wrong"}</Badge>
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-semibold tracking-tight text-foreground">{question.prompt}</h3>
                {question.hint ? <p className="text-sm leading-6 text-muted-foreground">{question.hint}</p> : null}
              </div>
              {question.questionType === "fill_blank" ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.25rem] border border-border/80 bg-white/80 p-4 shadow-soft">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Your answer</p>
                    <p className="mt-2 text-sm font-medium">{result ? resolveAnswerText(question, result.selectedOptionId) : "No answer"}</p>
                  </div>
                  <div className="rounded-[1.25rem] border border-border/80 bg-white/80 p-4 shadow-soft">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Correct answer</p>
                    <p className="mt-2 text-sm font-medium">{result ? resolveAnswerText(question, result.correctOptionId) : "Unavailable"}</p>
                  </div>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.25rem] border border-border/80 bg-white/80 p-4 shadow-soft">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Selected</p>
                    <p className="mt-2 text-sm font-medium">{result ? resolveAnswerText(question, result.selectedOptionId) : "No answer"}</p>
                  </div>
                  <div className="rounded-[1.25rem] border border-border/80 bg-white/80 p-4 shadow-soft">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Correct</p>
                    <p className="mt-2 text-sm font-medium">{result ? resolveAnswerText(question, result.correctOptionId) : "Unavailable"}</p>
                  </div>
                </div>
              )}
              <div
                className={cn(
                  "rounded-[1.25rem] border px-4 py-4 text-sm shadow-soft",
                  statusIsCorrect ? "border-success/20 bg-success/10 text-success" : "border-danger/20 bg-danger/10 text-danger"
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={statusIsCorrect ? "success" : "danger"}>
                    {statusIsCorrect ? "Correct answer" : "Needs review"}
                  </Badge>
                  <span>{result ? result.explanation : "No explanation returned."}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function QuizSession({ quiz }: { quiz: QuizResponse }) {
  const [submission, setSubmission] = useState<QuizSubmissionResponse | null>(null);
  const submitMutation = useSubmitQuizMutation(quiz.id);
  const questionSignature = useMemo(() => quiz.questions.map((question) => question.id).join("|"), [quiz.questions]);
  const defaultAnswers = useMemo(() => buildDefaultAnswers(quiz.questions), [questionSignature]);
  const quizSchema = useMemo(() => buildQuizSchema(quiz.questions), [questionSignature]);

  const form = useForm<QuizFormValues>({
    resolver: zodResolver(quizSchema) as Resolver<QuizFormValues>,
    defaultValues: {
      answers: defaultAnswers
    },
    mode: "onSubmit"
  });

  useEffect(() => {
    form.reset({ answers: defaultAnswers });
    setSubmission(null);
    submitMutation.reset();
  }, [defaultAnswers, form, quiz.id, submitMutation.reset]);

  const watchedAnswers = form.watch("answers");
  const answeredCount = Object.values(watchedAnswers ?? {}).filter((value) => value.trim().length > 0).length;
  const totalQuestions = quiz.questions.length;
  const progressValue = submission ? normalizePercent(submission.score) : totalQuestions === 0 ? 0 : (answeredCount / totalQuestions) * 100;
  const scorePercent = submission ? formatPercent(submission.score) : null;
  const thresholdPercent = formatPercent(quiz.passThreshold);
  const breakdownMap = useMemo(() => getBreakdownMap(submission), [submission]);
  const isSubmitting = form.formState.isSubmitting || submitMutation.isPending;

  const resetQuiz = () => {
    form.reset({ answers: defaultAnswers });
    setSubmission(null);
    submitMutation.reset();
  };

  const handleSubmit = form.handleSubmit(async (values) => {
    try {
      const response = await submitMutation.mutateAsync({
        answers: values.answers
      });
      setSubmission(response);
    } catch {
      // Surface mutation error below and keep the current answers intact.
    }
  });

  if (submission) {
    const recommendedActionLabel =
      submission.recommendedAction === "unlock_next_topic" ? "Unlock next topic" : "Review flashcards";
    const recommendedActionHref = submission.recommendedAction === "unlock_next_topic" ? "/progress" : "/flashcards";

    return (
      <section className="space-y-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={submission.passed ? "success" : "danger"}>{submission.passed ? "Passed" : "Needs more work"}</Badge>
            <Badge variant="secondary">{scorePercent}</Badge>
            <Badge variant="outline">Threshold {thresholdPercent}</Badge>
          </div>
          <h1 className="section-title">{quiz.title}</h1>
          <p className="section-subtitle">
            {submission.passed
              ? `You cleared the quiz and gained ${formatSignedPercent(submission.masteryDelta)} mastery.`
              : `You missed the pass threshold by a little. Review the breakdown below and try again.`}
          </p>
        </div>

        <Card className="overflow-hidden">
          <CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Score</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">{scorePercent}</p>
            </div>
            <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Threshold</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">{thresholdPercent}</p>
            </div>
            <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Mastery delta</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">{formatSignedPercent(submission.masteryDelta)}</p>
            </div>
            <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Recommended action</p>
              <p className="mt-2 text-lg font-semibold tracking-tight">{recommendedActionLabel}</p>
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link href={recommendedActionHref}>
              {submission.passed ? <CheckCircle2 className="h-4 w-4" /> : <RefreshCcw className="h-4 w-4" />}
              {recommendedActionLabel}
            </Link>
          </Button>
          <Button type="button" size="lg" variant="outline" className="w-full sm:w-auto" onClick={resetQuiz}>
            <RefreshCcw className="h-4 w-4" />
            Retake quiz
          </Button>
        </div>

        <QuizSummaryBreakdown quiz={quiz} submission={submission} />
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Quiz challenge</Badge>
          <Badge variant="secondary">{quiz.topic.title}</Badge>
          <Badge variant="outline">
            <Clock3 className="h-3.5 w-3.5" />
            {quiz.topic.estimatedMinutes} min
          </Badge>
        </div>
        <h1 className="section-title">{quiz.title}</h1>
        <p className="section-subtitle">
          Answer every question, then submit once you're ready for the auto-graded result and mastery update.
        </p>
      </div>

      <Card className="overflow-hidden">
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{quiz.questions.length} questions</Badge>
            <Badge variant="secondary">Pass threshold {thresholdPercent}</Badge>
            <Badge variant="outline">{answeredCount}/{totalQuestions} answered</Badge>
          </div>
          <Progress value={progressValue} />
          <p className="text-sm text-muted-foreground">
            Submit when you're finished. MCQ and code-output questions are auto-graded against the backend response.
          </p>
        </CardContent>
      </Card>

      <form className="space-y-4" onSubmit={handleSubmit}>
        {quiz.questions.map((question) => {
          const answerPath = `answers.${question.id}` as Path<QuizFormValues>;
          const feedback = breakdownMap.get(question.id) ?? null;

          return (
            <Controller
              key={question.id}
              control={form.control}
              name={answerPath}
              render={({ field, fieldState }) => {
                const answerValue = typeof field.value === "string" ? field.value : "";

                if (question.questionType === "mcq") {
                  return (
                    <MCQQuestion
                      question={question}
                      value={answerValue}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                      feedback={feedback}
                      error={fieldState.error?.message}
                    />
                  );
                }

                if (question.questionType === "code_output") {
                  return (
                    <CodeQuestion
                      question={question}
                      value={answerValue}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                      feedback={feedback}
                      error={fieldState.error?.message}
                    />
                  );
                }

                return (
                  <Card className="overflow-hidden">
                    <CardContent className="space-y-4 pt-6">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">Fill in the blank</Badge>
                        <Badge variant="secondary">{question.options.length} options</Badge>
                      </div>
                      <div className="space-y-2">
                        <h2 className="text-xl font-semibold tracking-tight text-foreground">{question.prompt}</h2>
                        {question.hint ? <p className="text-sm leading-6 text-muted-foreground">{question.hint}</p> : null}
                      </div>
                      <input
                        ref={field.ref}
                        value={answerValue}
                        onChange={field.onChange}
                        onBlur={field.onBlur}
                        name={field.name}
                        disabled={isSubmitting}
                        placeholder="Type your answer"
                        className="min-h-12 w-full rounded-2xl border border-border/80 bg-white/80 px-4 py-3 text-sm shadow-soft outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/50 focus:ring-2 focus:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"
                      />
                      {fieldState.error?.message ? <p className="text-sm font-medium text-danger">{fieldState.error.message}</p> : null}
                      {feedback ? (
                        <div
                          className={cn(
                            "rounded-[1.25rem] border px-4 py-4 text-sm shadow-soft",
                            feedback.isCorrect
                              ? "border-success/20 bg-success/10 text-success"
                              : "border-danger/20 bg-danger/10 text-danger"
                          )}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant={feedback.isCorrect ? "success" : "danger"}>
                              {feedback.isCorrect ? "Correct" : "Incorrect"}
                            </Badge>
                            <span>Selected: {resolveAnswerText(question, feedback.selectedOptionId)}</span>
                            <span>Correct: {resolveAnswerText(question, feedback.correctOptionId)}</span>
                          </div>
                          <p className="mt-2 leading-6 text-current/90">{feedback.explanation}</p>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                );
              }}
            />
          );
        })}

        {submitMutation.isError ? (
          <div className="rounded-[1.25rem] border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger shadow-soft">
            {submitMutation.error.message}
          </div>
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
          <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={isSubmitting}>
            {isSubmitting ? "Submitting..." : "Submit quiz"}
          </Button>
        </div>
      </form>
    </section>
  );
}

export default function QuizTopicPage() {
  const params = useParams<RouteParams>();
  const { isLoaded, isSignedIn } = useAppAuth();
  const topicId = getRouteTopicId(params.topicId);
  const quizQuery = useQuizQuery(topicId);

  if (!isLoaded || quizQuery.isLoading) {
    return <QuizLoadingState />;
  }

  if (!isSignedIn) {
    return (
      <QuizErrorState
        title="Sign in to take this quiz"
        message="This study route is protected. Sign in, then reload the quiz to continue."
      />
    );
  }

  if (!topicId) {
    return (
      <QuizErrorState
        title="Invalid quiz route"
        message="The quiz topic id is missing from the route."
      />
    );
  }

  if (quizQuery.isError) {
    return (
      <QuizErrorState
        title="We couldn't load the quiz"
        message={quizQuery.error.message}
        onRetry={() => void quizQuery.refetch()}
        retryLabel="Retry quiz"
      />
    );
  }

  const quiz = quizQuery.data;

  if (!quiz) {
    return <QuizLoadingState />;
  }

  if (quiz.questions.length === 0) {
    return (
      <QuizEmptyState
        title="No quiz questions yet"
        message="The backend returned an empty quiz. Try again once the topic content is ready."
        onRetry={() => void quizQuery.refetch()}
      />
    );
  }

  return (
    <main className="page-shell">
      <QuizSession key={quiz.id} quiz={quiz} />
    </main>
  );
}
