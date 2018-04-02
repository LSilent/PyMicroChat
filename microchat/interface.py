import http.client
import logging
import time
import random
import struct
import string
import urllib
import xmltodict
import zlib
from . import define
from . import dns_ip
from . import business
from . import Util
from . import mm_pb2
from .plugin.logger_wrapper import logger
from google.protobuf.internal import decoder, encoder


# 获取长短链接Ip
def GetDns():
    (ipShort,ipLong)  = dns_ip.get_ips()
    return {'longip':ipLong[0], 'shortip':ipShort[0]}

# 登录,参数为账号,密码
def Login(name, password):
    # 组包
    (senddata, login_aes_key) = business.login_req2buf(name, password)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/manualauth', senddata)
    logger.debug('返回数据:' + str(ret_bytes))
    # 解包
    return business.login_buf2Resp(ret_bytes, login_aes_key)

# 首次登录设备初始化
def new_init():
    continue_flag = True  # 需要继续初始化标志位(联系人过多需要多次初始化才能获取完整好友列表)
    cur = max = b''
    while continue_flag:
        # 组包
        send_data = business.new_init_req2buf(cur, max)
        # 发包
        ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/newinit', send_data)
        logger.debug('new_init返回数据:' + str(ret_bytes))
        # 解包
        (continue_flag, cur, max) = business.new_init_buf2resp(ret_bytes)

    return

# 同步消息
def new_sync():
    # 组包
    send_data = business.new_sync_req2buf()
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/newsync', send_data)
    logger.debug('new_sync返回数据:' + str(ret_bytes))
    # 解包
    return business.new_sync_buf2resp(ret_bytes)

# 发消息(Utf-8编码)
def new_send_msg(to_wxid, msg_content, msg_type=1):
    # 组包
    send_data = business.new_send_msg_req2buf(to_wxid, msg_content, msg_type)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/newsendmsg', send_data)
    logger.debug('new_send_msg返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    (ret_code, svrid) = business.new_send_msg_buf2resp(ret_bytes)
    # 消息记录存入数据库
    Util.insert_msg_to_db(svrid, Util.get_utc(), Util.wxid,to_wxid, msg_type, msg_content.decode())
    # 返回发送消息结果
    return ret_code

# 分享链接
def send_app_msg(to_wxid, title, des, link_url, thumb_url=''):
     # 组包
    (send_data, msg_content) = business.send_app_msg_req2buf(to_wxid, title, des, link_url, thumb_url)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/sendappmsg', send_data)
    logger.debug('send_app_msg返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    (ret_code, svrid) = business.send_app_msg_buf2resp(ret_bytes)
    # 消息记录存入数据库
    Util.insert_msg_to_db(svrid, Util.get_utc(),Util.wxid, to_wxid, 5, msg_content)
    # 返回发送消息结果
    return ret_code

# 获取好友列表(wxid,昵称,备注,alias,v1_name,头像)
def get_contact_list(contact_type=Util.CONTACT_TYPE_FRIEND):
    return Util.get_contact(contact_type)

# 好友请求
def verify_user(opcode, user_wxid, user_v1_name, user_ticket, user_anti_ticket, send_content):
    # 组包
    send_data = business.verify_user_req2buf(opcode, user_wxid, user_v1_name, user_ticket, user_anti_ticket, send_content)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/verifyuser', send_data)
    logger.debug('verify_user返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.verify_user_msg_buf2resp(ret_bytes)

# 收红包(返回0表示领取成功)
def receive_and_open_wxhb(channelId,msgType,nativeUrl,sendId,inWay = 1,ver='v1.0'):
    # 请求timingIdentifier组包
    send_data = business.recieve_wxhb_req2buf(channelId,msgType,nativeUrl,sendId,inWay,ver)
    # 请求timingIdentifier发包
    ret_bytes = Util.mmPost('/cgi-bin/mmpay-bin/receivewxhb', send_data)
    logger.debug('receivewxhb返回数据:' + Util.b2hex(ret_bytes))
    # 请求timingIdentifier解包
    (timingIdentifier,sessionUserName) = business.recieve_wxhb_buf2resp(ret_bytes)
    if timingIdentifier and sessionUserName:
        # 拆红包组包
        send_data = business.open_wxhb_req2buf(channelId,msgType,nativeUrl,sendId,sessionUserName,timingIdentifier,ver)
        # 拆红包发包
        ret_bytes = Util.mmPost('/cgi-bin/mmpay-bin/openwxhb', send_data)
        logger.debug('openwxhb返回数据:' + Util.b2hex(ret_bytes))
        # 拆红包解包
        return business.open_wxhb_buf2resp(ret_bytes)
    return (-1,'')

# 初始化python模块
def InitAll():
    # Util.initLog()
    Util.ip = GetDns()
    # 初始化ECC key
    if not Util.GenEcdhKey():
        logger.info('初始化ECC Key失败!')
        Util.ExitProcess()
