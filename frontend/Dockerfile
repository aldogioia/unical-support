FROM node:20-slim AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci


# ---------- DEV: ng serve con hot reload (usato da docker-compose) ----------
FROM base AS dev
COPY . .
EXPOSE 4200
CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--port", "4200", "--poll", "1000"]


# ---------- BUILD: build di produzione ----------
FROM base AS build
COPY . .
RUN npx ng build --configuration production


# ---------- PRODUCTION: static files serviti da nginx ----------
FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
