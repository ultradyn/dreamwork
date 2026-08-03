import type { ComponentType } from "react";
import type { ArtifactRowRecord } from "./ArtifactRow";

export interface ReviewsData {
  reviews: ArtifactRowRecord[];
}

export interface ReviewsProps {
  data?: ReviewsData | null;
}

export declare const Reviews: ComponentType<ReviewsProps>;
