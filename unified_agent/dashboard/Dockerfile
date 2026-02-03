# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy source
COPY . .

# Create public directory if it doesn't exist
RUN mkdir -p /app/public

# Build
RUN npm run build

# Production stage
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Copy public folder if it exists (using || true to ignore if empty)
RUN mkdir -p ./public
COPY --from=builder /app/public/ ./public/

EXPOSE 3000

CMD ["node", "server.js"]
