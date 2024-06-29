import os

import redis
import json
import pymysql
from datetime import datetime
from loguru import logger
import time
import asyncio
import cv2
import numpy as np
import pyautogui
from pywinauto import Application, Desktop
import ctypes
import psutil
import subprocess

import daily_work_nox

# 读取配置文件
config_path = 'config.json'
if not os.path.exists(config_path):
    raise FileNotFoundError(f"配置文件 {config_path} 未找到")

with open(config_path, 'r') as config_file:
    config = json.load(config_file)

# 获取 LDPlayer 路径
ldplayer_path = config.get('ldplayer_path')
if not ldplayer_path:
    raise ValueError("配置文件中缺少 'ldplayer_path' 项")

# 配置日志
logger.add("game_task.log", rotation="1 day")

# 配置Redis连接
redis_client = redis.StrictRedis(
    host='121.37.30.225',
    port=6379,
    password='ya6MCCTXsnPfYJg',
    decode_responses=True,
    socket_timeout=10  # 增加超时时间，单位是秒
)

# 配置MySQL连接
db_config = {
    'host': '121.37.30.225',
    'user': 'mff_user',
    'password': 'k3#Fv8z&Qh2!',
    'database': 'marvel_future_flight',
}


def save_log_to_mysql(timestamp, status, message):
    """保存日志到MySQL数据库"""
    connection = None
    try:
        connection = pymysql.connect(**db_config)
        with connection.cursor() as cursor:
            sql = "INSERT INTO logs (timestamp, status, message) VALUES (%s, %s, %s)"
            cursor.execute(sql, (timestamp, status, message))
        connection.commit()
    except pymysql.MySQLError as e:
        logger.error(f"保存日志到MySQL数据库时出错: {str(e)}")
    finally:
        if connection:
            connection.close()


def log_game_task_status(status, message):
    """记录游戏任务状态"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_log_to_mysql(timestamp, status, message)
    log_entry = {
        "timestamp": timestamp,
        "status": status,
        "message": message
    }
    logger.info(json.dumps(log_entry))


def close_window(hwnd):
    # 发送WM_CLOSE消息到窗口
    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)


def close_ldplayer_process():
    # 查找并关闭名为 "dnmultiplayerex.exe" 的进程
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'dnmultiplayerex.exe':
            logger.info(f"Terminating process {proc.info['name']} with PID {proc.info['pid']}")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.NoSuchProcess:
                pass


def close_ldplayer_windows():
    # 获取桌面上所有窗口
    windows = Desktop(backend="uia").windows()
    for window in windows:
        # 检查窗口的类名是否为"LDPlayerMainFrame"
        if window.class_name() == "LDPlayerMainFrame":
            logger.info(f"Closing window: {window.window_text()}")
            hwnd = window.handle
            close_window(hwnd)
            time.sleep(1)  # 等待1秒，确保窗口有时间响应关闭消息


def start_and_focus_app():
    # 关闭所有LDPlayer窗口和相关进程
    close_ldplayer_windows()
    close_ldplayer_process()

    # 启动模拟器管理器应用程序
    app = Application().start(ldplayer_path)

    # 等待应用程序启动
    time.sleep(5)

    # 获取模拟器管理器窗口
    dlg = Desktop(backend="uia").window(class_name="LDRemoteLoginFrame", title="雷電多開器")

    # 确保窗口已存在并可见
    dlg.wait('visible', timeout=10)
    return app, dlg


def find_and_click_image(template_path, threshold=0.8, offset_x=0, offset_y=0):
    # 读取模板图像
    template = cv2.imread(template_path, 0)
    w, h = template.shape[::-1]

    # 截取屏幕图像
    screenshot = pyautogui.screenshot()
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    # 在屏幕图像中查找模板图像
    res = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)

    # 获取目标图像的位置并进行单击操作
    for pt in zip(*loc[::-1]):
        # 调整点击位置
        click_x = pt[0] + w / 2 + offset_x
        click_y = pt[1] + h / 2 + offset_y
        pyautogui.click(click_x, click_y)
        return True
    return False


def get_adb_devices():
    """获取当前连接的ADB设备列表"""
    result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout.strip().split('\n')
    excluded_device = '192.168.31.190:5559'
    emulators = [line.split('\t')[0] for line in output[1:] if
                 'device' in line and line.split('\t')[0] != excluded_device]
    return emulators


async def monitor_emulator_start(initial_emulators, timeout=300, interval=10):
    """监控是否有新模拟器启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_emulators = get_adb_devices()
        if len(current_emulators) > len(initial_emulators):
            logger.info("模拟器启动成功")
            return True
        await asyncio.sleep(interval)
    logger.error("未能在规定时间内检测到新模拟器启动")
    return False


