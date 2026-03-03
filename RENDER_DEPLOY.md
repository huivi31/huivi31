# 🚀 Render 部署指南

## 方式1: 自动部署（推荐）

### 步骤1: 准备工作
1. 注册/登录 [Render.com](https://render.com/)
2. 确保你的GitHub仓库已经有最新代码

### 步骤2: 创建Web Service
1. 在Render Dashboard点击 **"New +"** → **"Web Service"**
2. 连接GitHub仓库: `huivi31/huivi31`
3. 选择分支: `main`

### 步骤3: 配置服务
- **Name**: `digital-twin-risk-wind-tunnel`
- **Region**: `Oregon (US West)`
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**: 
  ```bash
  pip install -r requirements.txt && python -c "from database import db; db.initialize(); db.create_tables()"
  ```
- **Start Command**: 
  ```bash
  python web_app.py
  ```

### 步骤4: 配置环境变量
在 **Environment** 标签页添加：

| Key | Value | 说明 |
|-----|-------|------|
| `GEMINI_API_KEY` | `你的API密钥` | ⚠️ 必填 |
| `SECRET_KEY` | `随机密钥` | 自动生成或自定义 |
| `PORT` | `8080` | 端口号 |
| `FLASK_ENV` | `production` | 环境 |

### 步骤5: 部署
1. 点击 **"Create Web Service"**
2. 等待3-5分钟完成构建和部署
3. 部署完成后会得到访问URL

---

## 方式2: 使用render.yaml自动配置

### 步骤1: 确认配置文件
仓库中已包含 `render.yaml`，Render会自动读取。

### 步骤2: 一键部署
1. 登录 [Render Dashboard](https://dashboard.render.com/)
2. 点击 **"New +"** → **"Blueprint"**
3. 选择GitHub仓库: `huivi31/huivi31`
4. Render自动检测 `render.yaml`
5. 配置 `GEMINI_API_KEY` 环境变量
6. 点击 **"Apply"**

---

## 方式3: 使用PostgreSQL数据库（生产环境）

### 步骤1: 创建PostgreSQL数据库
1. 在Render Dashboard点击 **"New +"** → **"PostgreSQL"**
2. 配置：
   - **Name**: `digital-twin-db`
   - **Database**: `digital_twin`
   - **User**: `dtuser`
   - **Region**: `Oregon (US West)`
   - **Plan**: `Free` 或 `Starter`

### 步骤2: 连接数据库到Web Service
1. 在Web Service的 **Environment** 添加：
   - Key: `DATABASE_URL`
   - Value: 选择 "Add from database" → 选择刚创建的数据库

### 步骤3: 重新部署
数据库连接会自动配置，重启服务即可。

---

## 环境变量说明

### 必需变量
- `GEMINI_API_KEY`: Gemini API密钥（从Google AI Studio获取）
  - 获取地址: https://makersuite.google.com/app/apikey

### 可选变量
- `SECRET_KEY`: JWT密钥（自动生成或自定义）
- `DATABASE_URL`: 数据库连接串（默认使用SQLite）
- `PORT`: 端口号（默认8080）
- `FLASK_ENV`: 环境（development / production）

---

## 健康检查

Render会自动监控服务健康状态：
- **端点**: `/api/db/health`
- **间隔**: 30秒
- **超时**: 10秒

---

## 部署后验证

### 1. 检查服务状态
访问: `https://your-app.onrender.com/api/db/health`

预期响应:
```json
{
  "success": true,
  "status": "healthy",
  "info": {
    "database": "postgresql",
    "status": "connected",
    "healthy": true
  }
}
```

### 2. 访问应用
- 主页: `https://your-app.onrender.com/`
- Dashboard: `https://your-app.onrender.com/dashboard`
- API文档: `https://your-app.onrender.com/api-docs`

### 3. 测试功能
1. 登录账号（demo / demo123）
2. 运行一次攻防测试
3. 查看Dashboard统计

---

## 常见问题

### Q1: 构建失败
**原因**: 缺少依赖或Python版本不匹配
**解决**: 
```bash
# 在 Environment 添加
PYTHON_VERSION=3.10.0
```

### Q2: 启动超时
**原因**: 数据库初始化时间过长
**解决**: 
- 使用SQLite（默认）
- 或增加启动超时时间

### Q3: API密钥错误
**原因**: `GEMINI_API_KEY` 未配置或无效
**解决**: 
1. 检查环境变量是否正确设置
2. 确认API密钥有效
3. 重启服务

### Q4: 内存超限（Free Plan）
**原因**: Free Plan限制512MB内存
**解决**: 
- 升级到Starter Plan ($7/月)
- 或优化内存使用

---

## 监控和日志

### 查看日志
1. 进入Web Service页面
2. 点击 **"Logs"** 标签
3. 实时查看应用日志

### 监控指标
Render提供：
- CPU使用率
- 内存使用率
- 请求数量
- 响应时间

---

## 自动部署

### 启用自动部署
1. 在Web Service设置中
2. 开启 **"Auto-Deploy"**
3. 每次推送到`main`分支会自动部署

### 禁用自动部署
如果需要手动控制部署：
1. 关闭 **"Auto-Deploy"**
2. 手动点击 **"Manual Deploy"** 触发部署

---

## 成本估算

### Free Plan
- ✅ 免费
- ⚠️ 512MB RAM
- ⚠️ 无活动15分钟后休眠
- ✅ 适合演示和测试

### Starter Plan ($7/月)
- ✅ 足够的资源
- ✅ 不会休眠
- ✅ 更好的性能
- ✅ 适合生产环境

---

## 升级建议

当遇到以下情况时，建议升级：
1. 并发用户>10
2. 需要24/7在线
3. 需要更快的响应
4. 需要PostgreSQL数据库

---

## 获取帮助

- **Render文档**: https://render.com/docs
- **项目Issues**: https://github.com/huivi31/huivi31/issues
- **技术支持**: support@render.com

---

## 快速链接

- 🌐 **Render Dashboard**: https://dashboard.render.com/
- 📚 **文档**: https://render.com/docs
- 💬 **社区**: https://community.render.com/
- 📖 **项目README**: https://github.com/huivi31/huivi31

---

**祝部署顺利！🚀**
