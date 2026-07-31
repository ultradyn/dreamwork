import type { ComponentType } from "react";

export interface QaCardQuestion {
  title: string;
  body?: string;
  follows?: Array<{ text: string; when?: string; by?: string }>;
  answer?: string;
  answer_when?: string;
  answer_by?: string;
  answers?: Array<{ text: string; when?: string; by?: string }>;
  when?: string;
  updated_at?: number;
}

export interface QaCardProps {
  q: QaCardQuestion;
  k: `o${number}` | `a${number}`;
  ctx?: {
    data?: { linkable_paths?: string[] };
    view?: { name?: string | null; param?: string | null; q?: string | null };
  };
}

export declare const QaCard: ComponentType<QaCardProps>;
