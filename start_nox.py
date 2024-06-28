import time
import cv2
import numpy as np
import pyautogui
from pywinauto import Application, Desktop

def start_and_focus_app():
    # 启动模拟器管理器应用程序
    app = Application().start("D:\LDPlayer\ldmutiplayer\dnmultiplayerex.exe")

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

def main(image_id):
    image_paths = {
        '1': 'resource/images/start_nox/img.png',
        '2': 'resource/images/start_nox/img2.png',
        '3': 'resource/images/start_nox/img3.png',
        # 添加更多路径根据需要
    }

    if image_id not in image_paths:
        print("Invalid image_id")
        return

    # 启动并获取应用程序窗口
    app, dlg = start_and_focus_app()

    # 连接到目标应用程序
    app = Application().connect(process=app.process)  # 使用进程ID连接
    ldremote_login_frame = app.window(handle=dlg.handle)  # 使用窗口句柄连接

    # 将窗口置于前台
    ldremote_login_frame.set_focus()

    # 查找并点击图像，右边偏移520像素
    if find_and_click_image(image_paths[image_id], offset_x=520):
        print("图像已找到并点击")
    else:
        print("图像未找到")

# 运行主函数，并传入图像ID
main('1')
