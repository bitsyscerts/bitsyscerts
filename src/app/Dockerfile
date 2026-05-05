# ── Stage 1: build the Vite app ───────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY src/app/package.json src/app/package-lock.json ./
RUN npm ci --prefer-offline

COPY src/app .
RUN npm run build

# ── Stage 2: serve with Nginx ─────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove the default Nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY src/app/nginx.conf /etc/nginx/conf.d/bitsyscerts.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
