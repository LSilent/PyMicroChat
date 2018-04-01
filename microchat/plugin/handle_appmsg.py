import json
from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from .  import plugin
from bs4 import BeautifulSoup
from ..Util import logger


# appmsg 消息处理
def appmsg_handler(msg):
    # 读取消息类型
    try:
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        msg_type = soup.appmsg.type.contents[0]                     # 红包:<type><![CDATA[2001]]></type>
    except:
        pass

    if '2001' == msg_type:                                          # 红包消息
        if plugin.TEST_STATE[4]:                                    # 自动抢红包功能开关
            auto_recive_hb(msg)                                     # 自动抢红包
    return


# 自动抢红包
def auto_recive_hb(msg):
    try:
        # 解析nativeUrl,获取msgType,channelId,sendId
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        nativeUrl = soup.msg.appmsg.wcpayinfo.nativeurl.contents[0]
        msgType = Util.find_str(nativeUrl,'msgtype=','&')
        channelId = Util.find_str(nativeUrl,'&channelid=','&')
        sendId = Util.find_str(nativeUrl,'&sendid=','&')

        # 领红包
        (ret_code,info) = interface.receive_and_open_wxhb(channelId,msgType,nativeUrl,sendId)
        if not ret_code:
            logger.info('自动抢红包成功!')
            logger.debug('红包详细信息:' + info)
    except:
        logger.info('自动抢红包失败!')
    return