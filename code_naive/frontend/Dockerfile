FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 4173
# vite preview — встроенный статический сервер, без nginx
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]