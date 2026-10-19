# ------------------------------------------------------------------------------
# Frontend — Admin Dashboard (Vite + React + TanStack Router)
# ------------------------------------------------------------------------------
# Build context: 仓库根（不是 ./frontend-admin）
#
# frontend-admin 是 pnpm workspace 的成员，而 pnpm-workspace.yaml 与
# pnpm-lock.yaml 都在仓库根。上下文设成 ./frontend-admin 时这两个文件不在构建
# 上下文里，COPY 直接失败，镜像根本构建不出来。
#
# Production runtime: nginx
# ------------------------------------------------------------------------------

# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Run pnpm in non-interactive CI mode
ENV CI=true

# Install pnpm
RUN npm install -g pnpm

# 先只放依赖清单，让依赖层能被 Docker 缓存复用。
# --frozen-lockfile 会按 lockfile 校验**全部**工作区成员的清单，因此
# frontend-public/package.json 也必须在场；--filter 保证只真正安装
# frontend-admin 的依赖。
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend-admin/package.json frontend-admin/
COPY frontend-public/package.json frontend-public/
RUN pnpm install --frozen-lockfile --filter ./frontend-admin...

# Inject the build-time version string (defaults to "dev" for local builds).
ARG VITE_APP_VERSION=dev
ENV VITE_APP_VERSION=${VITE_APP_VERSION}

# Copy source and build
COPY frontend-admin/ frontend-admin/
WORKDIR /app/frontend-admin
RUN pnpm build

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# 只替换 Compose 注入的后端地址，保留 $host、$remote_addr 等 Nginx 自身变量。
ENV NGINX_ENVSUBST_FILTER=^BACKEND_UPSTREAM$

# Copy built static assets
COPY --from=builder /app/frontend-admin/dist /usr/share/nginx/html

# 官方 Nginx entrypoint 会在启动时把模板渲染到 conf.d。
COPY frontend-admin/nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
