FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM dependencies AS development
COPY . .
CMD ["npm", "run", "dev"]

FROM dependencies AS build
COPY . .
# Public configuration only. Database credentials never enter this build.
ARG VITE_API_BASE_URL
RUN test -n "$VITE_API_BASE_URL" && VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run build

FROM nginx:stable-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

