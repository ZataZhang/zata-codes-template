# ------------------------------------------------------------------------------
# Public Frontend — Next.js App Router Marketing + App Shell
# ------------------------------------------------------------------------------
# Build context: 仓库根（不是 ./frontend-public）
#
# frontend-public 是 pnpm workspace 的成员，而 pnpm-workspace.yaml 与
# pnpm-lock.yaml 都在仓库根。上下文设成 ./frontend-public 时这两个文件不在构建
# 上下文里，COPY 直接失败，镜像根本构建不出来。
#
# Production runtime: node (Next.js standalone)
# ------------------------------------------------------------------------------

# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Run pnpm in non-interactive CI mode
ENV CI=true

RUN npm install -g pnpm

# 先只放依赖清单，让依赖层能被 Docker 缓存复用。
# --frozen-lockfile 会按 lockfile 校验**全部**工作区成员的清单，因此
# frontend-admin/package.json 也必须在场；--filter 保证只真正安装
# frontend-public 的依赖。
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend-public/package.json frontend-public/
COPY frontend-admin/package.json frontend-admin/
RUN pnpm install --frozen-lockfile --filter ./frontend-public...

# Copy source and build
COPY frontend-public/ frontend-public/
WORKDIR /app/frontend-public
RUN pnpm build

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Next.js standalone 产物。next.config.ts 把 outputFileTracingRoot 指到仓库根，
# 因此 standalone 内部保留了 frontend-public/ 这一层，server.js 也在其中。
COPY --from=builder /app/frontend-public/.next/standalone ./
COPY --from=builder /app/frontend-public/.next/static ./frontend-public/.next/static
COPY --from=builder /app/frontend-public/public ./frontend-public/public

EXPOSE 3000

CMD ["node", "frontend-public/server.js"]
