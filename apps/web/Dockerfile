FROM node:22.19.0-alpine AS build
WORKDIR /app
RUN npm install --global pnpm@10.15.1
COPY package.json ./
RUN pnpm install --no-frozen-lockfile
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm build
FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
