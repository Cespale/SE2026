@echo off
echo ================================
echo   StreamHub CI/CD 简单测试
echo ================================
echo.

echo 步骤 1: 进入后端目录并安装依赖
cd backend
echo 当前目录: %CD%
pip install -r requirements.txt
echo 后端依赖安装完成
echo.

echo 步骤 2: 返回根目录并安装前端依赖
cd ..
echo 当前目录: %CD%
npm ci
echo 前端依赖安装完成
echo.

echo 步骤 3: 执行 TypeScript 检查
npm run typecheck
echo TypeScript 检查完成
echo.

echo 步骤 4: 编译前端代码
npm run build
echo 前端编译完成
echo.

echo 步骤 5: 检查编译结果
if exist "dist" (
    echo [OK] dist 目录已创建
    dir dist
) else (
    echo [ERROR] dist 目录不存在
)

echo.
echo ================================
echo   测试完成！
echo ================================
pause