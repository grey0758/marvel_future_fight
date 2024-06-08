from main import AppManager
import threading
from daily_work_nox import get_adb_devices


def run_app_manager(appium_url_1, emulator_name):
    app_manager = AppManager(appium_url_1, emulator_name)
    app_manager.daily_work_nox()


if __name__ == "__main__":
    appium_url = 'http://localhost:4723'
    emulators = ['127.0.0.1:62025', '127.0.0.1:62026']
    # emulators = ['127.0.0.1:62025']

    threads = []
    for emulator in emulators:
        thread = threading.Thread(target=run_app_manager, args=(appium_url, emulator))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()
