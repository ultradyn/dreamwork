import type { ComponentType } from "react";

export interface ExpandProps {
  s: string;
  inner: string;
  cls?: string;
  keep?: string;
}

export declare const Expand: ComponentType<ExpandProps>;
