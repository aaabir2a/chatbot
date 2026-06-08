// Script-embed entry (IIFE). Exposes window.RagChat and auto-initializes from
// the <script> tag's data-* attributes. No React — pure vanilla core.
import { createChatWidget } from "./core";
import type { ChatTheme, ChatWidgetInstance, ChatWidgetOptions } from "./types";

declare global {
  interface Window {
    RagChat?: {
      init: (opts: ChatWidgetOptions) => ChatWidgetInstance;
    };
  }
}

function init(opts: ChatWidgetOptions): ChatWidgetInstance {
  if (!opts || !opts.apiUrl || !opts.apiKey || !opts.chatbotId) {
    throw new Error("RagChat.init requires { apiUrl, apiKey, chatbotId }.");
  }
  return createChatWidget(opts);
}

window.RagChat = { init };

// Auto-init from data attributes on the loading <script>:
//   <script src="widget.js"
//     data-api-url="https://api.example.com"
//     data-api-key="sk_..."
//     data-chatbot-id="abc"
//     data-title="Support"
//     data-primary-color="#5b5bf5"
//     data-position="bottom-right"></script>
(function autoInit() {
  const current =
    (document.currentScript as HTMLScriptElement | null) ||
    (() => {
      const scripts = document.getElementsByTagName("script");
      for (let i = scripts.length - 1; i >= 0; i--) {
        if (scripts[i].src && scripts[i].dataset.apiKey) return scripts[i];
      }
      return null;
    })();

  if (!current) return;
  const d = current.dataset;
  if (!d.apiUrl || !d.apiKey || !d.chatbotId) return;

  const theme: ChatTheme = {};
  if (d.primaryColor) theme.primaryColor = d.primaryColor;
  if (d.textOnPrimary) theme.textOnPrimary = d.textOnPrimary;
  if (d.position === "bottom-left" || d.position === "bottom-right")
    theme.position = d.position;
  if (d.title) theme.title = d.title;
  if (d.subtitle) theme.subtitle = d.subtitle;
  if (d.welcomeMessage) theme.welcomeMessage = d.welcomeMessage;
  if (d.placeholder) theme.placeholder = d.placeholder;
  if (d.launcherIcon) theme.launcherIcon = d.launcherIcon;

  const run = () => init({ apiUrl: d.apiUrl!, apiKey: d.apiKey!, chatbotId: d.chatbotId!, theme });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
