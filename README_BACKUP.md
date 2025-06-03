# MCSM Git备份功能使用说明

## 功能概述

本插件提供了完整的Minecraft服务器Git备份解决方案，包括：
- 自动备份到Git仓库
- 备份历史管理和清理
- 备份大小分析和增长预测
- 定时自动备份
- 版本回滚功能

## 环境变量配置

### 基础配置
```bash
# 启用Git备份
GIT_BACKUP_ENABLED=true

# 最大备份数量（超过后会提示或自动清理）
GIT_BACKUP_MAX_COUNT=10

# Git用户信息
GIT_BACKUP_USER_NAME="MCSM Bot"
GIT_BACKUP_USER_EMAIL="bot@mcsm.local"

# 服务器实例配置
MCSM_SLIMEFUN_ID="your_instance_id_here"
MCSM_BASE_PATH="/opt/mcsmanager/daemon/data/InstanceData"
MCSM_BACKUP_TARGET="full"  # "full" 或 "world"
```

### 高级配置
```bash
# 启用自动清理（删除超过限制的旧备份）
GIT_BACKUP_AUTO_CLEANUP=true

# 自定义备份路径（可选）
GIT_BACKUP_PATHS="slimefun:/path/to/backup/slimefun"
```

## 使用方式

### 1. 手动备份
```
/server_backup <服务器名> [备份描述]
```
例如：`/server_backup slimefun 添加新插件前的备份`

### 2. 查看备份信息
```
/backup_info [服务器名]     # 查看备份配置和状态
/backup_list <服务器名>     # 查看备份历史列表
/backup_analyze [服务器名]  # 分析备份大小和增长趋势
```

### 3. 版本回滚
```
/backup_rollback <服务器名> <版本号>
```
版本号可以是：
- 序号（如 1, 2, 3）
- Git提交hash（如 a1b2c3d4）

### 4. 自动备份管理
```
/auto_backup status                              # 查看状态
/auto_backup on <服务器名> [间隔分钟]           # 启用（默认360分钟=6小时）
/auto_backup off <服务器名>                     # 禁用
```

常用间隔参考：
- 15分钟 = 15
- 30分钟 = 30
- 1小时 = 60
- 6小时 = 360（推荐）
- 12小时 = 720

## Git仓库大小分析

### 不清理的增长情况
假设服务器存档大小为1GB，每次备份平均变化10%：

| 天数 | 备份次数 | 预估Git历史大小 | 总大小 |
|------|----------|----------------|--------|
| 7天  | 28次     | ~300MB         | 1.3GB  |
| 30天 | 120次    | ~1.2GB         | 2.2GB  |
| 90天 | 360次    | ~3.6GB         | 4.6GB  |
| 365天| 1460次   | ~14GB          | 15GB   |

### 启用自动清理的效果
配置`GIT_BACKUP_MAX_COUNT=10`时：
- Git历史大小稳定在 ~100MB
- 总大小稳定在 ~1.1GB
- 保留最近10个备份版本

## 最佳实践

### 1. 推荐配置
```bash
GIT_BACKUP_ENABLED=true
GIT_BACKUP_MAX_COUNT=20           # 保留20个版本
GIT_BACKUP_AUTO_CLEANUP=true      # 启用自动清理
MCSM_BACKUP_TARGET="world"        # 只备份存档目录
```

### 2. 备份策略
- **开发/测试服务器**：15-30分钟备份一次，保留50个版本
- **生产服务器**：1-6小时备份一次，保留20个版本
- **大型服务器**：只备份world目录，6-12小时备份一次

### 3. 存储管理
- 启用自动清理可节省70-90%的Git存储空间
- 定期使用`/backup_analyze`监控增长趋势
- 合理设置备份限制数量

## 安全特性

### 1. 自动清理安全机制
- 创建备份分支防止数据丢失
- 失败时自动回滚到原状态
- 使用孤儿分支重建历史，避免冲突

### 2. 备份安全保障
- 备份前自动执行`save-all`
- 等待20秒确保存档完成
- 检查文件变化后再提交

### 3. 回滚安全保障
- 回滚前自动停止服务器
- 创建临时备份分支
- 失败时自动恢复原状态

## 故障排除

### 1. 备份失败
```
❌ 备份路径创建失败: /path/to/backup
```
- 检查路径权限
- 确认磁盘空间充足

### 2. Git操作失败
```
❌ Git 操作失败: Command returned non-zero exit status
```
- 检查Git是否已安装
- 确认备份目录访问权限

### 3. 自动清理失败
```
⚠️ 清理失败，正在恢复...
```
- 通常会自动恢复，无需干预
- 可禁用自动清理改为手动管理

## 监控和优化

### 1. 定期检查
```bash
# 查看所有服务器备份概况
/backup_analyze

# 查看详细分析
/backup_analyze <服务器名>
```

### 2. 性能优化
- 根据分析结果调整备份频率
- 监控Git仓库大小增长
- 适时调整备份限制数量

### 3. 容量规划
使用`/backup_analyze`命令获取：
- 当前存储使用情况
- 平均增长速度
- 未来容量需求预测 