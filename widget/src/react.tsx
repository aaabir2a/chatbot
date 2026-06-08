import { useEffect, useRef } from "react";
import { createChatWidget } from "./core";
import type { ChatTheme, ChatWidgetInstance } from "./types";

export interface ChatWidgetProps {
  apiUrl: string;
  apiKey: string;
  chatbotId: string;
  theme?: ChatTheme;
}

/**
 * React wrapper around the framework-agnostic core. Mounts into document.body
 * (Shadow DOM isolated), so it composes cleanly with any React app — including
 * one already deployed on Vercel.
 */
export function ChatWidget({ apiUrl, apiKey, chatbotId, theme }: ChatWidgetProps) {
  const instanceRef = useRef<ChatWidgetInstance | null>(null);
  // Stringify theme so prop-object identity changes don't remount needlessly.
  const themeKey = JSON.stringify(theme ?? {});

  useEffect(() => {
    const instance = createChatWidget({ apiUrl, apiKey, chatbotId, theme });
    instanceRef.current = instance;
    return () => instance.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, apiKey, chatbotId, themeKey]);

  return null; // widget renders itself into <body> via Shadow DOM
}

export default ChatWidget;
