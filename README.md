# Marvel Future Fight 自动化任务管理工具

该项目是一个基于Appium的自动化脚本，用于游戏《Marvel Future Fight》的任务管理和操作自动化。它能够模拟玩家在游戏中的各种操作，例如自动战斗、任务完成、角色操作等。通过图像识别技术，脚本自动执行重复性任务，提高玩家的游戏效率，节省时间。

## 主要功能

- **自动战斗与任务完成**：通过图像识别自动完成游戏中的各类战斗和任务。
- **任务频率管理**：根据任务要求，自动调整任务执行频率，确保每个任务按时完成。
- **障碍检测与处理**：自动检测并处理游戏中的障碍，避免中途卡住。
- **与数据库交互**：与MySQL数据库交互，更新任务进度，记录任务完成状态。
- **图像识别和点击操作**：利用Appium进行精准的UI元素识别和点击操作，自动化任务执行。
- **自动登录与恢复**：支持自动重新登录游戏，确保任务不中断，自动恢复执行。

## 项目结构

- `app_manager.py`：包含自动化脚本的主要逻辑，包括任务自动执行、战斗和登录流程。
- `db_config.py`：数据库连接配置文件，管理与MySQL的连接。
- `resource/`：存储游戏UI截图和资源文件的目录，供脚本进行图像匹配。
- `logs/`：日志目录，用于存储执行过程中的详细信息与错误日志。

## 安装与运行

### 环境要求

- Python 3.7+
- Appium 2.x（用于自动化测试）
- MySQL 5.x+（用于记录任务状态）
- `pymysql`（用于数据库操作）
- `selenium`（用于Appium接口交互）

### 安装依赖

首先，安装项目所需的Python依赖：

```bash
pip install -r requirements.txt
```
配置Appium与游戏环境
安装并启动Appium服务：确保Appium能够连接到你的模拟器或真实设备。你可以参考Appium官方文档来设置环境。
配置游戏的相关参数：确保《Marvel Future Fight》的安装在你的设备上，并配置正确的设备UDID（唯一设备标识符）和游戏版本。
MySQL配置：确保已安装MySQL并创建用于记录任务状态的数据库和表。
启动脚本
启动脚本以开始自动化任务执行：

## 配置Appium与游戏环境

### 安装并启动Appium服务

1. 确保Appium能够连接到你的模拟器或真实设备。你可以参考[Appium官方文档](http://appium.io/docs/en/about-appium/intro/)来设置环境。
   
2. 安装Appium：
   ```bash
   npm install -g appium
   ```
3.启动Appium服务：
   ```bash
  appium
  ```
### 配置游戏的相关参数
1.确保《Marvel Future Fight》已安装在你的设备上。
2.配置正确的设备 UDID（唯一设备标识符）。你可以通过以下命令来查看设备的 UDID：

```bash
adb devices
```
### 启动脚本
```bash
python app_manager.py
```  
脚本会自动登录《Marvel Future Fight》，并开始执行配置好的任务。
