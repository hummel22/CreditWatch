FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
# Empty = same-origin /api requests; nginx (below) proxies them to the backend.
# An absolute http:// URL here gets blocked as mixed content when the UI is
# served over HTTPS (e.g. creditwatch.lab.streambudget.com).
ARG VITE_BACKEND_URL=
ARG VITE_BACKEND_PORT=
ARG VITE_BUILD_MODE=development
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_BACKEND_PORT=${VITE_BACKEND_PORT}
ENV VITE_BUILD_MODE=${VITE_BUILD_MODE}
ENV NODE_ENV=${VITE_BUILD_MODE}
RUN npm run build -- --mode ${VITE_BUILD_MODE}

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
