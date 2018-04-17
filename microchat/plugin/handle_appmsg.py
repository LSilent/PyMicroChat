import json
from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from .  import plugin
from bs4 import BeautifulSoup
from .logger_wrapper import logger


# appmsg 消息处理
def appmsg_handler(msg):
    # 读取消息类型
    try:
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        msg_type = soup.appmsg.type.contents[0]                     # 红包:<type><![CDATA[2001]]></type>  转账: <type>2000</type>
    except:
        pass  

    if '2001' == msg_type:                                          # 红包消息
        if plugin.TEST_STATE[4]:                                    # 自动抢红包功能开关
            auto_recive_hb(msg)                                     # 自动抢红包
            qry_detail_wxhb(msg)                                    # 获取红包领取信息
    elif '2000' == msg_type:                                        # 转账信息
        if plugin.TEST_STATE[4]:                                    # 自动收款功能开关
            auto_confirm_transfer(msg)                              # 自动确认收款
            transfer_query(msg)                                     # 查看转账记录
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
            logger.info('自动抢红包成功!', 11)
            logger.debug('红包详细信息:' + info)
        else:
            logger.info('红包详细信息:' + info, 13)
    except:
        logger.info('自动抢红包失败!', 13)
    return

# 查看红包信息
def qry_detail_wxhb(msg):
    try:
        # 解析nativeUrl,获取sendId
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        nativeUrl = soup.msg.appmsg.wcpayinfo.nativeurl.contents[0]
        sendId = Util.find_str(nativeUrl, '&sendid=', '&')

        # 查看红包领取情况
        (ret_code,info) = interface.qry_detail_wxhb(nativeUrl, sendId)
        logger.info('查询红包详细信息:\n错误码:{}\n领取信息:{}'.format(ret_code, info), 13)
    except:
        logger.info('查看红包详细信息失败!', 13)
    return

# 自动确认收款
def auto_confirm_transfer(msg):  
    # 过滤自己发出去的收款信息(收款成功通知)
    if msg.from_id.id == Util.wxid:
        return

    try: 
        # 解析transcationid，transferid，invalidtime
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        transaction_id  = soup.msg.appmsg.wcpayinfo.transcationid.contents[0]
        trans_id        = soup.msg.appmsg.wcpayinfo.transferid.contents[0]
        invalid_time    = soup.msg.appmsg.wcpayinfo.invalidtime.contents[0]

        # 确认收款
        (ret_code,info) = interface.transfer_operation(invalid_time, trans_id, transaction_id, msg.from_id.id)
        if not ret_code:
            logger.info('收款成功!', 11)
            logger.debug('转账详细信息:' + info)
        else:
            logger.info('转账详细信息:' + info, 13)
    except:
        logger.info('自动收款失败!', 13)     
    return

# 查询转账记录
def transfer_query(msg):
    # 过滤自己发出去的收款信息(收款成功通知)
    if msg.from_id.id == Util.wxid:
        return
    
    try:
        # 解析transcationid，transferid，invalidtime
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        trans_id        = soup.msg.appmsg.wcpayinfo.transcationid.contents[0]
        transfer_id     = soup.msg.appmsg.wcpayinfo.transferid.contents[0]
        invalid_time    = soup.msg.appmsg.wcpayinfo.invalidtime.contents[0]

        # 查询转账记录
        (ret_code,info) = interface.transfer_query(invalid_time, trans_id, transfer_id)
        logger.info('[查询转账记录]:\n错误码:{}\n转账信息:{}'.format(ret_code, info), 13)
    except:
        logger.info('查询转账记录失败!', 13)
    return