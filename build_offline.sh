#!/bin/bash
# ============================================
# Acdante DB Inspector - 离线打包脚本
# 使用 Docker 在 Linux 环境中打包，兼容 macOS
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d)
PACK_NAME="acdante-db-inspector-offline-${TIMESTAMP}"

echo "=========================================="
echo "  Acdante DB Inspector - 离线打包工具"
echo "  (Docker Linux 环境，跨平台兼容)"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未找到 Docker，请先安装 Docker Desktop"
    echo "   下载: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# 清理
rm -rf "$SCRIPT_DIR/$PACK_NAME" "$SCRIPT_DIR/$PACK_NAME.tar.gz"

# 构建临时 Docker 镜像用于下载 Linux 依赖
echo ""
echo "[1/3] 使用 Docker Linux 环境下载依赖包..."
cat > /tmp/acdante_dockerfile << 'DOCKERFILE'
FROM python:3.11-slim
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /build
RUN mkdir -p wheels app
DOCKERFILE

cat > /tmp/acdante_download.sh << 'DLSH'
#!/bin/bash
set -e
echo ">>> 下载 Python 依赖包 (Linux x86_64)..."
pip download -d /build/wheels \
    python-docx docxtpl psutil PyYAML cryptography \
    flask flask-socketio gevent pymysql psycopg2-binary \
    oracledb dmpython pyodbc paramiko openpyxl pandas \
    reportlab apscheduler PyPDF2 bcrypt PyJWT \
    gbase8sdb jaydebeapi JPype1
echo ">>> 下载完成: $(ls /build/wheels/*.whl 2>/dev/null | wc -l) 个包"
DLSH

docker build -t acdante-packer -f /tmp/acdante_dockerfile . 2>&1 | tail -3
docker run --rm \
    -v "$SCRIPT_DIR/$PACK_NAME/wheels:/build/wheels" \
    -v /tmp/acdante_download.sh:/build/download.sh \
    python:3.11-slim \
    bash -c "
        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
        bash /build/download.sh
    " 2>&1

echo "  ✅ 已下载 $(ls "$SCRIPT_DIR/$PACK_NAME/wheels"/*.whl 2>/dev/null | wc -l) 个 Linux wheel 包"

# 复制代码
echo ""
echo "[2/3] 复制项目代码..."
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app"
cd "$SCRIPT_DIR"
for item in * .*; do
    [ "$item" = "." ] || [ "$item" = ".." ] || [ "$item" = ".git" ] || [ "$item" = ".github" ] && continue
    [ -d "$item" ] && [[ "$item" == "$PACK_NAME" ]] && continue
    cp -r "$item" "$SCRIPT_DIR/$PACK_NAME/app/" 2>/dev/null || true
done
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app/pro_data" "$SCRIPT_DIR/$PACK_NAME/app/data" "$SCRIPT_DIR/$PACK_NAME/app/reports"
echo "  ✅ 项目代码已复制"

# 生成安装脚本
echo ""
echo "[3/3] 生成安装脚本并打包..."
cat > "$SCRIPT_DIR/$PACK_NAME/install.sh" << 'INSTEOF'
#!/bin/bash
set -e
SD="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="/opt/acdante-db-inspector"
echo ">>> Acdante DB Inspector 离线安装"
echo ">>> [1/3] 安装依赖..."
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl --break-system-packages 2>/dev/null || \
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl
echo ">>> [2/3] 部署应用..."
mkdir -p "$APP_DIR"
cp -r "$SD/app/"* "$APP_DIR/"
echo ">>> [3/3] 初始化 RBAC..."
cd "$APP_DIR"
python3 -m user_management.seed
echo ""
echo "=========================================="
echo "  安装完成！"
echo "  启动: cd $APP_DIR && python3 web_ui.py"
echo "  访问: http://localhost:5003/um/login"
echo "  管理员: admin / admin123"
echo "=========================================="
INSTEOF
chmod +x "$SCRIPT_DIR/$PACK_NAME/install.sh"

# systemd 服务
cat > "$SCRIPT_DIR/$PACK_NAME/app/acdante-db-inspector.service" << 'SVC'
[Unit]
Description=Acdante DB Inspector
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/acdante-db-inspector
ExecStart=/usr/bin/python3 /opt/acdante-db-inspector/web_ui.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
SVC

# 打包
cd "$SCRIPT_DIR"
tar czf "$PACK_NAME.tar.gz" "$PACK_NAME"
rm -rf "$PACK_NAME"

echo ""
echo "=========================================="
echo "  🎉 打包完成！"
echo "  文件: $SCRIPT_DIR/$PACK_NAME.tar.gz ($(du -sh $PACK_NAME.tar.gz | cut -f1))"
echo ""
echo "  部署步骤:"
echo "    1. 复制 $PACK_NAME.tar.gz 到目标 Linux 服务器"
echo "    2. tar xzf $PACK_NAME.tar.gz"
echo "    3. cd $PACK_NAME"
echo "    4. bash install.sh"
echo "=========================================="
