import os

import cv2
import numpy as np

# 加载图像和模板
main_image_path = r'garbage/20240514225053.png'
template_image_path = r'garbage/20240514225123.png'

# 检查图片文件是否存在
if not os.path.exists(main_image_path) or not os.path.exists(template_image_path):
    print("One or both image files do not exist.")
else:
    # 加载图像和模板
    main_image = cv2.imread(main_image_path)
    template_image = cv2.imread(template_image_path)
    h, w = template_image.shape[:2]

    # 进行模板匹配
    res = cv2.matchTemplate(main_image, template_image, cv2.TM_CCOEFF_NORMED)

    # 设定阈值
    threshold = 0.5
    loc = np.where(res >= threshold)

    # 标记匹配区域
    for pt in zip(*loc[::-1]):  # Switch collumns and rows
        cv2.rectangle(main_image, pt, (pt[0] + w, pt[1] + h), (0, 255, 0), 2)

    # 显示结果
    cv2.imshow('Detected', main_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
