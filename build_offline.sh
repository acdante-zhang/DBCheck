#!/bin/bash
# ============================================
# Acdante DB Inspector - 离线打包脚本 v2
# 在有网络的环境中运行，生成离线部署包
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d)
PACK_NAME="acdante-db-inspector-offline-${TIMESTAMP}"
OUTPUT_DIR="$SCRIPT_DIR/$PACK_NAME"

echo "=========================================="
echo "  Acdante DB Inspector - 离线打包工具"
echo "=========================================="

# 清理
rm -rf "$OUTPUT_DIR" "$OUTPUT_DIR.tar.gz"
mkdir -p "$OUTPUT_DIR/wheels"
mkdir -p "$OUTPUT_DIR/app"

# 1. 下载依赖
echo ""
echo "[1/4] 下载 Python 依赖包（49 个，约 250MB，请耐心等待）..."
echo "   正在下载中..."
cat > /tmp/acdante_reqs.txt << 'REQS'
python-docx>=0.8.10
docxtpl>=0.16.0
psutil>=5.9.0
PyYAML>=6.0.0
cryptography>=41.0.0
flask>=2.0.0
flask-socketio>=5.0.0
gevent>=24.0.0
pymysql>=1.0.0
psycopg2-binary>=2.9.0
oracledb>=1.4.0
dmpython>=1.0.0
pyodbc>=4.0.0
paramiko>=2.10.0
openpyxl>=3.0.0
pandas>=1.3.0
reportlab>=4.0.0
apscheduler>=3.10.0
PyPDF2>=3.0.1
bcrypt>=4.0.0
PyJWT>=2.7.0
REQS
pip3 download --progress-bar on \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -d "$OUTPUT_DIR/wheels" -r /tmp/acdante_reqs.txt
echo ""
echo "  ✅ 已下载 $(ls "$OUTPUT_DIR/wheels"/*.whl 2>/dev/null | wc -l) 个 wheel 包"

# 2. 复制代码
echo ""
echo "[2/4] 复制项目代码..."
cd "$SCRIPT_DIR"
EXCLUDES=".git .github .pytest_cache __pycache__ awr_uploads reports snapshot data pro_data offline_pack build_offline.sh *.tar.gz *.pyc"
for item in * .*; do
    [ "$item" = "." ] || [ "$item" = ".." ] && continue
    skip=0
    for ex in $EXCLUDES; do
        [[ "$item" == $ex ]] && skip=1 && break
    done
    [ $skip -eq 1 ] && continue
    cp -r "$item" "$OUTPUT_DIR/app/" 2>/dev/null || true
done
mkdir -p "$OUTPUT_DIR/app/pro_data" "$OUTPUT_DIR/app/data" "$OUTPUT_DIR/app/reports"
echo "  ✅ 项目代码已复制"

# 3. 创建安装脚本
echo ""
echo "[3/4] 生成离线安装脚本..."
cat > "$OUTPUT_DIR/install.sh" << 'INSTEOF'
#!/bin/bash
set -e
SD="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="/opt/acdante-db-inspector"
echo ">>> Acdante DB Inspector 离线安装"
echo ">>> Python: $(python3 --version 2>&1)"
echo ">>> [1/3] 安装依赖..."
python3 -m pip install --no-index --find-links="$SD/wheels" "$SD/wheels"/*.whl --break-system-packages 2>&1 | tail -3
echo ">>> [2/3] 部署应用..."
mkdir -p "$APP_DIR"
cp -r "$SD/app/"* "$APP_DIR/"
echo ">>> [3/3] 初始化 RBAC..."
cd "$APP_DIR"
python3 -m user_management.seed
echo ""
echo "=========================================="
echo "  安装完成！启动: cd $APP_DIR && python3 web_ui.py"
echo "  访问: http://localhost:5003/um/login"
echo "  管理员: admin / admin123"
echo "=========================================="
INSTEOF
chmod +x "$OUTPUT_DIR/install.sh"

# 4. systemd 服务
cat > "$OUTPUT_DIR/app/acdante-db-inspector.service" << 'SVC'
[Unit]
Description=Acdante DB Inspector
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/acdante-db-inspector
ExecStart=/usr/bin/python3 /opt/acdante-db-inspector/web_ui.py
Restart=always
RestartSec=5
Environment=FLASK_ENV=production
[Install]
WantedBy=multi-user.target
SVC
echo "  ✅ 安装脚本和服务文件已生成"

# 5. 打包
echo ""
echo "[4/4] 打包压缩..."
cd "$SCRIPT_DIR"
tar czf "$PACK_NAME.tar.gz" "$PACK_NAME"
echo "  ✅ $PACK_NAME.tar.gz ($(du -sh $PACK_NAME.tar.gz | cut -f1))"

echo ""
echo "=========================================="
echo "  离线部署包: $SCRIPT_DIR/$PACK_NAME.tar.gz"
echo ""
echo "  部署: tar xzf $PACK_NAME.tar.gz && cd $PACK_NAME && bash install.sh"
echo "=========================================="
