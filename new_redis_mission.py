import redis
import json
from datetime import datetime

# 配置Redis连接
REDIS_HOST = '121.37.30.225'
REDIS_PORT = 6379
REDIS_PASSWORD = 'ya6MCCTXsnPfYJg'

# 创建Redis客户端
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)


def add_task_to_queue(task):
    """将任务添加到Redis队列"""
    try:
        task_data = json.dumps(task)  # 将任务转换为JSON字符串
        redis_client.lpush("game_tasks", task_data)  # 将任务添加到Redis队列
        print(f"任务 {task['task_id']} 已添加到队列")
    except Exception as e:
        print(f"添加任务失败: {str(e)}")


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

combined_task = {
    "task_id": 3,
    "task_type": "open_game",
    "account_names": ["蛋挞菩提", "大号"],
    "description": "Open game accounts 蛋挞菩提 and 大号",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# 添加任务到队列
# add_task_to_queue(task1)
# add_task_to_queue(task2)
add_task_to_queue(combined_task)
