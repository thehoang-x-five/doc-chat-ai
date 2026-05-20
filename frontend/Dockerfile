# Frontend - Vite Dev Server with Hot Reload
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Fresh install
RUN rm -rf node_modules package-lock.json && \
    npm install --silent --no-audit --no-fund

# Copy source code
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
