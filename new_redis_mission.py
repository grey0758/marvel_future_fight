import redis
import json
from datetime import datetime

# 配置Redis连接
REDIS_HOST = '121.37.30.225'
REDIS_PORT = 6379
REDIS_PASSWORD = 'ya6MCCTXsnPfYJg'

redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)

def add_task_to_queue(task):
    """将任务添加到Redis队列"""
    task_data = json.dumps(task)
    redis_client.lpush("game_tasks", task_data)

# 示例任务
task1 = {
    "task_id": 1,
    "task_type": "daily_task",
    "description": "Complete daily game task",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

task2 = {
    "task_id": 2,
    "task_type": "weekly_task",
    "description": "Complete weekly game task",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

task3 = {
    "task_id": 3,
    "task_type": "open_game",
    "account_name": "蛋挞菩提",
    "description": "Open game account 蛋挞菩提",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# add_task_to_queue(task1)
# add_task_to_queue(task2)
add_task_to_queue(task3)

print("任务已添加到队列")
