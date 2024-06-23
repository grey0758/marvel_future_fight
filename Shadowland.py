from main import AppManager
import threading
import subprocess


def run_app_manager(appium_url_1, emulator_name):
    app_manager = AppManager(appium_url_1, emulator_name)
    app_manager.Shadowland()


def get_adb_devices():
    # 运行 adb devices 命令并获取输出
    result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 分析命令输出
    output = result.stdout.strip().split('\n')

    # 要排除的设备
    excluded_device = '192.168.31.190:5559'

    # 提取设备信息并过滤排除设备
    emulators = []
    for line in output[1:]:  # 跳过第一行 "List of devices attached"
        if 'device' in line:
            device_info = line.split('\t')[0]
            if device_info != excluded_device:
                emulators.append(device_info)

    return emulators


if __name__ == "__main__":

    # 获取设备列表并打印
    emulators = get_adb_devices()
    print(f"emulators = {emulators}")

    appium_url = 'http://localhost:4723'
    # emulators = ['127.0.0.1:62026', '127.0.0.1:62025']
    # emulators = ['127.0.0.1:62026']

    threads = []
    for emulator in emulators:
        thread = threading.Thread(target=run_app_manager, args=(appium_url, emulator))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()