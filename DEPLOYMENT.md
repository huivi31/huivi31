# 部署指南 | Deployment Guide

## 🚀 快速开始

### 1. 环境要求
- Python 3.11+
- pip 或 conda
- (可选) Docker

### 2. 本地部署

```bash
# 克隆仓库
git clone https://github.com/huivi31/huivi31.git
cd huivi31

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件,设置:
# - JWT_SECRET (务必修改!)
# - GEMINI_API_KEY 或 OPENAI_API_KEY

# 启动服务
python web_app.py
# 或使用 gunicorn (生产环境)
gunicorn web_app:app --bind 0.0.0.0:8000 --workers 4
```

访问: http://localhost:8000

---

## 🔐 安全配置

### JWT密钥设置
```bash
# 生成强随机密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 在 .env 中设置
JWT_SECRET=your_generated_secret_here
```

### 默认账号
| 用户名 | 密码 | 角色 |
|--------|------|------|
| demo | demo123 | user |
| admin | admin123 | admin |

⚠️ **生产环境务必修改默认密码!**

---

## 🐳 Docker部署 (推荐)

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "web_app:app", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 运行
```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

---

## 🌐 Render部署 (当前线上环境)

### 配置
1. 连接GitHub仓库
2. 设置构建命令: `pip install -r requirements.txt`
3. 设置启动命令: `gunicorn web_app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. 添加环境变量:
   ```
   JWT_SECRET=your_secret
   GEMINI_API_KEY=your_key
   OPENAI_API_KEY=your_key (可选)
   ```

### 访问
- 生产URL: https://your-app.onrender.com
- 健康检查: https://your-app.onrender.com/health

---

## 📊 性能优化

### Gunicorn配置
```bash
gunicorn web_app:app \
  --bind 0.0.0.0:8000 \
  --workers 4 \              # CPU核心数 * 2 + 1
  --threads 2 \               # 每个worker的线程数
  --worker-class sync \       # 或 gevent 用于更高并发
  --timeout 120 \             # 超时时间(秒)
  --max-requests 1000 \       # 自动重启worker
  --max-requests-jitter 50 \
  --access-logfile - \        # 访问日志
  --error-logfile - \         # 错误日志
  --log-level info
```

### 环境变量优化
```bash
# 限制文档上传大小(MB)
MAX_DOC_UPLOAD_MB=512

# 日志级别
LOG_LEVEL=INFO  # DEBUG/INFO/WARNING/ERROR

# Flask环境
FLASK_ENV=production
```

---

## 🔧 故障排查

### 常见问题

#### 1. API密钥错误
```
错误: [API错误 401] Invalid API key
解决: 检查 .env 中的 GEMINI_API_KEY 或 OPENAI_API_KEY
```

#### 2. 端口占用
```
错误: Address already in use
解决: 更改端口或杀掉占用进程
lsof -ti:8000 | xargs kill -9
```

#### 3. 依赖安装失败
```
错误: Failed building wheel for xxx
解决: 
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

#### 4. JWT认证失败
```
错误: Invalid or expired token
解决: 
1. 检查 JWT_SECRET 是否设置
2. 重新登录获取新token
3. 确认token未过期(默认24小时)
```

### 日志查看
```bash
# 实时查看日志
tail -f logs/app.log

# 搜索错误
grep ERROR logs/app.log
```

---

## 📈 监控建议

### 健康检查
```bash
# 定期检查服务状态
curl http://localhost:8000/health

# 响应示例:
{
  "status": "ok",
  "version": "2.1.0",
  "timestamp": "2026-03-02T12:00:00",
  "system": {
    "rules": 10,
    "agents": 72,
    "knowledge": 5
  }
}
```

### Prometheus指标 (规划中)
```
# 计划在 v2.2.0 添加
/metrics - Prometheus格式指标
```

---

## 🔄 更新升级

### 从v2.0升级到v2.1
```bash
# 1. 拉取最新代码
git pull origin main

# 2. 安装新依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 设置 JWT_SECRET

# 4. 重启服务
# 使用 systemd
sudo systemctl restart digital-twin

# 或使用 supervisor
supervisorctl restart digital-twin

# 或手动重启
pkill -f gunicorn
gunicorn web_app:app --bind 0.0.0.0:8000 --workers 4 &
```

### 数据迁移
v2.1.0向后兼容,无需数据迁移。

---

## 🆘 技术支持

- **问题反馈**: https://github.com/huivi31/huivi31/issues
- **在线演示**: https://digital-twin-risk-demo.onrender.com/
- **文档**: 查看 README.md, v2.0_GUIDE.md, CHANGELOG.md

---

## 📝 生产环境检查清单

部署到生产前请确认:

- [ ] 已修改默认JWT_SECRET
- [ ] 已修改默认账号密码
- [ ] 已配置正确的API密钥
- [ ] 已设置合理的worker数量
- [ ] 已配置日志目录权限
- [ ] 已设置健康检查
- [ ] 已配置HTTPS(推荐)
- [ ] 已设置防火墙规则
- [ ] 已配置备份策略
- [ ] 已测试基本功能

---

**祝部署顺利!** 🎉
