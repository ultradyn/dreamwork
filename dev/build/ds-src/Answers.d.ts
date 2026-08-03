import type { ComponentType } from "react";

export interface AnswerRecord {
  title: string;
  body?: string;
  aid?: string;
}

export interface AnswersData {
  answers_health?: "unreadable";
  answers_open: AnswerRecord[];
  answers_answered: AnswerRecord[];
}

export interface AnswersProps {
  data?: AnswersData | null;
}

export declare const Answers: ComponentType<AnswersProps>;
