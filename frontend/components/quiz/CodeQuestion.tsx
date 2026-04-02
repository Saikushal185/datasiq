"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { QuizQuestionResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type QuizFeedback = {
  selectedOptionId: string;
  correctOptionId: string;
  isCorrect: boolean;
  explanation: string;
};

type CodeQuestionProps = {
  question: Pick<QuizQuestionResponse, "id" | "prompt" | "options" | "hint" | "codeSnippet">;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  feedback?: QuizFeedback | null;
  error?: string | null;
  className?: string;
};

function resolveOptionLabel(options: QuizQuestionResponse["options"], optionId: string): string {
  return options.find((option) => option.id === optionId)?.text ?? optionId;
}

export default function CodeQuestion({
  question,
  value,
  onChange,
  disabled = false,
  feedback,
  error,
  className
}: CodeQuestionProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Code output</Badge>
          <Badge variant="secondary">{question.options.length || 0} answers</Badge>
        </div>
        <CardTitle className="text-xl leading-tight sm:text-2xl">{question.prompt}</CardTitle>
        {question.hint ? <p className="text-sm leading-6 text-muted-foreground">{question.hint}</p> : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-hidden rounded-[1.25rem] border border-border/80 bg-slate-950 p-4 shadow-soft">
          <p className="mb-3 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-slate-400">Snippet</p>
          <pre className="overflow-x-auto text-sm leading-6 text-slate-100">
            <code>{question.codeSnippet ?? "No code snippet was provided."}</code>
          </pre>
        </div>

        {question.options.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {question.options.map((option) => {
              const isSelected = value === option.id;
              const isCorrect = feedback?.correctOptionId === option.id;
              const showFeedback = feedback !== null && feedback !== undefined;

              return (
                <button
                  key={option.id}
                  type="button"
                  disabled={disabled}
                  aria-pressed={isSelected}
                  onClick={() => onChange(option.id)}
                  className={cn(
                    "flashcard-option min-h-16",
                    isSelected ? "flashcard-option-selected" : "",
                    showFeedback && isCorrect ? "feedback-flash-correct" : "",
                    showFeedback && feedback?.selectedOptionId === option.id && !feedback.isCorrect ? "feedback-flash-wrong" : ""
                  )}
                >
                  <span className="text-left">{option.text}</span>
                  <span className="text-[0.7rem] uppercase tracking-[0.18em] text-muted-foreground">
                    {showFeedback ? (isCorrect ? "Correct" : isSelected ? "Chosen" : "Option") : isSelected ? "Selected" : "Choose"}
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="empty-state py-8">
            <p className="text-sm text-muted-foreground">No answer choices were returned for this code question.</p>
          </div>
        )}

        {feedback ? (
          <div
            className={cn(
              "rounded-[1.25rem] border px-4 py-4 text-sm shadow-soft",
              feedback.isCorrect ? "border-success/20 bg-success/10 text-success" : "border-danger/20 bg-danger/10 text-danger"
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={feedback.isCorrect ? "success" : "danger"}>{feedback.isCorrect ? "Correct" : "Incorrect"}</Badge>
              <span>Selected: {resolveOptionLabel(question.options, feedback.selectedOptionId)}</span>
              <span>Correct: {resolveOptionLabel(question.options, feedback.correctOptionId)}</span>
            </div>
            <p className="mt-2 leading-6 text-current/90">{feedback.explanation}</p>
          </div>
        ) : null}

        {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
