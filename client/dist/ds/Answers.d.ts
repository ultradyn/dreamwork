import type { ComponentType } from "react";

export interface AnswerRecord {
  title: string;
  body?: string;
  aid?: string;
}

// answers_health is the complete union watch.answers_health emits
// (watch.py:3000): "missing" | "empty" | "unreadable" | "ok".
export interface AnswersData {
  answers_health: "missing" | "empty" | "unreadable" | "ok";
  answers_open: AnswerRecord[];
  answers_answered: AnswerRecord[];
}

export interface AnswersProps {
  // buildAnswers dereferences data.answers_health immediately (views.js:1214),
  // so data is required, never null.
  data: AnswersData;
}

export declare const Answers: ComponentType<AnswersProps>;
