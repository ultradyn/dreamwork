import type { ComponentType } from "react";

export interface ArtifactRowRecord {
  name: string;
  created?: number;
  created_known?: boolean;
  mtime?: number;
  show_modified?: boolean;
  decision?: "accepted" | "rejected" | "pending" | null;
  question_title?: string | null;
}

export interface ArtifactRowProps {
  r: ArtifactRowRecord;
  kind: "review" | "research";
}

export declare const ArtifactRow: ComponentType<ArtifactRowProps>;
