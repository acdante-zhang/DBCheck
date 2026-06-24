#!/bin/bash
# ============================================
# Acdante DB Inspector - 本地离线打包 (无需 Docker)
# 在 macOS 上运行，排除 Linux 专有包
# 目标服务器需自行安装 dmpython/gbase8sdb
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d)
PACK_NAME="acdante-db-inspector-offline-${TIMESTAMP}"

echo "=========================================="
echo "  Acdante DB Inspector - 本地离线打包"
echo "=========================================="

rm -rf "$SCRIPT_DIR/$PACK_NAME" "$SCRIPT_DIR/$PACK_NAME.tar.gz"
mkdir -p "$SCRIPT_DIR/$PACK_NAME/wheels"
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app"

# 1. 下载通用依赖（排除 Linux 专有包）
echo ""
echo "[1/4] 下载通用 Python 依赖包..."
pip3 download --progress-bar on \
    -i https://mirrors.aliyun.com/pypi/simple \
    --trusted-host mirrors.aliyun.com \
    -d "$SCRIPT_DIR/$PACK_NAME/wheels" \
    python-docx docxtpl psutil PyYAML cryptography \
    flask flask-socketio gevent pymysql psycopg2-binary \
    oracledb pyodbc paramiko openpyxl pandas \
    reportlab apscheduler PyPDF2 bcrypt PyJWT

echo "  ✅ 已下载 $(ls "$SCRIPT_DIR/$PACK_NAME/wheels"/*.whl 2>/dev/null | wc -l) 个包"

# 2. 额外下载 Linux 专有包的纯 Python 版本（如果可用）
echo ""
echo "[2/4] 尝试下载 Linux 专有包..."
for pkg in dmpython gbase8sdb jaydebeapi JPype1; do
    pip3 download --progress-bar off \
        -i https://mirrors.aliyun.com/pypi/simple \
        --trusted-host mirrors.aliyun.com \
        --only-binary=:all: --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 \
        --python-version 311 --implementation cp --abi cp311 \
        -d "$SCRIPT_DIR/$PACK_NAME/wheels" "$pkg" 2>/dev/null && echo "    ✅ $pkg" || echo "    ⚠️  $pkg 跳过 (需目标服务器手动安装)"
done
echo "  ✅ 共 $(ls "$SCRIPT_DIR/$PACK_NAME/wheels"/*.whl 2>/dev/null | wc -l) 个包"

# 3. 复制代码
echo ""
echo "[3/4] 复制项目代码..."
cd "$SCRIPT_DIR"
SKIP=".git .github .pytest_cache __pycache__ awr_uploads reports snapshot data pro_data $PACK_NAME build_offline.sh build_offline_nodocker.sh *.tar.gz"
for item in * .*; do
    [ "$item" = "." ] || [ "$item" = ".." ] && continue
    s=0; for x in $SKIP; do [ "$item" = "$x" ] && s=1 && break; done
    [ $s -eq 1 ] && continue
    cp -r "$item" "$SCRIPT_DIR/$PACK_NAME/app/" 2>/dev/null || true
done
mkdir -p "$SCRIPT_DIR/$PACK_NAME/app/pro_data" "$SCRIPT_DIR/$PACK_NAME/app/data" "$SCRIPT_DIR/$PACK_NAME/app/reports"
echo "  ✅ 项目代码已复制"

# 4. 安装脚本
echo ""
echo "[4/4] 生成安装脚本并打包..."

cat > "$SCRIPT_DIR/$PACK_NAME/install.sh" << 'INSTALL'
#!/bin/bash
set -e
SD="$(cd "$(dirname "$0")" && pwd)"
APP="/opt/acdante-db-inspector"

echo ">>> Acdante DB Inspector 离线安装"
echo ">>> [1/4] 安装通用依赖..."
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl --break-system-packages 2>/dev/null || \
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl

echo ">>> [2/4] 检查数据库驱动..."
python3 -c "import pymysql; print('  ✅ MySQL/TiDB')" 2>/dev/null || echo "  ⚠️ MySQL"
python3 -c "import psycopg2; print('  ✅ PostgreSQL')" 2>/dev/null || echo "  ⚠️ PostgreSQL"
python3 -c "import oracledb; print('  ✅ Oracle')" 2>/dev/null || echo "  ⚠️ Oracle"
python3 -c "import pyodbc; print('  ✅ SQL Server')" 2>/dev/null || echo "  ⚠️ SQL Server"

echo ">>> [3/4] 部署应用..."
mkdir -p "$APP"
cp -r "$SD/app/"* "$APP/"

echo ">>> [4/4] 初始化 RBAC..."
cd "$APP"
python3 -m user_management.seed

echo ""
echo "=========================================="
echo "  安装完成！"
echo "  启动: cd $APP && python3 web_ui.py"
echo "  访问: http://localhost:5003/um/login"
echo "  管理员: admin / admin123"
echo ""
echo "  如需 DM8/Kingbase/GBase 支持，手动安装驱动:"
echo "    pip install dmpython gbase8sdb jaydebeapi JPype1"
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
echo "  部署: tar xzf $PACK_NAME.tar.gz && cd $PACK_NAME && bash install.sh"
echo "=========================================="
