# Acdante DB Inspector — 私有化部署手册

> **机密文档** — 仅供授权人员使用  
> 版本: v2.7.0-acdante | 日期: 2026-06-24

---

## 一、项目概述

Acdante DB Inspector 是基于开源项目二次开发的私有化数据库健康巡检平台，已完整替换品牌标识、版权信息和许可协议。

### 版本对比

| 维度 | 开源版 (DBCheck) | 私有版 (Acdante) |
|------|------------------|-------------------|
| 仓库分支 | `feature/user-management` | `feature/acdante-private` |
| 品牌标识 | DBCheck | Acdante DB Inspector |
| 许可证 | MIT | Proprietary (私有) |
| 前端版权 | 显示 | **隐藏** |
| 功能 | 相同 | 相同 |

---

## 二、获取代码

### 2.1 从 GitHub 下载

```bash
# 克隆仓库（私有仓库需要认证）
git clone https://github.com/acdante-zhang/DBCheck.git
cd DBCheck
git checkout feature/acdante-private
```

### 2.2 从 Gitee 下载

```bash
git clone https://gitee.com/acdante/DBCheck.git
cd DBCheck
git checkout feature/acdante-private
```

### 2.3 下载 ZIP 包

访问 https://github.com/acdante-zhang/DBCheck/tree/feature/acdante-private  
点击 "Code" → "Download ZIP"

---

## 三、Docker 部署（推荐）

### 3.1 构建并启动

```bash
cd DBCheck
git checkout feature/acdante-private

# 构建镜像
docker build -t acdante/db-inspector:latest .

# 使用 docker-compose 启动
docker-compose up -d
```

### 3.2 手动运行容器

```bash
docker run -d \
  --name acdante-db-inspector \
  -p 5003:5003 \
  -v acdante_data:/app/data \
  -v acdante_pro_data:/app/pro_data \
  -v acdante_reports:/app/reports \
  acdante/db-inspector:latest
```

### 3.3 访问服务

| 地址 | 说明 |
|------|------|
| http://localhost:5003 | 主页面 |
| http://localhost:5003/um/login | 登录页 |
| http://localhost:5003/um/admin | 管理后台 |

---

## 四、本地部署

### 4.1 环境要求

- Python 3.9+
- pip
- SQLite 3

### 4.2 安装步骤

```bash
cd DBCheck
git checkout feature/acdante-private

# 安装依赖
pip install -r requirements.txt

# 初始化 RBAC 用户数据
python -m user_management.seed

# 启动服务
python web_ui.py
```

---

## 五、默认账户

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `admin123` | 系统管理员 | 拥有所有权限 |
| `viewer` | `viewer123` | 只读用户 | 只能查看 |
| `operator` | `operator123` | 运维人员 | 可读写 |

> ⚠️ **安全提醒**：首次部署后请立即修改默认密码！

---

## 六、数据持久化

### Docker Volume

| Volume | 容器路径 | 内容 |
|--------|----------|------|
| `acdante_data` | `/app/data` | 巡检数据 |
| `acdante_pro_data` | `/app/pro_data` | RBAC 用户数据库 |
| `acdante_reports` | `/app/reports` | 巡检报告 |

### 备份命令

```bash
# 备份 RBAC 用户数据
docker run --rm -v acdante_pro_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/acdante_pro_data_$(date +%Y%m%d).tar.gz -C /data .

# 恢复
docker run --rm -v acdante_pro_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/acdante_pro_data_20260624.tar.gz -C /data
```

---

## 七、品牌替换清单

以下内容已在私有化版本中完成替换：

| 替换项 | 原内容 | 新内容 |
|--------|--------|--------|
| 产品名 | DBCheck | Acdante DB Inspector |
| 版权归属 | fiyo (Jack Ge) | Acdante |
| 许可证 | MIT License | Proprietary |
| 前端页脚 | 显示版权 | **隐藏** |
| Docker 镜像 | jackge12345/dbcheck | acdante/db-inspector |
| Docker 卷 | dbcheck_* | acdante_* |
| 版本号 | v2.7.0 | v2.7.0-acdante |

---

## 八、常见问题

**Q: 如何重置所有数据？**
```bash
# Docker
docker-compose down -v
docker-compose up -d

# 本地
rm -f pro_data/um_rbac.db pro_data/.rbac_seeded
python -m user_management.seed
```

**Q: 忘记管理员密码？**
```bash
docker exec -it acdante-db-inspector sh
rm -f /app/pro_data/um_rbac.db /app/pro_data/.rbac_seeded
python -m user_management.seed
exit
# 密码重置为 admin123
```

**Q: 如何更改端口？**
修改 `docker-compose.yml` 中 `ports` 配置，如改为 8080：
```yaml
ports:
  - "8080:5003"
```

**Q: 如何确认是私有化版本？**
访问 http://localhost:5003，页面标题显示 "Acdante DB Inspector"，页脚无版权信息。

---

## 九、联系信息

- 技术支持: 请联系 Acdante 团队
- 代码仓库: https://github.com/acdante-zhang/DBCheck (分支: feature/acdante-private)
