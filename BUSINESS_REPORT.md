# AI Chatbot Platform — Business Report

**Build period:** 8 June – 30 July 2026 (two months) · **Status:** live and running on our own server

---

## 1. What we set out to build

A chatbot that sits on a company website, answers customer questions using *that
company's own documents*, and turns those conversations into sales leads.

Built as a **platform, not a single bot** — one system can run chatbots for many
different companies at once, each fully separated from the others. That means we
can sell it as a service, not just use it ourselves.

---

## 2. What is built and working today

### The customer-facing chatbot
- Answers from **our uploaded documents only** — no made-up answers, no generic internet guessing.
- Replies appear **word by word as it types**, like ChatGPT. No waiting screens.
- **Remembers the conversation.** A customer can ask "and how much does that cost?" and it knows what "that" refers to.
- Handles greetings and small talk naturally instead of replying "I couldn't find that in the documents."
- Formats answers properly — bold text, bullet lists, clickable links.
- Shows **suggested questions** as clickable buttons when the chat opens, so customers know what to ask.
- **Drops into any website with one line of code.** It cannot break or be broken by the site's own design.

### Turning chats into revenue
- **Automatic lead capture.** After a few messages, the bot asks for name, phone and email. If the customer skips, it politely asks again later — it does not give up on the first no.
- **Sales-intent detection.** When someone shows buying interest — or when the bot genuinely has no answer — it immediately shows the sales phone number and the contact form. That is the moment a visitor is most likely to convert.
- **Leads dashboard** where the team sees every captured lead and marks its status.

### Live human takeover
- Staff can watch conversations in real time and **jump in and take over** from the bot mid-chat, then hand it back.
- Full conversation history with timestamps, so nothing is lost between the bot and the human.

### CRM connection
- Our CRM can **read** every conversation, transcript and lead automatically.
- The CRM can **push lead status back**, so both systems stay in sync.
- **Instant notifications** are sent to the CRM the moment a lead is captured, a message arrives, or a customer asks for a human. Signed and verified so no one can fake them.
- CRM staff can even take over a live chat from inside the CRM.

### Self-service admin
- A web dashboard to create chatbots, upload documents, set the greeting, tone, sales phone and suggested questions, issue access keys, and see usage.
- **No developer needed** for day-to-day changes.

---

## 3. The three changes that changed the business case

**1. Freedom to choose the AI brain (13 June).**
Originally the AI ran only on our own server — cheap, but slow on modest hardware.
We rebuilt it so any major AI provider (Groq, Google Gemini, OpenAI, DeepSeek) can be
plugged in, **chosen per chatbot from the dashboard**. Result: near-instant answers
for premium clients, cheap self-hosted answers for budget ones, and no lock-in to any
one vendor's pricing. This alone took the product from "demo" to "sellable."

**2. The bot stopped being a FAQ and became a salesperson (10–24 June).**
Lead capture, the retry-after-skip logic, and sales-intent detection turned every
conversation into a chance to collect a contact. The chatbot now produces a measurable
business output — leads — rather than just deflecting support questions.

**3. It plugs into the rest of the business (1–2 July).**
The CRM integration and live-agent takeover mean the chatbot is no longer an island.
Leads flow automatically into the sales process, and a human can rescue any conversation
the bot cannot finish. This is what makes it viable for real clients rather than internal use.

---

## 4. Where it stands commercially

- **Live on our own server** — no per-message fees to a third party unless we choose a hosted AI provider.
- **Multi-client from day one.** Each client's documents are locked to their own chatbot; one client can never see another's data.
- **Sellable as a monthly service** — each client gets their own dashboard, their own bot, their own leads.
- Two months of work, from empty repository to a deployed, integrated, revenue-capable product.

---

## 5. What comes next

**Immediate (days)**
- **Live push to the CRM.** Today the CRM checks for new leads every few seconds. The last piece is a direct live connection so leads appear the instant they happen. Design is done; build is short.
- **Onboard the first paying clients** — upload their documents, set their branding and sales phone, embed on their site.

**Near term (weeks)**
- Analytics for the owner: most-asked questions, conversations-to-leads conversion rate, hours where customers are most active.
- Bangla language replies — started, paused in June, ready to resume.
- Automated quality checks before each update, so releases stay safe as client count grows.

**Growth**
- Self-service signup so clients onboard themselves without our involvement.
- Billing and plan tiers on top of the existing usage tracking.
- Additional channels — WhatsApp and Facebook Messenger reuse the same engine already built.

---

## 6. Bottom line

In two months we went from nothing to a **live, multi-client AI chatbot service** that
answers from a company's own documents, captures leads, hands off to humans, and feeds
our CRM automatically. The engineering foundation is complete. The remaining work is
mostly about **selling it and polishing the edges**, not building it.