async def open_game_accounts(account_names):
    """打开多个游戏账号并监控模拟器启动"""
    image_paths = {
        '大号': 'resource/images/start_nox/img.png',
        '蛋挞菩提': 'resource/images/start_nox/img_1.png',
        '小号': 'resource/images/start_nox/img_2.png',
        '鼠': 'resource/images/start_nox/img_3.png',
    }

    invalid_accounts = [name for name in account_names if name not in image_paths]
    if invalid_accounts:
        for account in invalid_accounts:
            logger.error(f"无效的账号名称: {account}")
            log_game_task_status('ERROR', f"无效的账号名称: {account}")
        return

    app, dlg = start_and_focus_app()

    time.sleep(2)

    initial_emulators = get_adb_devices()
    logger.info(f"初始模拟器数量: {len(initial_emulators)}")

    app = Application().connect(process=app.process)
    ldremote_login_frame = app.window(handle=dlg.handle)
    ldremote_login_frame.set_focus()

    for account_name in account_names:
        if find_and_click_image(image_paths[account_name], offset_x=520):
            logger.info(f"成功打开游戏账号: {account_name}")
            log_game_task_status('INFO', f"成功打开游戏账号: {account_name}")
        else:
            logger.error(f"未能找到并点击图像: {account_name}")
            log_game_task_status('ERROR', f"未能找到并点击图像: {account_name}")
            return

    success = await monitor_emulator_start(initial_emulators)
    if success:
        log_game_task_status('INFO', f"模拟器启动成功: {', '.join(account_names)}")
    else:
        log_game_task_status('ERROR', f"模拟器启动失败: {', '.join(account_names)}")


def complete_daily_task(task):
    """执行每日任务"""
    try:
        daily_work_nox.main()
        log_game_task_status("SUCCESS", "每日任务成功执行")
    except Exception as e:
        log_game_task_status("ERROR", f"每日任务执行失败: {str(e)}")



def complete_weekly_task(task):
    """执行每周任务"""
    try:
        log_game_task_status("INFO", f"开始执行每周任务: {task['description']}")
        # 这里添加完成每周任务的代码
        log_game_task_status("SUCCESS", f"每周任务完成: {task['description']}")
    except Exception as e:
        log_game_task_status("ERROR", f"执行每周任务时出错: {str(e)}")


def complete_game_task(task):
    """根据任务类型执行游戏任务"""
    task_type = task.get('task_type')
    if task_type == 'daily_task':
        complete_daily_task(task)
    elif task_type == 'weekly_task':
        complete_weekly_task(task)
    elif task_type == 'open_game':
        account_names = task.get('account_names', [])
        if account_names:
            asyncio.run(open_game_accounts(account_names))  # 使用 asyncio.run 来运行异步函数
        else:
            log_game_task_status("ERROR", "任务中缺少 'account_names'")
    else:
        log_game_task_status("ERROR", f"未知任务类型: {task_type}")


def consume_task():
    """从Redis队列中提取任务并执行"""
    while True:
        try:
            task_data = redis_client.rpop("game_tasks")
            if task_data:
                task = json.loads(task_data)
                complete_game_task(task)
            else:
                # 队列为空时休眠一段时间
                time.sleep(5)
        except Exception as e:
            log_game_task_status("ERROR", f"提取任务时出错: {str(e)}")


if __name__ == "__main__":
    consume_task()
