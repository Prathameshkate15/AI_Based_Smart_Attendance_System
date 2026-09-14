FROM node:20-alpine AS build

WORKDIR /app
COPY package.json bun.lock ./
RUN corepack enable && corepack prepare bun@1.1.38 --activate && bun install --frozen-lockfile
COPY . .
RUN bun run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
