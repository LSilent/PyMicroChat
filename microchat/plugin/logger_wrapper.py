import logging
import sys
import os
import time
import ctypes, sys
import threading
import enum
from .color_console import ColorConsole

__all__ = ['logger']

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12


class ColorDefine(enum.IntEnum):

    # 字体颜色定义 ,关键在于颜色编码，由2位十六进制组成，分别取0~f，前一位指的是背景色，后一位指的是字体色
    #由于该函数的限制，应该是只有这16种，可以前景色与背景色组合。也可以几种颜色通过或运算组合，组合后还是在这16种颜色中

    # Windows CMD命令行 字体颜色定义 text colors
    FOREGROUND_BLACK = 0x00  # black.
    FOREGROUND_DARKBLUE = 0x01  # dark blue.
    FOREGROUND_DARKGREEN = 0x02  # dark green.
    FOREGROUND_DARKSKYBLUE = 0x03  # dark skyblue.
    FOREGROUND_DARKRED = 0x04  # dark red.
    FOREGROUND_DARKPINK = 0x05  # dark pink.
    FOREGROUND_DARKYELLOW = 0x06  # dark yellow.
    FOREGROUND_DARKWHITE = 0x07  # dark white.
    FOREGROUND_DARKGRAY = 0x08  # dark gray.
    FOREGROUND_BLUE = 0x09  # blue.
    FOREGROUND_GREEN = 0x0a  # green.
    FOREGROUND_SKYBLUE = 0x0b  # skyblue.
    FOREGROUND_RED = 0x0c  # red.
    FOREGROUND_PINK = 0x0d  # pink.
    FOREGROUND_YELLOW = 0x0e  # yellow.
    FOREGROUND_WHITE = 0x0f  # white.
    FOREGROUND_PURPLE = FOREGROUND_RED | FOREGROUND_BLUE

    # Windows CMD命令行 背景颜色定义 background colors
    BACKGROUND_DARKBLUE = 0x10  # dark blue.
    BACKGROUND_DARKGREEN = 0x20  # dark green.
    BACKGROUND_DARKSKYBLUE = 0x30  # dark skyblue.
    BACKGROUND_DARKRED = 0x40  # dark red.
    BACKGROUND_DARKPINK = 0x50  # dark pink.
    BACKGROUND_DARKYELLOW = 0x60  # dark yellow.
    BACKGROUND_DARKWHITE = 0x70  # dark white.
    BACKGROUND_DARKGRAY = 0x80  # dark gray.
    BACKGROUND_BLUE = 0x90  # blue.
    BACKGROUND_GREEN = 0xa0  # green.
    BACKGROUND_SKYBLUE = 0xb0  # skyblue.
    BACKGROUND_RED = 0xc0  # red.
    BACKGROUND_PINK = 0xd0  # pink.
    BACKGROUND_YELLOW = 0xe0  # yellow.
    BACKGROUND_WHITE = 0xf0  # white.


std_out_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)


def set_cmd_text_color(color, handle=std_out_handle):
    Bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)
    return Bool


def reset_color():
    # set_cmd_text_color(FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE) #reset white
    set_cmd_text_color(ColorDefine.FOREGROUND_GREEN)  #reset green


def __singletion(cls):
    """
    单例模式的装饰器函数
    :param cls: 实体类
    :return: 返回实体类对象
    """
    instances = {}

    def getInstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return getInstance


