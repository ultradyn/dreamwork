import type { ComponentType } from "react";

export interface QaComposeProps {
  key: `o${number}` | `a${number}`;
  st: "open" | "awaiting" | "folded";
  title: string;
}

export declare const QaCompose: ComponentType<QaComposeProps>;
