import type { ComponentType } from "react";

export interface FollowThreadItem {
  author?: string;
  text: string;
  when?: string;
}

export interface FollowThreadProps {
  follows: FollowThreadItem[];
  fold: boolean;
  ctx?: {
    data?: { linkable_paths?: string[] };
    view?: { name?: string | null; param?: string | null; q?: string | null };
  };
}

export declare const FollowThread: ComponentType<FollowThreadProps>;
