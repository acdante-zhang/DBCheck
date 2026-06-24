#!/bin/bash
# ============================================
# Acdante DB Inspector - Docker 镜像离线打包
# 在 macOS Docker 上构建 → 导出 tar → 部署到 Oracle Linux 9 + Podman
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="acdante-db-inspector"
IMAGE_TAG="latest"
EXPORT_FILE="$SCRIPT_DIR/${IMAGE_NAME}-${IMAGE_TAG}.tar"
EXPORT_FILE_GZ="${EXPORT_FILE}.gz"

echo "=========================================="
echo "  Acdante DB Inspector - Docker 镜像打包"
echo "  目标: Oracle Linux 9.5 + Podman"
echo "=========================================="

cd "$SCRIPT_DIR"

# 1. 生成精简 Dockerfile（跳过 drivers.zip 加速构建）
echo ""
echo "[1/3] 生成 Dockerfile..."

cat > "$SCRIPT_DIR/Dockerfile.offline" << 'DOCKERFILE'
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl unzip tzdata ca-certificates unixodbc unixodbc-dev libaio1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖（用清华源加速）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir \
    python-docx docxtpl psutil PyYAML cryptography \
    flask flask-socketio gevent pymysql psycopg2-binary \
    oracledb dmpython pyodbc paramiko openpyxl pandas \
    reportlab apscheduler PyPDF2 bcrypt PyJWT \
    gbase8sdb jaydebeapi JPype1

# 复制应用代码
COPY . /app

# 清理构建缓存
RUN pip cache purge && \
    find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "*.pyc" -delete 2>/dev/null || true

# 确保目录存在
RUN mkdir -p /app/data /app/pro_data /app/reports

# 复制入口脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PATH="/usr/local/bin:$PATH"
ENV TZ=Asia/Shanghai
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

RUN echo "2.7.0-acdante" > /app/VERSION.txt

EXPOSE 5003
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5003/api/v1/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
DOCKERFILE

echo "  ✅ Dockerfile.offline 已生成"

# 2. 构建镜像
echo ""
echo "[2/3] 构建 Docker 镜像（首次约 5-10 分钟）..."

docker build \
    -f Dockerfile.offline \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    --platform linux/amd64 \
    . 2>&1

echo "  ✅ 镜像构建完成: $IMAGE_NAME:$IMAGE_TAG"

# 3. 导出镜像
echo ""
echo "[3/3] 导出镜像为离线文件..."

docker save "$IMAGE_NAME:$IMAGE_TAG" -o "$EXPORT_FILE"
gzip -f "$EXPORT_FILE"

SIZE=$(du -sh "$EXPORT_FILE_GZ" | cut -f1)
echo "  ✅ $EXPORT_FILE_GZ ($SIZE)"

# 4. 生成部署说明
cat > "$SCRIPT_DIR/deploy_to_server.sh" << 'DEPLOY'
#!/bin/bash
# ============================================
# 目标服务器 (Oracle Linux 9.5 + Podman) 部署脚本
# 将此脚本和 .tar.gz 文件复制到目标服务器运行
# ============================================

set -e
IMAGE_FILE="acdante-db-inspector-latest.tar.gz"
IMAGE_NAME="acdante-db-inspector:latest"
CONTAINER_NAME="acdante-db-inspector"
HOST_PORT="${1:-5003}"

echo ">>> Acdante DB Inspector - Podman 部署"

# 加载镜像
echo ">>> [1/3] 加载镜像..."
gunzip -kf "$IMAGE_FILE" 2>/dev/null || true
podman load -i "${IMAGE_FILE%.gz}"
echo "  ✅ 镜像已加载"

# 创建持久化目录
echo ">>> [2/3] 创建数据目录..."
mkdir -p /opt/acdante/data /opt/acdante/pro_data /opt/acdante/reports

# 启动容器
echo ">>> [3/3] 启动容器..."
podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT:5003" \
    -v /opt/acdante/data:/app/data:Z \
    -v /opt/acdante/pro_data:/app/pro_data:Z \
    -v /opt/acdante/reports:/app/reports:Z \
    --restart always \
    "$IMAGE_NAME"

echo ""
echo "=========================================="
echo "  🎉 部署完成！"
echo "  访问: http://$(hostname -I | awk '{print $1}'):$HOST_PORT"
echo "  登录: http://$(hostname -I | awk '{print $1}'):$HOST_PORT/um/login"
echo "  管理员: admin / admin123"
echo ""
echo "  常用命令:"
echo "    podman logs $CONTAINER_NAME     # 查看日志"
echo "    podman restart $CONTAINER_NAME  # 重启"
echo "    podman stop $CONTAINER_NAME     # 停止"
echo "=========================================="
DEPLOY
chmod +x "$SCRIPT_DIR/deploy_to_server.sh"

# 清理临时文件
rm -f "$SCRIPT_DIR/Dockerfile.offline"

echo ""
echo "=========================================="
echo "  🎉 全部完成！"
echo ""
echo "  交付文件:"
echo "    1. $EXPORT_FILE_GZ  (Docker 镜像)"
echo "    2. deploy_to_server.sh    (服务器部署脚本)"
echo ""
echo "  部署步骤:"
echo "    1. 将上面两个文件复制到 Oracle Linux 服务器"
echo "    2. bash deploy_to_server.sh"
echo "=========================================="
