import redis
import json
import pymysql
from datetime import datetime
from loguru import logger
import time

# 配置日志
logger.add("game_task.log", rotation="1 day")

# 配置Redis连接
REDIS_HOST = '121.37.30.225'
REDIS_PORT = 6379
REDIS_PASSWORD = 'ya6MCCTXsnPfYJg'

redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)

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


def complete_daily_task(task):
    """执行每日任务"""
    try:
        log_game_task_status("INFO", f"开始执行每日任务: {task['description']}")
        # 这里添加完成每日任务的代码
        log_game_task_status("SUCCESS", f"每日任务完成: {task['description']}")
    except Exception as e:
        log_game_task_status("ERROR", f"执行每日任务时出错: {str(e)}")


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
