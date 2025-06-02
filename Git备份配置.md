# MCSM Git 备份配置指南

## 🚀 新功能：动态路径生成

现在支持根据 MCSM 实例 ID 自动生成备份路径，无需手动配置每个服务器！

## 📝 环境变量配置

### 基础配置
```bash
# 启用 Git 备份功能
GIT_BACKUP_ENABLED=true

# 最大备份数量
GIT_BACKUP_MAX_COUNT=10

# Git 提交者信息
GIT_BACKUP_USER_NAME=MCSM Bot
GIT_BACKUP_USER_EMAIL=bot@mcsm.local
```

### 动态路径配置（推荐）
```bash
# MCSM 实例数据基础路径
MCSM_BASE_PATH=/opt/mcsmanager/daemon/data/InstanceData

# 备份目标：'full' 备份整个服务器，'world' 只备份存档
MCSM_BACKUP_TARGET=full
```

### 手动路径配置（可选）
```bash
# 如果需要特殊路径，可以手动指定
GIT_BACKUP_PATHS=slimefun:/custom/path/to/server
```

## 🔧 配置示例

### 完整配置示例
```bash
# MCSM 基础配置
MCSM_URL=http://localhost:23333
MCSM_APIKEY=your_api_key_here
MCSM_DAEMON_ID=your_daemon_id_here
MCSM_SLIMEFUN_ID=f645c80e421f4fea8997ba6eb53644b7

# Git 备份配置（动态模式）
GIT_BACKUP_ENABLED=true
GIT_BACKUP_MAX_COUNT=15
GIT_BACKUP_USER_NAME=服务器管理员
GIT_BACKUP_USER_EMAIL=admin@yourserver.com
MCSM_BASE_PATH=/opt/mcsmanager/daemon/data/InstanceData
MCSM_BACKUP_TARGET=full
```

## 📁 路径生成规则

### 完整服务器备份 (MCSM_BACKUP_TARGET=full)
```
实例ID: f645c80e421f4fea8997ba6eb53644b7
备份路径: /opt/mcsmanager/daemon/data/InstanceData/f645c80e421f4fea8997ba6eb53644b7/
```

### 仅存档备份 (MCSM_BACKUP_TARGET=world)
```
实例ID: f645c80e421f4fea8997ba6eb53644b7
备份路径: /opt/mcsmanager/daemon/data/InstanceData/f645c80e421f4fea8997ba6eb53644b7/world/
```

## 🎯 优势

### 动态路径的好处
1. ✅ **自动化**: 无需手动配置每个服务器路径
2. ✅ **标准化**: 使用 MCSM 标准目录结构
3. ✅ **灵活性**: 支持完整备份或仅存档备份
4. ✅ **维护性**: 添加新服务器时无需更新配置

### 备份目标选择
- **full**: 备份整个服务器（推荐）
  - 包含插件、配置、存档等所有文件
  - 适合生产环境完整备份
  
- **world**: 仅备份存档
  - 只备份世界数据
  - 适合频繁备份或存储空间有限的情况

## 📋 使用方法

### 查看备份配置
```
/backup_info
```

### 查看特定服务器备份信息
```
/backup_info slimefun
```

### 执行备份
```
/server_backup slimefun
/server_backup slimefun 更新粘液科技插件
```

### 查看备份历史
```
/backup_list slimefun
```

### 回滚到指定版本
```
# 使用序号回滚（推荐）
/backup_rollback slimefun 3

# 使用提交hash回滚
/backup_rollback slimefun a1b2c3d4
```

## 🔄 回滚功能详解

### 回滚流程
1. **自动停服**：如果服务器正在运行，自动停止
2. **安全检查**：验证目标版本是否存在
3. **创建备份点**：为当前状态创建临时备份
4. **执行回滚**：使用Git回滚到指定版本
5. **自动开服**：如果原来在运行，自动重启服务器

### 版本号格式
- **序号**：`1`, `2`, `3`... (对应备份历史列表中的序号)
- **提交hash**：`a1b2c3d4`, `abc123def`... (Git提交的完整或部分hash)

### 安全特性
- ✅ **自动服务器控制**：智能停启服务器
- ✅ **状态保持**：保持原有的服务器运行状态
- ✅ **失败回滚**：操作失败时自动恢复
- ✅ **临时备份**：回滚前自动创建安全点

## 🔍 路径优先级

系统按以下优先级选择备份路径：

1. **手动指定路径** (`GIT_BACKUP_PATHS` 中的具体配置)
2. **动态生成路径** (基于 `MCSM_BASE_PATH` + 实例ID)
3. **基础路径** (`GIT_BACKUP_PATHS` 作为基础目录)
4. **错误** (无有效配置)

## ⚠️ 注意事项

1. **权限**: 确保机器人进程对目标目录有读写权限
2. **路径**: Linux 环境使用 `/`，Windows 使用 `\` 或 `/`
3. **空间**: 定期检查备份目录大小
4. **安全**: 建议定期推送到远程Git仓库

## 🛠️ 故障排除

### 常见问题
1. **"未配置备份路径"**
   - 检查 `MCSM_BASE_PATH` 配置
   - 确认服务器实例ID正确

2. **"备份目录为空"**
   - 检查 `MCSM_BASE_PATH` 是否正确
   - 确认服务器文件存在

3. **"权限不足"**
   - 检查目录权限
   - 确认进程用户有访问权限 