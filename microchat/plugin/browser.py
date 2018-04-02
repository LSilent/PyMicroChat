import sys
import threading
import time
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import *

# 浏览器主窗口
class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("mm security_center")
        self.resize(600, 400)
        self.show()
        self.browser = QWebEngineView()
        self.url = sys.argv[1]                                                                  #浏览器url通过命令行第2个参数传递
        self.browser.load(QUrl(self.url))
        self.setCentralWidget(self.browser)
        
        # 通过监测浏览器地址判断登录授权结果
        self.timer = threading.Timer(0.1, self.check_url)
        self.start = True                                                                       # 开始监测url
        self.timer.start()                                                                      # 启动定时器
        return
        
    # 监测url,判断网页授权是否结束
    def check_url(self):
        if self.start: 
            if self.url == self.browser.url().toString():                                       # 授权页面url未改变                                        
                pass                                                                            # 继续等待用户操作
            else:
                if self.browser.url().toString().find('t=login_verify_entrances/w_tcaptcha_ret') > 0: # 滑块验证通过,关闭浏览器
                    self.start = False
                    self.close()
                    return
                elif self.browser.url().toString().find('login_verify_entrances/result') > 0:   # 授权结果
                    time.sleep(2)                                                               # 显示结果2秒后关闭浏览器
                    self.close()
                    return
                else:                                                                           # 继续等待用户操作
                    pass
            self.timer = threading.Timer(0.1, self.check_url)        
            self.timer.start()                                                                  # 重启定时器
        else:
            #点X关闭了浏览器
            self.close()
        
 
if __name__=='__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()
    window.start = False
    window.close()
    sys.exit()