# Multi-stage Dockerfile for Next.js Frontend

# Stage 1: Dependencies
FROM node:20-alpine AS deps

WORKDIR /app

# Copy package files
COPY apps/web/package*.json ./

# Install dependencies
RUN npm ci

# Stage 2: Builder
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY apps/web .
COPY apps/web/healthcheck.js ./healthcheck.js

# Build arguments
ARG NEXT_PUBLIC_API_URL
ARG NEXTAUTH_URL
ARG NEXTAUTH_SECRET

# Set environment variables for build
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXTAUTH_URL=${NEXTAUTH_URL}
ENV NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
ENV NODE_ENV=production

# Build application
RUN npm run build

# Stage 3: Development
FROM node:20-alpine AS development

WORKDIR /app

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules

# Copy source
COPY apps/web .

# Expose port
EXPOSE 3000

# Run development server
CMD ["npm", "run", "dev"]

# Stage 4: Production runner
FROM node:20-alpine AS production

WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./package.json
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

# Expose port
EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node healthcheck.js

# Start Next.js
CMD ["npm", "start"]

