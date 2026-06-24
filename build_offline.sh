#!/bin/bash
# ============================================
# Acdante DB Inspector - 离线打包脚本 v3
# 使用 Docker Linux 环境，兼容 macOS / Windows
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d)
PACK_NAME="acdante-db-inspector-offline-${TIMESTAMP}"

echo "=========================================="
echo "  Acdante DB Inspector - 离线打包工具"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未找到 Docker"
    echo "   下载: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# 清理
rm -rf "$SCRIPT_DIR/$PACK_NAME" "$SCRIPT_DIR/$PACK_NAME.tar.gz"
mkdir -p "$SCRIPT_DIR/$PACK_NAME/wheels"

# 1. 用 Docker 下载 Linux 依赖
echo ""
echo "[1/3] Docker Linux 环境下载依赖包..."
echo "   (首次需拉取 python:3.11-slim 镜像，约 50MB)"

docker run --rm \
    -v "$SCRIPT_DIR/$PACK_NAME/wheels:/wheels" \
    python:3.11-slim \
    bash -c "
        pip config set global.index-url https://mirrors.aliyun.com/pypi/simple && \
        pip download -d /wheels \
            python-docx docxtpl psutil PyYAML cryptography \
            flask flask-socketio gevent pymysql psycopg2-binary \
            oracledb dmpython pyodbc paramiko openpyxl pandas \
            reportlab apscheduler PyPDF2 bcrypt PyJWT \
            gbase8sdb jaydebeapi JPype1 && \
        echo \"下载完成: \$(ls /wheels/*.whl | wc -l) 个包\"
    " 2>&1

echo "  ✅ 已下载 $(ls "$SCRIPT_DIR/$PACK_NAME/wheels"/*.whl 2>/dev/null | wc -l) 个 wheel 包"

# 2. 复制代码
echo ""
echo "[2/3] 复制项目代码..."
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app"
cd "$SCRIPT_DIR"

# 排除列表
SKIP=".git .github .pytest_cache __pycache__ awr_uploads reports snapshot data pro_data $PACK_NAME build_offline.sh"
for item in * .*; do
    [ "$item" = "." ] || [ "$item" = ".." ] && continue
    skip=0
    for s in $SKIP; do [ "$item" = "$s" ] && skip=1 && break; done
    [ $skip -eq 1 ] && continue
    cp -r "$item" "$SCRIPT_DIR/$PACK_NAME/app/" 2>/dev/null || true
done
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app/pro_data" "$SCRIPT_DIR/$PACK_NAME/app/data" "$SCRIPT_DIR/$PACK_NAME/app/reports"
echo "  ✅ 项目代码已复制"

# 3. 生成安装脚本 + 打包
echo ""
echo "[3/3] 生成安装脚本并打包..."

cat > "$SCRIPT_DIR/$PACK_NAME/install.sh" << 'INSTALL'
#!/bin/bash
set -e
SD="$(cd "$(dirname "$0")" && pwd)"
APP="/opt/acdante-db-inspector"
echo ">>> Acdante DB Inspector 离线安装"
echo ">>> [1/3] 安装依赖..."
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl --break-system-packages 2>/dev/null || \
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl
echo ">>> [2/3] 部署应用..."
mkdir -p "$APP"
cp -r "$SD/app/"* "$APP/"
echo ">>> [3/3] 初始化 RBAC..."
cd "$APP"
python3 -m user_management.seed
echo ""
echo "=========================================="
echo "  安装完成！启动: cd $APP && python3 web_ui.py"
echo "  访问: http://localhost:5003/um/login"
echo "  管理员: admin / admin123"
echo "=========================================="
INSTALL
chmod +x "$SCRIPT_DIR/$PACK_NAME/install.sh"

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

cd "$SCRIPT_DIR"
tar czf "$PACK_NAME.tar.gz" "$PACK_NAME"
rm -rf "$PACK_NAME"

echo "  ✅ $PACK_NAME.tar.gz ($(du -sh $PACK_NAME.tar.gz | cut -f1))"
echo ""
echo "=========================================="
echo "  🎉 打包完成！"
echo ""
echo "  部署步骤:"
echo "    1. 复制 $PACK_NAME.tar.gz 到目标 Linux 服务器"
echo "    2. tar xzf $PACK_NAME.tar.gz && cd $PACK_NAME"
echo "    3. bash install.sh"
echo "=========================================="
