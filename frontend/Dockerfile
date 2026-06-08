# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# Public backend URL is baked in at build time (Vite inlines VITE_* vars).
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build   # outputs /app/dist

# ── Serve stage ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
