from main import AppManager
import threading
from daily_work_nox import get_adb_devices


def run_app_manager(appium_url, emulator_name):
    app_manager = AppManager(appium_url, emulator_name)
    app_manager.login(is_clash=True)


if __name__ == "__main__":
    appium_url = 'http://localhost:4723'
    # emulators = ['127.0.0.1:62025', '127.0.0.1:62001']
    # emulators = ['127.0.0.1:62025']
    emulators = get_adb_devices()
    print(f"emulators = {emulators}")

    threads = []
    for emulator in emulators:
        thread = threading.Thread(target=run_app_manager, args=(appium_url, emulator))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()
