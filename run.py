from microchat import client_tornado
from microchat.plugin.logger_wrapper import logger, ColorDefine
from microchat import logo_bingo

#配置logger
logger.config("microchat", out=0)
logo_bingo()

def main():
    usrname = "13212345678"
    passwd = "123456"
    client_tornado.start(usrname, passwd)


if __name__ == '__main__':
    main()