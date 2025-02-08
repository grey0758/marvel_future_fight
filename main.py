import base64
import json
import logging
import os
import re
import time
import cv2
import numpy as np
import pymysql
from PIL import Image
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
import pytesseract
from datetime import datetime

pytesseract.pytesseract.tesseract_cmd = r"D:\Program Files\Tesseract-OCR\tesseract.exe"

db_config = {
    'host': '192.168.188.132',
    'user': 'mff_user',
    'password': 'k3#Fv8z&Qh2!',
    'database': 'marvel_future_flight',
}

logger = logging.getLogger(__name__)


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


def get_base64_image(image_path):
    """
    将图像文件转换为base64编码。
    :param image_path: 图像文件的路径。
    :return: base64编码的图像字符串。
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def preprocess_image(cropped_image):
    # 转换为灰度图像
    gray = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)

    # 应用二值化获得二值图像
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 使用形态学操作去除噪声
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return morphed


def preprocess_image_1(image):
    # 转换为灰度图像
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 二值化处理
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 腐蚀操作（去除噪声）
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    eroded = cv2.erode(binary, kernel, iterations=1)

    # 膨胀操作（使字符更分离）
    dilated = cv2.dilate(eroded, kernel, iterations=1)

    # 转换回正常颜色（可选）
    # processed_image = cv2.bitwise_not(dilated)
    cv2.imwrite('processed_image.png', dilated)
    # 使用PIL转换图像
    processed_image_pil = Image.fromarray(dilated)

    return processed_image_pil


def get_game_id_by_devices_udids(udids):
    """通过 devices 和 udids 获取 game_id"""
    # 读取配置文件
    config_path = 'config.json'
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件 {config_path} 未找到")

    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    devices = config.get('devices')
    connection = None
    try:
        connection = pymysql.connect(**db_config)
        with connection.cursor() as cursor:
            sql =  """
            SELECT player_name, game_id
            FROM players
            WHERE JSON_EXTRACT(udids, '$.devices') = %s
              AND JSON_CONTAINS(JSON_EXTRACT(udids, '$.udids'), %s)
            """
            cursor.execute(sql, (json.dumps(devices), json.dumps(udids)))
            result = cursor.fetchone()
            return {
                'player_name': result['player_name'],
                'game_id': result['game_id']
            } if result else None
    except pymysql.MySQLError as e:
        logger.error(f"获取 player_name 和 game_id 时出错: {str(e)}")
    finally:
        if connection:
            connection.close()


class AppManager:
    def __init__(self, appium_server_url, udid):
        self.db_config = {
            'host': '192.168.188.132',
            'user': 'mff_user',
            'password': 'k3#Fv8z&Qh2!',
            'database': 'marvel_future_flight',
        }
        self.player_name = None
        self.popup_thread = None
        self.keep_running = None
        self.appium_server_url = appium_server_url
        self.driver = None
        self.udid = udid
        self.setup_driver(udid)

    def setup_driver(self, udid):
        capabilities = dict(
            platformName="Android",
            platformVersion="9",
            deviceName="Android Emulator",
            automationName="UiAutomator2",
            autoGrantPermissions=True,
            udid=udid,
            noReset=True,
            autoLaunch=False,
            imageMatchThreshold=0.8  # 设置图像相似度阈值为80%
        )
        self.driver = webdriver.Remote(
            self.appium_server_url,
            options=UiAutomator2Options().load_capabilities(capabilities)
        )
        self.driver.update_settings({"imageMatchThreshold": 0.8})

    def activate_app(self, app_package):
        if self.driver:
            self.driver.activate_app(app_package)

    def toggle_clash(self, action, timeout=15):
        """根据参数启动或停止Clash应用"""
        try:
            # 激活Clash应用
            self.activate_app("com.github.metacubex.clash.meta")
            # 将图像文件转换为 base64 编码字符串
            wait = WebDriverWait(self.driver, timeout)
            status_element = wait.until(
                lambda driver: driver.find_element(by=AppiumBy.ID,
                                                   value="com.github.metacubex.clash.meta:id/text_view")
            )
            status_text = status_element.text
            print(status_text)
            print(action)
            if action == "start" and (status_text == "Stopped" or status_text == "已停止"):
                # 如果Clash已经停止，计算元素中心点并点击
                self.tap_element(status_element)
                print("Clash was stopped. Attempting to start...")
            elif action == "stop" and (status_text == "Running" or status_text == "运行中"):
                # 如果Clash正在运行，点击停止按钮
                self.tap_element(status_element)
                print("Clash was running. Attempting0 to stop...")
            else:
                print(f"Clash is already {status_text.lower()}.")
        except Exception as e:
            print(f"Error during {action} Clash: {e}")

    def tap_element(self, element):
        """计算元素中心点并执行点击操作"""
        location = element.location
        size = element.size
        center_x = location['x'] + size['width'] // 2
        center_y = location['y'] + size['height'] // 2
        self.driver.tap([(center_x, center_y)])

    def take_screenshot_cv2(self):
        # 截取屏幕图片并转换为OpenCV格式
        screenshot_base64 = self.driver.get_screenshot_as_base64()
        screenshot_np = np.frombuffer(base64.b64decode(screenshot_base64), np.uint8)
        screenshot = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)
        return screenshot

    def find_and_click_image(self, image_path, click=True, find_multiple=False, click_index=None,
                             image_match_threshold=0.9, timeout=5.0, timeout_position=None, poll_frequency=0.5,
                             x_offset=0, y_offset=0, direct_click_coordinates=False):
        """
        查找图像元素并点击。
        :param poll_frequency:
        :param click: 是否点击找到的元素。
        :param image_path: 要查找的图像文件路径。
        :param find_multiple: 是否查找多个匹配的元素。
        :param click_index: 指定点击哪一个找到的元素的索引。
        :param image_match_threshold: 图像匹配的阈值。
        :param timeout: 等待图像出现的超时时间。
        :param timeout_position: 在超时情况下点击的位置，默认为None。
        :param x_offset: 点击时的x坐标偏移量，仅适用于单个元素。
        :param y_offset: 点击时的y坐标偏移量，仅适用于单个元素。
        :param direct_click_coordinates: 如果为True，直接点击timeout_position提供的坐标。
        :return: 找到的元素或元素列表，或者在超时情况下返回 False。
        """
        if direct_click_coordinates and timeout_position:
            self.driver.tap([timeout_position])
            return True

        self.driver.update_settings({"imageMatchThreshold": image_match_threshold})

        try:
            encoded_string = get_base64_image(image_path)
            wait = WebDriverWait(self.driver, timeout, poll_frequency)

            if find_multiple:
                elements = wait.until(
                    lambda driver: driver.find_elements(AppiumBy.IMAGE, encoded_string)
                )
                if click and click_index is not None and 0 <= click_index < len(elements):
                    elements[click_index].click()
                return elements
            else:
                element = wait.until(
                    lambda driver: driver.find_element(AppiumBy.IMAGE, encoded_string)
                )
                if click:
                    location = element.location
                    size = element.size
                    tap_x = location['x'] + size['width'] // 2 + x_offset
                    tap_y = location['y'] + size['height'] // 2 + y_offset
                    self.driver.tap([(tap_x, tap_y)])
                return element

        except TimeoutException:
            if timeout_position:
                self.driver.tap([timeout_position])
                print("已在超时位置点击")
            else:
                print("未在指定时间内找到图像，且没有指定超时位置")
            return False

    def login(self, is_clash=False, check_clash=True, timeout=10, time_sleep=3):
        if check_clash:
            self.toggle_clash("start")
        self.activate_app("com.netmarble.mherosgb")
        time.sleep(timeout)
        while True:
            if self.find_and_click_image(r'./resource/images/start_war.png', click=False, timeout=3,
                                         image_match_threshold=0.8):
                break
            self.check_obstacle(time_sleep=time_sleep)
        self.check_obstacle()
        if not is_clash:
            self.toggle_clash("stop")
            self.activate_app("com.netmarble.mherosgb")
        return True

    def Shadowland(self, hero=1, first_set=False):

        def check_boos_flight_floor_element():
            try:
                boos_flight_floor_element = self.find_and_click_image(
                    r'resource/images/shadowland/boos_flight_floor.png', image_match_threshold=0.8)
                if not boos_flight_floor_element:
                    self.find_and_click_image(r'resource/images/shadowland/img_7.png', image_match_threshold=0.9,
                                              x_offset=-100)
                    boos_flight_floor_element = self.find_and_click_image(
                        r'resource/images/shadowland/boos_flight_floor.png', image_match_threshold=0.8)

                a, b = boos_flight_floor_element.location['y'], boos_flight_floor_element.location['y'] + \
                                                                boos_flight_floor_element.size['height']
                c, d = boos_flight_floor_element.location['x'] + boos_flight_floor_element.size['width'] * 2, int(
                    boos_flight_floor_element.location['x'] + boos_flight_floor_element.size['width'] * 3)
                image = self.take_screenshot_cv2()
                cropped_image_1 = image[a:b, c:d]
                preprocess_image_1 = preprocess_image(cropped_image_1)
                extracted_text_1 = pytesseract.image_to_string(preprocess_image_1, lang='chi_sim')
                floor = re.findall(r'\d+', extracted_text_1)
                if not floor:
                    floor.append(0)
                if int(floor[0]) in [20, 25, 33]:
                    self.find_and_click_image(r'resource/images/shadowland/refreshstage.png')
                    time.sleep(1)
                    self.find_and_click_image(r'resource/images/shadowland/OK.png')
            except Exception as e:
                print(e)

        def handle_shadowland_stage():
            skip_to_next_cycle = False
            executed = False
            while True:

                if not self.find_and_click_image(r'resource/images/shadowland/entershadowland.png'):
                    self.find_and_click_image(r'resource/images/shadowland/img_5.png')
                check_boos_flight_floor_element()
                self.find_and_click_image(r'resource/images/shadowland/entershadowland2.png')
                if skip_to_next_cycle:
                    self.driver.tap([(1080, 286)])
                    time.sleep(.5)
                    self.driver.tap([(1643, 390)])
                    self.find_and_click_image(r'resource/images/shadowland/start.png')
                    skip_to_next_cycle = False
                else:
                    descending_element = self.find_and_click_image(r'resource/images/shadowland/descending.png',
                                                                   image_match_threshold=0.8,
                                                                   timeout_position=(1850, 280))

                    # if descending_element:
                    #     time.sleep(0.2)
                    #     y_offset = descending_element.size['height'] * 2.5
                    #     x_center = descending_element.location['x'] + descending_element.size['width'] * 0.7
                    #     for x in [x_center, descending_element.location['x'],
                    #               descending_element.location['x'] - descending_element.size['width'] * 0.7]:
                    #         self.driver.tap([(x, descending_element.location['y'] + y_offset)])

                    self.driver.tap([(1643, 390)])
                    time.sleep(0.2)
                    self.driver.tap([(1803, 390)])
                    time.sleep(0.2)
                    self.driver.tap([(1965, 390)])
                self.find_and_click_image(r'resource/images/shadowland/start.png')

                if not executed and self.find_and_click_image(r'resource/images/shadowland/img.png',
                                                              image_match_threshold=0.9, timeout=2):
                    self.find_and_click_image(r'resource/images/shadowland/img_1.png')

                if self.find_and_click_image(r'resource/images/shadowland/end.png', timeout=2):
                    print("通关")
                    break

                if self.find_and_click_image(r'resource/images/shadowland/continue.png', image_match_threshold=0.8,
                                             timeout=180):
                    time.sleep(3)
                else:
                    self.find_and_click_image(r'resource/images/legend_war/img_7.png', image_match_threshold=0.6,
                                              timeout=30)
                    skip_to_next_cycle = True  # Set the flag to skip to the next cycle
                    time.sleep(3)

        def handle_intermediate_stage():
            executed = False
            # executed_1 = False
            while True:
                if not self.find_and_click_image(r'resource/images/shadowland/entershadowland.png',
                                                 image_match_threshold=0.75, timeout=8):
                    self.find_and_click_image(r'resource/images/shadowland/img_4.png', image_match_threshold=0.8,
                                              timeout=3)
                    self.find_and_click_image(r'resource/images/shadowland/img_12.png', timeout=6)

                    return self.Shadowland(first_set=True)
                # if not executed_1:
                #     if not self.find_and_click_image(r'resource/images/shadowland/img_11.png',
                #                                      image_match_threshold=0.95, timeout=5, click=False):
                #         self.find_and_click_image(r'resource/images/shadowland/img_7.png', image_match_threshold=0.9,
                #                                   x_offset=-100)
                #         executed_1 = True
                #     executed_1 = True
                self.find_and_click_image(r'resource/images/shadowland/img_6.png',
                                          image_match_threshold=0.80, y_offset=80, x_offset=100)

                # self.driver.tap([(element.location['x'] + 200, element.location['y'] + 100)])
                self.find_and_click_image(r'resource/images/shadowland/descending.png', click=False)
                if hero == 3:
                    self.driver.tap([(1643, 390)])
                    time.sleep(0.2)
                    self.driver.tap([(1803, 390)])
                    time.sleep(0.2)
                    self.driver.tap([(1965, 390)])
                else:
                    self.driver.tap([(1635, 387)])
                self.find_and_click_image(r'resource/images/shadowland/start.png')

                if not executed and self.find_and_click_image(r'resource/images/shadowland/img.png',
                                                              image_match_threshold=0.9, timeout=2):
                    self.find_and_click_image(r'resource/images/shadowland/img_1.png')
                    executed = True

                self.find_and_click_image(r'resource/images/shadowland/continue.png', image_match_threshold=0.8,
                                          timeout=180)
                time.sleep(3)

        def get_initial_stage():
            time.sleep(2)
            if self.find_and_click_image(r'resource/images/shadowland/entershadowland.png'):
                time.sleep(0.5)
                if self.find_and_click_image(r'resource/images/shadowland/img_9.png', timeout=3, click=False,
                                             image_match_threshold=0.93):
                    if self.find_and_click_image(r'resource/images/shadowland/img_6.png',
                                                 image_match_threshold=0.8, y_offset=80, x_offset=100, click=False):
                        self.driver.press_keycode(4)
                        return 16
                    else:
                        self.find_and_click_image(r'resource/images/shadowland/img_7.png', image_match_threshold=0.85,
                                                  x_offset=-100)
                        time.sleep(0.5)
                        self.driver.press_keycode(4)
                        return 37
                else:
                    if self.find_and_click_image(r'resource/images/shadowland/boos_flight_floor_2.png',
                                                 image_match_threshold=0.6, timeout=3):
                        self.driver.press_keycode(4)
                        return 37
                    else:
                        self.find_and_click_image(r'resource/images/shadowland/img_7.png', image_match_threshold=0.85,
                                                  x_offset=-100)
                        self.driver.press_keycode(4)
                        return 16
            else:
                raise Exception("Unable to enter shadowland")

        def get_initial_stage_2():
            time.sleep(2)
            if self.find_and_click_image(r'resource/images/shadowland/entershadowland.png'):
                time.sleep(2)
                image = self.take_screenshot_cv2()
                # 设置裁剪区域，格式为[y1:y2, x1:x2]
                cropped_image = image[100:157, 935:1294]
                cropped_image = preprocess_image(cropped_image)
                extracted_text = pytesseract.image_to_string(cropped_image, lang='chi_sim').strip()  # 使用中文简体模型
                extracted_text = extracted_text.replace('\n', '').replace('\r', '').replace(' ', '')
                numbers_1 = re.findall(r'\d+', extracted_text)
                if numbers_1:
                    self.driver.press_keycode(4)
                    return numbers_1[0]
                else:
                    self.driver.press_keycode(4)
                    return 36

        if first_set:
            self.change_game_quality()
            self.find_and_click_image(r'resource/images/start_war.png')
            self.driver.tap([(979, 200)])
            time.sleep(0.5)
            self.driver.tap([(1320, 671)])
            self.check_obstacle()
            self.find_and_click_image(r'resource/images/start_war.png')
            self.driver.tap([(979, 200)])
            time.sleep(0.5)
            self.driver.tap([(1320, 671)])

        numbers = [get_initial_stage()]
        print(numbers)
        if int(numbers[0]) > 35:
            handle_shadowland_stage()
        elif 15 < int(numbers[0]) < 36:
            handle_intermediate_stage()

    def Plot(self):
        image = self.take_screenshot_cv2()
        # 设置裁剪区域，格式为[y1:y2, x1:x2]
        cropped_image = image[21:22, 94:150]
        extracted_text = pytesseract.image_to_string(cropped_image, lang='chi_sim')  # 使用中文简体模型

    def daily_work_nox(self, timeout=30):
        def friend():
            self.check_obstacle()
            self.find_and_click_image(r'resource/images/daily_quiz/img.png')
            self.find_and_click_image(r'resource/images/friend/img.png')
            self.find_and_click_image(r'resource/images/friend/img_1.png')
            self.find_and_click_image(r'resource/images/friend/img_2.png', timeout=2)
            if self.find_and_click_image(r'resource/images/friend/img_5.png'):
                self.find_and_click_image(r'resource/images/friend/img_2.png', timeout=2)
            if self.find_and_click_image(r'resource/images/friend/img_3.png'):
                self.find_and_click_image(r'resource/images/friend/img_4.png')
                self.find_and_click_image(r'resource/images/friend/img_5.png')
                self.find_and_click_image(r'resource/images/friend/img_2.png', timeout=2)
                self.find_and_click_image(r'resource/images/friend/img_5.png')
                print("好友已经领取")
            else:
                self.find_and_click_image(r'resource/images/friend/img_6.png', timeout=5)
                print("好友已经领取")

        def union():
            self.check_obstacle()
            self.find_and_click_image(r'resource/images/daily_quiz/img.png')
            self.find_and_click_image(r'resource/images/union/img.png')
            if self.find_and_click_image(r'resource/images/union/img_1.png'):
                self.find_and_click_image(r'resource/images/union/img_2.png')
                print("公会已经领取")

        self.login(is_clash=False, timeout=timeout, time_sleep=15)
        self.change_game_quality()
        self.check_obstacle()
        friend()
        union()
        self.store()
        self.otherworldly_battle()
        if self.udid not in ['emulator-5554', 'emulator-5556']:
            self.TIMELINE_BATTLE()
        self.multiverse_invasion()
        self.check_obstacle()
        self.daily_quiz()

    def store(self):
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/daily_work/store.png', timeout_position=(90, 404),
                                  direct_click_coordinates=True)
        time.sleep(8)
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/daily_work/store.png', timeout_position=(90, 404),
                                  direct_click_coordinates=True)

        if self.find_and_click_image(r'resource/images/normal_store/img_1.png'):
            if self.find_and_click_image(r'resource/images/normal_store/img_3.png',
                                         timeout=3):
                self.driver.press_keycode(4)
            else:
                if self.find_and_click_image(r'resource/images/normal_store/img.png'):
                    self.find_and_click_image(r'resource/images/normal_store/img_2.png',
                                              timeout=20)
                else:
                    print("告诉我商店有新商品")
                    self.driver.press_keycode(4)

        max_attempts = 10
        attempts = 0

        while True:
            self.driver.swipe(267, 755, 269, 346, 0)
            time.sleep(1)
            if self.find_and_click_image(r'resource/images/support_store/img_1.png', timeout=1.5):
                break
            attempts += 1
            if attempts >= max_attempts:
                self.driver.press_keycode(4)  # Press the back button
                attempts = 0  # Reset the attempt counter

        self.find_and_click_image(r'resource/images/support_store/img_2.png', timeout=8, timeout_position=(1200, 190))
        self.find_and_click_image(r'resource/images/support_store/img_3.png', timeout_position=(830, 851))
        # self.find_and_click_image(r'resource/images/support_store/img_5.png', timeout=8, timeout_position=(1400, 675))
        time.sleep(0.5)
        self.driver.tap([(1400, 675)])
        self.find_and_click_image(r'resource/images/support_store/img_6.png', timeout=8, timeout_position=(1458, 862))
        self.find_and_click_image(r'resource/images/support_store/img_8.png', timeout_position=(1200, 850))
        self.find_and_click_image(r'resource/images/support_store/img_4.png', timeout=8, timeout_position=(867, 867))
        # self.find_and_click_image(r'resource/images/support_store/img_5.png', timeout=8, timeout_position=(1400, 675))
        time.sleep(0.5)
        self.driver.tap([(1400, 675)])
        self.find_and_click_image(r'resource/images/support_store/img_6.png', timeout=8, timeout_position=(1458, 862))
        self.find_and_click_image(r'resource/images/support_store/img_8.png', timeout_position=(1200, 850))

    def daily_quiz(self):

        def find_answer(question_text, questions_1):
            for question in questions_1:
                # 如果 question_text 存在于 question['question'] 中，则认为匹配
                if question['question'] in question_text:
                    image_answer = self.take_screenshot_cv2()
                    # 设置裁剪区域，格式为[y1:y2, x1:x2]
                    cropped_image_answer = image_answer[441:929, 1572:2000]
                    cropped_image_answer = preprocess_image_1(cropped_image_answer)
                    custom_config = r'--oem 3 --psm 6'
                    extracted_text_answer = pytesseract.image_to_string(cropped_image_answer, config=custom_config,
                                                                        lang='chi_sim')
                    print(extracted_text_answer)
                    # 使用 split 方法按换行符分割字符串，得到一个列表
                    items = extracted_text_answer.split("\n")
                    # 去除每个 item 中的所有空格，并过滤掉去除空格后为空的 item
                    items = [item.replace(' ', '') for item in items if item.replace(' ', '')]
                    # 打印列表以确认存储的内容
                    print(items)
                    try:
                        matches = [item for item in items if question['answer'] in item]
                        if matches:
                            index = items.index(matches[0])
                            print(f"Match found at index: {index}")
                            tap_answer(index + 1)

                            self.find_and_click_image(r'resource/images/daily_quiz/img_5.png')
                            # time.sleep(0.5)
                            # self.driver.press_keycode(4)
                    except ValueError:
                        print("The answer is not in the list.")
                        return 0
            print("Question not found.")
            return None

        def tap_answer(answer_1):
            if answer_1 == 1:
                self.driver.tap([(1783, 485)])
            elif answer_1 == 2:
                self.driver.tap([(1783, 623)])
            elif answer_1 == 3:
                self.driver.tap([(1783, 762)])
            elif answer_1 == 4:
                self.driver.tap([(1783, 884)])

            self.find_and_click_image(r'resource/images/daily_quiz/img_5.png')

        def open_daily_quiz():
            self.check_obstacle()
            self.change_game_quality()
            self.check_obstacle()
            self.find_and_click_image(r'resource/images/daily_quiz/img.png')
            time.sleep(.5)
            self.find_and_click_image(r'resource/images/daily_quiz/img_1.png', image_match_threshold=0.65, timeout_position=(2207, 559))
            self.find_and_click_image(r'resource/images/daily_quiz/img_2.png', image_match_threshold=0.65, timeout_position=(2207, 559))
            time.sleep(0.5)
            self.driver.tap([(1430, 164)])
            time.sleep(0.5)
            self.driver.tap([(1430, 164)])
            self.find_and_click_image(r'resource/images/daily_quiz/img_3.png')
            self.find_and_click_image(r'resource/images/daily_quiz/img_4.png')

        open_daily_quiz()
        with open('resource/题库.json', mode='r', encoding='utf-8') as file:
            questions = json.load(file)

        # 循环五次
        a = 0
        while a < 7:
            image = self.take_screenshot_cv2()
            # 设置裁剪区域，格式为[y1:y2, x1:x2]
            cropped_image = image[525:710, 447:1344]
            cropped_image = preprocess_image(cropped_image)
            extracted_text = pytesseract.image_to_string(cropped_image, lang='chi_sim').strip()  # 使用中文简体模型
            extracted_text = extracted_text.replace('\n', '').replace('\r', '').replace(' ', '')
            find_answer(extracted_text, questions)
            a += 1
            print(extracted_text)

    def check_obstacle(self, time_sleep=0.5):
        a = True
        while a:
            time.sleep(time_sleep)
            self.driver.press_keycode(4)
            try:
                # 使用 WebDriverWait 来等待图像元素出现
                wait = WebDriverWait(self.driver, 1)

                cancel_element = wait.until(
                    lambda driver: driver.find_element(by=AppiumBy.ID,
                                                       value="android:id/button2")
                )
                if cancel_element:
                    cancel_element.click()
                    a = False
            except TimeoutException:
                pass

    def legend_war(self):
        self.check_obstacle()

        def swipe():
            while True:
                self.driver.swipe(301, 981, 271, 224, 0)
                time.sleep(1)
                if self.find_and_click_image(r'resource/images/legend_war/img_1.png',
                                             timeout=1):
                    if self.find_and_click_image(r'resource/images/legend_war/img_2.png', image_match_threshold=0.8,
                                                 timeout=1):
                        self.find_and_click_image(r'resource/images/legend_war/img_3.png')

                        break

        self.find_and_click_image(r'resource/images/legend_war/stage.png')
        time.sleep(0.2)
        self.find_and_click_image(r'resource/images/legend_war/img.png')
        time.sleep(0.2)
        swipe()
        self.find_and_click_image(r'resource/images/legend_war/img_4.png')
        self.driver.tap([(1500, 834)])
        while True:
            self.find_and_click_image(r'resource/images/legend_war/img_5.png')
            if self.find_and_click_image(r'resource/images/legend_war/img_8.png', timeout=3):
                print('传奇战斗完成')
                break
            self.find_and_click_image(r'resource/images/legend_war/img_6.png', timeout=5)
            while True:
                self.driver.tap([(1926, 805)])
                if self.find_and_click_image(r'resource/images/legend_war/img_7.png',
                                             timeout=1):
                    break

    def multiverse_invasion(self):
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/multiverse_invasion/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_1.png')
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_2.png', timeout_position=(2150, 100))
        time.sleep(5)
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/multiverse_invasion/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_1.png')
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_2.png', timeout_position=(2150, 100))
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_3.png', timeout_position=(1760, 1000))
        self.driver.tap([(1760, 1000)])
        self.find_and_click_image(r'resource/images/multiverse_invasion/img_4.png', timeout_position=(1350, 800))
        while True:
            if self.find_and_click_image(r'resource/images/multiverse_invasion/img_6.png'):
                self.find_and_click_image(r'resource/images/multiverse_invasion/img_7.png',
                                          timeout_position=(1200, 800))
                print('多元入侵完成')
                break
            time.sleep(30)

    def otherworldly_battle(self):
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/otherworldly_battle/img_1.png')
        time.sleep(5)
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/otherworldly_battle/img_1.png')
        self.find_and_click_image(r'resource/images/otherworldly_battle/img_2.png', timeout_position=(1400, 1000))
        if self.find_and_click_image(r'resource/images/otherworldly_battle/img_8.png'):
            print('异世战斗完成')
            self.find_and_click_image(r'resource/images/otherworldly_battle/img_9.png', timeout_position=(1050, 800))
            return
        else:
            self.driver.tap([(1224, 711)])
            time.sleep(0.5)
            self.find_and_click_image(r'resource/images/otherworldly_battle/img_4.png', timeout_position=(1340, 850),
                                      direct_click_coordinates=True)
        while True:
            if self.find_and_click_image(r'resource/images/otherworldly_battle/img_7.png'):
                print('异世战斗完成')
                self.find_and_click_image(r'resource/images/otherworldly_battle/img_6.png',
                                          timeout_position=(1200, 900))
                self.find_and_click_image(r'resource/images/otherworldly_battle/img_10.png',
                                          timeout_position=(1666, 1022))
                self.check_obstacle()
                self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000))
                self.find_and_click_image(r'resource/images/otherworldly_battle/img_1.png')
                self.find_and_click_image(r'resource/images/multiverse_invasion/img_8.png',
                                          timeout_position=(1020, 191))
                self.find_and_click_image(r'resource/images/multiverse_invasion/img_9.png',
                                          timeout_position=(1952, 580))
                self.driver.tap([(1952, 580)])
                time.sleep(.5)
                break
            time.sleep(15)

    def TIMELINE_BATTLE(self):
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_1.png')
        self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_2.png', timeout_position=(1850, 1000))
        time.sleep(8)
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)
        self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_1.png')
        self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_2.png', timeout_position=(1850, 1000))
        self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_3.png', timeout_position=(60, 177))
        # if not self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img.png', imageMatchThreshold=0.8):
        #     self.driver.tap([(1636, 914)])
        if not self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_5.png'):
            if self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_8.png'):
                print('时间线战斗完成')
                return True
        while True:
            if self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_6.png'):
                self.find_and_click_image(r'resource/images/TIMELINE_BATTLE/img_7.png')
                print('时间线战斗完成')
                # 从中间向上滑动
                # self.driver.swipe(1217, 720, 1217, 225, 0)
                break
            time.sleep(30)

    # 修改游戏画质
    def change_game_quality(self):
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/change_game_quality/img.png', timeout_position=(2174, 55))
        # self.find_and_click_image(r'resource/images/change_game_quality/img_1.png', timeout_position=(536, 189),
        # image_match_threshold=0.93) self.find_and_click_image(r'resource/images/change_game_quality/img_2.png',
        # timeout_position=(2206, 56), image_match_threshold=0.93) self.driver.tap([(2260, 1000)])  # 对应于 img.png 的点击
        time.sleep(0.3)
        self.driver.tap([(536, 189)])  # 对应于 img_1.png 的点击
        time.sleep(0.8)
        self.driver.tap([(1197, 418)])  # 对应于 img_2.png 的点击
        time.sleep(0.5)
        self.driver.press_keycode(4)

    def test(self):
        self.find_and_click_image(r'resource/images/otherworldly_battle/img_7.png', timeout_position=(90, 404))

    def Companions_entering_randomly(self, task_name, check_image_frequency=12):
        tasks = {
            'Brothers_in_Danger': {
                'image_path': r'resource/images/Companions_entering_randomly/img_1.png',
                'subtasks': {
                    'subtask_count': 2,
                    'coordinates': [(1533, 547), (929, 572)],
                    'frequency': 3,
                    'check_image_frequency': 12
                }
            },
            'Stupid_X-Men': {
                'image_path': r'resource/images/Companions_entering_randomly/img_6.png',
                'subtasks': {
                    'subtask_count': 2,
                    'coordinates': [(1533, 547), (929, 572)],
                    'frequency': 3,
                    'check_image_frequency': 14
                }
            },
            'Spatiotemporal_splitting': {
                'image_path': r'resource/images/Companions_entering_randomly/img_9.png',
                'subtasks': {
                    'subtask_count': 2,
                    'coordinates': [(1533, 547), (929, 572)],
                    'frequency': 3,
                    'check_image_frequency': 14
                }
            },
            'Twisted_World': {
                'image_path': r'resource/images/Companions_entering_randomly/img_10.png',
                'subtasks': {
                    'subtask_count': 2,
                    'coordinates': [(929, 572), (1533, 547)],
                    'frequency': 3,
                    'check_image_frequency': 14
                }
            },
        }

        def get_image_path(task_name):
            return tasks.get(task_name,
                             {"image_path": None, "subtasks": {"subtask_count": 0, "coordinates": [], "frequency": 1}})

        mission = get_image_path(task_name)
        self.login(is_clash=True, check_clash=False)
        number_of_battles = 0
        number_of_battles_1 = 0
        index = 0
        is_continue = False
        # second_times = False
        # second_times_1 = True
        while number_of_battles < mission['subtasks']['subtask_count'] * mission['subtasks']['frequency']:
            # if second_times and second_times_1:
            #     check_image_frequency = check_image_frequency - 2
            #     second_times_1 = False
            # second_times = True
            if not is_continue:
                self.find_and_click_image(r'resource/images/otherworldly_battle/img.png')
                self.find_and_click_image(mission['image_path'])
                time.sleep(2)
                try:
                    self.driver.tap([mission['subtasks']['coordinates'][index]])
                except IndexError:
                    break

            self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_2.png', timeout=20)

            if self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_4.png', timeout=2):
                self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_5.png',
                                          timeout_position=(1200, 800))
                number_of_battles_1 += 3
                number_of_battles = (number_of_battles // mission['subtasks']['frequency']) * mission['subtasks'][
                    'frequency']
            else:
                print("匹配乱入" + str(check_image_frequency) + "次")
                check_image_frequency_1 = check_image_frequency
                while check_image_frequency_1 < 50 and check_image_frequency_1 != 0:
                    check_image_frequency_1 -= 1
                    if self.find_and_click_image(r'resource/images/Companions_entering_randomly/img.png',
                                                 image_match_threshold=0.45, timeout=0.5, poll_frequency=0.1,
                                                 click=False):
                        check_image_frequency_1 = 100
                if not check_image_frequency_1:
                    self.driver.terminate_app("com.netmarble.mherosgb")
                    self.login(is_clash=True, check_clash=False)
                    is_continue = False
                else:
                    print("乱入成功")
                    self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_3.png', timeout=120)
                    while self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_3.png',
                                                    timeout=2, image_match_threshold=0.8,
                                                    timeout_position=(2233, 1000)):
                        self.find_and_click_image(r'resource/images/Companions_entering_randomly/img_5.png',
                                                  timeout_position=(2233, 1000))
                        pass
                    is_continue = True
                    number_of_battles += 1
                    number_of_battles_1 += 1

            if number_of_battles_1 >= 3:
                number_of_battles_1 = 0
                self.driver.terminate_app("com.netmarble.mherosgb")
                self.login(is_clash=True, check_clash=False)
                is_continue = False
                index += 1

            time.sleep(2)

    def plot(self):
        self.check_obstacle()

    def get_id(self):

        if self.player_name:
            return self.player_name

        json_1 = get_game_id_by_devices_udids(self.udid)
        if json_1:
            self.player_name = json_1['player_name']
            return json_1['player_name']
        else:
            self.player_name = 'default_player'
            return 'default_player'



        # self.check_obstacle()
        # self.find_and_click_image(r'resource/images/change_game_quality/img.png', timeout_position=(2174, 55),
        #                           direct_click_coordinates=True)
        # time.sleep(1)
        # self.find_and_click_image(r'resource/images/get_id/img.png', timeout_position=(1555, 382),
        #                           direct_click_coordinates=True)

        # 获取剪贴板内容
        # clipboard_text = self.driver.get_clipboard_text()
        # # print("Clipboard content:", clipboard_text)
        # if clipboard_text:
        #     self.player_name = clipboard_text
        #     return clipboard_text
        # else:
        #     self.player_name = 'default_player'
        #     return 'default_player'

    def daily_work_2(self):
        self.login(is_clash=False, timeout=30, time_sleep=15)
        self.check_obstacle()
        self.get_id()
        self.check_obstacle()
        self.find_and_click_image(r'resource/images/otherworldly_battle/img.png', timeout_position=(1850, 1000),
                                  direct_click_coordinates=False)

        if self.find_and_click_image(r'resource/images/daily_work_2/img.png'):
            time.sleep(1)
            self.driver.tap([(929, 572)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('hidden_secret_left')
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)

            self.driver.tap([(1533, 547)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('hidden_secret_right')
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)

        if self.find_and_click_image(r'resource/images/daily_work_2/img_1.png'):
            time.sleep(1)
            self.driver.tap([(929, 572)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('healthy_twins_left')
            time.sleep(1)
            self.driver.press_keycode(4)

            self.driver.tap([(1533, 547)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('healthy_twins_right')
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)

        if self.find_and_click_image(r'resource/images/daily_work_2/img_2.png'):
            time.sleep(1)
            self.driver.tap([(929, 572)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('unfortunate_fate_left')
            time.sleep(1)
            self.driver.press_keycode(4)

            self.driver.tap([(1533, 547)])
            time.sleep(1)
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('unfortunate_fate_right')
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)
            self.driver.press_keycode(4)
            time.sleep(1)

        if self.find_and_click_image(r'resource/images/daily_work_2/img_6.png'):
            self.find_and_click_image(r'resource/images/daily_work_2/img_7.png', timeout_position=(1067, 1023))
            self.find_and_click_image(r'resource/images/daily_work_2/img_3.png', timeout_position=(1067, 1023))
            if not self.find_and_click_image(r'resource/images/daily_work_2/img_5.png', click=False):
                self.find_and_click_image(r'resource/images/daily_work_2/img_4.png', timeout_position=(1200, 828))
            time.sleep(1)
            self.driver.press_keycode(4)
            self.update_task_status('united_fate_normal')
            time.sleep(1)
            self.driver.press_keycode(4)

    def update_task_status(self, task_name):
        """更新任务状态"""
        connection = None
        try:
            connection = pymysql.connect(**self.db_config)
            with connection.cursor() as cursor:
                # 获取今天的日期
                today = datetime.now().date()

                # 获取 game_id
                game_id = self.get_id()

                # 确保任务表中有玩家的记录
                sql = f"""
                INSERT INTO tasks (game_id, date)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE {task_name} = TRUE;
                """
                cursor.execute(sql, (game_id, today))
            connection.commit()

            # 记录任务完成日志
            timestamp = datetime.now()
            save_log_to_mysql(timestamp, 'Success', f"任务 {task_name} 已完成 for game_id {game_id}")
        except pymysql.MySQLError as e:
            logger.error(f"更新任务状态时出错: {str(e)}")
            timestamp = datetime.now()
            save_log_to_mysql(timestamp, 'Error', f"更新任务状态时出错: {str(e)}")
        finally:
            if connection:
                connection.close()


if __name__ == "__main__":
    appium_url = 'http://localhost:4723'

    # app_manager = AppManager(appium_url, 'emulator-5560')
    app_manager = AppManager(appium_url, '192.168.31.190:5559')
    # app_manager.store()
    # app_manager.Companions_entering_randomly('Brothers_in_Danger')
    # app_manager.daily_work_nox()
    # app_manager.legend_war()
    # app_manager.legend_war()
    app_manager.daily_work_2()
    # app_manager.daily_quiz()
    # app_manager.multiverse_invasion()
