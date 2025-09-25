FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_BACKEND_URL=http://backend
ARG VITE_BACKEND_PORT=8000
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_BACKEND_PORT=${VITE_BACKEND_PORT}
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
