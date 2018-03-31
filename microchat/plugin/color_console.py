'''
输出彩色终端字体，可扩展，可组合，跨平台...
@example: 
    print(ColorConsole.red('I am red!'))
-----------------colorama模块的一些常量---------------------------
Fore: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
Back: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
Style: DIM, NORMAL, BRIGHT, RESET_ALL
'''

from colorama import init, Fore, Back, Style
init(autoreset=True)


class ColorConsole(object):
   
    @staticmethod
    def red(s):
        """前景色:红色  背景色:默认"""
        return Fore.RED + s + Fore.RESET
    
    @staticmethod
    def green(s):
        """前景色:绿色  背景色:默认"""
        return Fore.GREEN + s + Fore.RESET

    @staticmethod
    def yellow(s):
        """前景色:黄色  背景色:默认"""
        return Fore.YELLOW + s + Fore.RESET

    
    @staticmethod
    def blue(s):
        """前景色:蓝色  背景色:默认"""
        return Fore.BLUE + s + Fore.RESET

    @staticmethod
    def magenta(s):
        """前景色:洋红色  背景色:默认"""
        return Fore.MAGENTA + s + Fore.RESET

    @staticmethod
    def cyan(s):
        """前景色:青色  背景色:默认"""
        return Fore.CYAN + s + Fore.RESET

    @staticmethod
    def white(s):
        """前景色:白色  背景色:默认"""
        return Fore.WHITE + s + Fore.RESET

    @staticmethod
    def black(s):
        """前景色:黑色  背景色:默认"""
        return Fore.BLACK

    @staticmethod
    def white_green(s):
        """前景色:白色  背景色:绿色"""
        return Fore.WHITE + Back.GREEN + s + Fore.RESET + Back.RESET