# MCSM Git 备份功能配置说明

## 环境变量配置

在 `.env` 文件中添加以下配置项来启用 Git 备份功能：

### 基础配置

```bash
# 启用 Git 备份功能
GIT_BACKUP_ENABLED=true

# 最大备份数量（超过此数量会自动合并旧备份）
GIT_BACKUP_MAX_COUNT=10

# Git 提交者信息
GIT_BACKUP_USER_NAME=MCSM Bot
GIT_BACKUP_USER_EMAIL=bot@mcsm.local
```

### 备份路径配置

#### 方式1：服务器特定路径
```bash
# 格式：服务器名:路径，多个用逗号分隔
GIT_BACKUP_PATHS=slimefun:D:/MinecraftServers/slimefun,creative:D:/MinecraftServers/creative
```

#### 方式2：基础路径（自动为每个服务器创建子目录）
```bash
# 基础路径，系统会自动为每个服务器创建 {base_path}/{server_name} 目录
GIT_BACKUP_PATHS=D:/MinecraftServers
```

## 使用方法

### 基本备份
```
/server_backup <服务器名>
```

### 带描述的备份
```
/server_backup <服务器名> 更新插件配置
```

## 备份流程

1. **保存世界数据**：向服务器发送 `save-all` 指令
2. **Git 初始化**：如果目录没有 Git 仓库，自动初始化
3. **创建提交**：将所有变更提交到 Git 仓库
4. **管理历史**：当备份数量超过 `GIT_BACKUP_MAX_COUNT` 时，自动合并旧提交

## 注意事项

1. **权限要求**：使用此命令需要 `mc_server` 特殊权限
2. **路径格式**：Windows 环境下使用正斜杠 `/` 或反斜杠 `\\`
3. **空间管理**：定期检查备份目录大小，Git 会保留所有历史版本
4. **网络备份**：建议将备份目录同步到远程 Git 仓库以确保安全

## 错误排查

### 常见错误

1. **"备份路径不存在"**
   - 检查 `GIT_BACKUP_PATHS` 配置是否正确
   - 确保路径存在且可访问

2. **"Git 操作失败"**
   - 确保系统已安装 Git
   - 检查路径权限

3. **"发送存档保存指令失败"**
   - 检查服务器是否在运行
   - 验证 MCSM 连接配置

## 配置示例

### 完整配置示例
```bash
# MCSM 基础配置
MCSM_URL=http://localhost:23333
MCSM_APIKEY=your_api_key_here
MCSM_DAEMON_ID=your_daemon_id_here
MCSM_SLIMEFUN_ID=your_instance_id_here

# Git 备份配置
GIT_BACKUP_ENABLED=true
GIT_BACKUP_MAX_COUNT=15
GIT_BACKUP_USER_NAME=服务器管理员
GIT_BACKUP_USER_EMAIL=admin@yourserver.com
GIT_BACKUP_PATHS=slimefun:D:/Servers/SlimeFun,survival:D:/Servers/Survival
``` 