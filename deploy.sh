#!/bin/bash
# -*- coding: utf-8 -*-
# 部署脚本 v2.3.0

set -e

echo "========================================="
echo "数字孪生风控风洞 v2.3.0 部署脚本"
echo "========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: docker-compose 未安装${NC}"
    echo "请先安装 docker-compose"
    exit 1
fi

# 检查.env文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}警告: .env 文件不存在，使用默认配置${NC}"
    cat > .env << EOF
GEMINI_API_KEY=your_api_key_here
SECRET_KEY=change-this-secret-key-$(openssl rand -hex 16)
POSTGRES_PASSWORD=change-this-password-$(openssl rand -hex 12)
EOF
    echo -e "${GREEN}已创建 .env 文件，请编辑并填入实际配置${NC}"
fi

echo "1. 停止现有容器..."
docker-compose down

echo ""
echo "2. 构建镜像..."
docker-compose build

echo ""
echo "3. 启动服务..."
docker-compose up -d

echo ""
echo "4. 等待服务就绪..."
sleep 5

echo ""
echo "5. 检查服务状态..."
docker-compose ps

echo ""
echo "========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "========================================="
echo ""
echo "访问地址:"
echo "  主页:    http://localhost:8080"
echo "  监控台:  http://localhost:8080/dashboard"
echo "  批量测试: http://localhost:8080/batch-test"
echo "  API文档: http://localhost:8080/api-docs"
echo ""
echo "查看日志: docker-compose logs -f app"
echo "停止服务: docker-compose down"
echo ""