# @__singletion
class LoggerWrapper(object):
    def __init__(self):
        """
        单例初始化
        :param out: 设置输出端：0：默认控制台
        :return: 返回日志对象
        """
        self.out = 0
        if os.path.exists(os.getcwd() + '/log') is False:
            os.mkdir(os.getcwd() + '/log')

    def config(self, appName, logFileName=None, level=logging.INFO, out=2, fore_color = ColorDefine.FOREGROUND_GREEN):
        """
        获取日志处理对象
        :param appName: 应用程序名
        :param logFileName: 日志文件名
        :param out: 设置输出端：0：默认控制台，1：输入文件，其他：logger指定的控制台和文件都输出
        :           2: 定制的控制台输出和文件输出
        :return: 返回日志对象
        """
        self.appName = appName
        if logFileName is None:
            self.logFileName = os.getcwd() + '/log/' + time.strftime(
                "%Y-%m-%d", time.localtime()) + ".log"
        self.log_level = level
        self.out = out
        self.fore_color = fore_color
        self.logger_file, self.logger_console = self.getLogger()

    def getLogger(self):
        # 获取logging实例
        logger_file = logging.getLogger(self.appName)
        logger_console = logging.getLogger('streamer')
        # 指定输出的格式
        formatter = logging.Formatter(
            '%(name)s %(asctime)s %(levelname)8s: %(message)s')

        # 文件日志
        file_handler = logging.FileHandler(self.logFileName, encoding='utf-8')
        file_handler.setFormatter(formatter)

        # 控制台日志
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # # 指定日志的最低输出级别
        logger_file.setLevel(self.log_level)         # 20 INFO
        logger_console.setLevel(self.log_level)  # 20
        # 为logger添加具体的日志处理器输出端
        if self.out == 1:
            logger_file.addHandler(file_handler)
        elif self.out == 0:
            logger_console.addHandler(console_handler)
        else:
            logger_file.addHandler(file_handler)
            logger_console.addHandler(console_handler)
        
        logger_file.propagate = False
        logger_console.propagate = False

        return logger_file, logger_console

    def setLevel(self, level):
        if self.out == 1:
            self.log_level = self.logger_file.setLevel(level)
        elif self.out == 0:
            self.log_level = self.logger_console.setLevel(level)
        else:
            self.log_level = self.logger_file.setLevel(level)
            self.log_level = self.logger_console.setLevel(level)

    def debug(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(ColorDefine.FOREGROUND_WHITE)
        else:
            set_cmd_text_color(color)

        if self.out == 1:
            self.logger_file.debug(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.debug(msg1, *args, **kwargs)
        else:
            self.logger_file.debug(msg, *args, **kwargs)
            self.logger_console.debug(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

    def info(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(self.fore_color)
        else:
            set_cmd_text_color(color)
            
        if self.out == 1:
            self.logger_file.info(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.info(msg1, *args, **kwargs)
        else:
            self.logger_file.info(msg, *args, **kwargs)
            self.logger_console.info(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

    def warning(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(ColorDefine.FOREGROUND_YELLOW)
        else:
            set_cmd_text_color(color)

        if self.out == 1:
            self.logger_file.warning(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.warning(msg1, *args, **kwargs)
        else:
            self.logger_file.warning(msg, *args, **kwargs)
            self.logger_console.warning(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

    def warn(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(ColorDefine.FOREGROUND_DARKYELLOW)
        else:
            set_cmd_text_color(color)

        if self.out == 1:
            self.logger_file.warn(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.warn(msg1, *args, **kwargs)
        else:
            self.logger_file.warn(msg, *args, **kwargs)
            self.logger_console.warn(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

    def error(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(ColorDefine.FOREGROUND_RED)
        else:
            set_cmd_text_color(color)

        if self.out == 1:
            self.logger_file.error(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.error(msg1, *args, **kwargs)
        else:
            self.logger_file.error(msg, *args, **kwargs)
            self.logger_console.error(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

    def critical(self, msg, color=None, *args, **kwargs):
        try:
            msg1 = msg.encode('gbk', 'ignore').decode('gbk', 'ignore')
        except:
            msg1 = ''

        if color is None:
            set_cmd_text_color(ColorDefine.FOREGROUND_DARKPINK)
        else:
            set_cmd_text_color(color)

        if self.out == 1:
            self.logger_file.critical(msg, *args, **kwargs)
        elif self.out == 0:
            self.logger_console.critical(msg1, *args, **kwargs)
        else:
            self.logger_file.critical(msg, *args, **kwargs)
            self.logger_console.critical(msg1, *args, **kwargs)
        set_cmd_text_color(self.fore_color)

# 定义一个logger
logger = LoggerWrapper()
