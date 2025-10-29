FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
ARG VITE_BACKEND_URL=http://creditwatch
ARG VITE_BACKEND_PORT=8010
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
