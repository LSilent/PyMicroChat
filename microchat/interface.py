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
from .plugin.logger_wrapper import logger, ColorDefine
from google.protobuf.internal import decoder, encoder
from . import logo_bingo


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

# 发消息(Utf-8编码)(使用at功能时消息内容必须至少有相同数量的@符号,允许不以\u2005结尾)
def new_send_msg(to_wxid, msg_content, at_user_list = [], msg_type=1):
    # 组包
    send_data = business.new_send_msg_req2buf(to_wxid, msg_content, at_user_list, msg_type)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/newsendmsg', send_data)
    logger.debug('new_send_msg返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    (ret_code, svrid) = business.new_send_msg_buf2resp(ret_bytes)
    # 消息记录存入数据库
    Util.insert_msg_to_db(svrid, Util.get_utc(), Util.wxid,to_wxid, msg_type, msg_content.decode())
    # 返回发送消息结果
    return ret_code, svrid

# 分享链接
def send_app_msg(to_wxid, title, des, link_url, thumb_url=''):
     # 组包
    send_data, msg_content, client_msg_id = business.send_app_msg_req2buf(to_wxid, title, des, link_url, thumb_url)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/sendappmsg', send_data)
    logger.debug('send_app_msg返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    (ret_code, svrid) = business.send_app_msg_buf2resp(ret_bytes)
    # 消息记录存入数据库
    Util.insert_msg_to_db(svrid, Util.get_utc(),Util.wxid, to_wxid, 5, msg_content, client_msg_id)
    # 返回发送消息结果
    return ret_code, svrid

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

# 查看红包详情(limit,offset参数设置本次请求返回领取红包人数区间)
def qry_detail_wxhb(nativeUrl, sendId, limit = 11, offset = 0, ver='v1.0'):
    # 组包
    send_data = business.qry_detail_wxhb_req2buf(nativeUrl, sendId, limit, offset, ver)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/mmpay-bin/qrydetailwxhb', send_data)
    logger.debug('qrydetailwxhb返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.qry_detail_wxhb_buf2resp(ret_bytes)

# 发emoji表情：file_name为emoji加密文件名; game_type=0直接发送emoji; game_type=1无视file_name参数,接收方播放石头剪刀布动画;其余game_type值均为投骰子动画;
# content只在game_type不为0即发送游戏表情时有效;content取1-3代表剪刀、石头、布;content取4-9代表投骰子1-6点;
def send_emoji(wxid, file_name, game_type, content):
    # 组包
    send_data, client_msg_id = business.send_emoji_req2buf(wxid, file_name, game_type, content)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/sendemoji', send_data)
    logger.debug('send_emoji返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    ret_code, svrid  = business.send_emoji_buf2resp(ret_bytes)
    # 消息记录存入数据库
    Util.insert_msg_to_db(svrid, Util.get_utc(), Util.wxid, wxid, 47, file_name, client_msg_id)
    return ret_code, svrid

# 收款
def transfer_operation(invalid_time, trans_id, transaction_id, user_name):
    # 组包
    send_data = business.transfer_operation_req2buf(invalid_time, trans_id, transaction_id, user_name)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/mmpay-bin/transferoperation', send_data)
    logger.debug('transfer_operation返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.transfer_operation_buf2resp(ret_bytes)

# 查询转账结果
def transfer_query(invalid_time, trans_id, transfer_id):
    # 组包
    send_data = business.transfer_query_req2buf(invalid_time, trans_id, transfer_id)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/mmpay-bin/transferquery', send_data)
    logger.debug('transfer_query返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.transfer_query_buf2resp(ret_bytes)

# 刷新好友信息(通讯录中的好友或群聊可以获取详细信息;陌生人仅可获取昵称和头像)
def get_contact(wxid):
    # 组包
    send_data = business.get_contact_req2buf(wxid)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/getcontact', send_data)
    logger.debug('get_contact返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.get_contact_buf2resp(ret_bytes)

# 获取群成员列表
def get_chatroom_member_list(wxid):
    friend, __ = get_contact(wxid)
    return [member.wxid for member in friend.group_member_list.member]

# 建群聊(参数group_member_list为群成员wxid)(建群成功返回新建群聊的wxid)
def create_chatroom(group_member_list):
    # 组包
    send_data = business.create_chatroom_req2buf(group_member_list)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/createchatroom', send_data)
    logger.debug('createchatroom返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.create_chatroom_buf2resp(ret_bytes)

# 面对面建群(参数为群密码,建群地点经纬度)(无需好友建群方便测试)
# 建群成功返回新建群聊的wxid;系统会发10000消息通知群创建成功;使用相同密码短时间内会返回同一群聊
def mm_facing_create_chatroom(pwd = '9999', lon = 116.39, lat = 38.90):
    # 面对面建群步骤1组包
    send_data = business.mm_facing_create_chatroom_req2buf(0, pwd, lon, lat)
    # 面对面建群步骤1发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/mmfacingcreatechatroom', send_data)
    logger.debug('mmfacingcreatechatroom返回数据:' + Util.b2hex(ret_bytes))
    # 面对面建群步骤1解包
    ret, wxid = business.mm_facing_create_chatroom_buf2resp(ret_bytes, 0)
    if not ret:
        # 面对面建群步骤2组包
        send_data = business.mm_facing_create_chatroom_req2buf(1, pwd, lon, lat)
        # 面对面建群步骤2发包
        ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/mmfacingcreatechatroom', send_data)
        logger.debug('mmfacingcreatechatroom返回数据:' + Util.b2hex(ret_bytes))
        # 面对面建群步骤2解包
        ret, wxid = business.mm_facing_create_chatroom_buf2resp(ret_bytes, 1)
        return wxid
    return ''

# 群聊拉人
def add_chatroom_member(chatroom_wxid, member_list):
    # 组包
    send_data = business.add_chatroom_member_req2buf(chatroom_wxid, member_list)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/addchatroommember', send_data)
    logger.debug('addchatroommember返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.add_chatroom_member_buf2resp(ret_bytes)

# 群聊中at所有人(每100人一条消息)(最后发送文字消息)
def at_all_in_group(chatroom_wxid, send_text):
    group, __ = get_contact(chatroom_wxid)
    at_text = ''
    at_list = []
    for i in range(group.group_member_list.cnt):
        if i and i%100 == 0:
            #每at100人发送一次消息
            new_send_msg(chatroom_wxid,at_text.encode(encoding = 'utf-8'), at_list)
            at_text = ''
            at_list = []
        at_text += '@{}'.format(group.group_member_list.member[i].nick_name)
        at_list.append(group.group_member_list.member[i].wxid)
    if at_text and at_list:
        new_send_msg(chatroom_wxid,at_text.encode(encoding = 'utf-8'), at_list)
    # 发送文字消息
    if send_text:
        new_send_msg(chatroom_wxid,send_text.encode(encoding = 'utf-8'))
    return

# 设置群聊中自己昵称(utf-8)
def set_group_nick_name(chatroom_wxid, nick_name):
    # 组包
    send_data = business.set_group_nick_name_req2buf(chatroom_wxid, nick_name)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/oplog', send_data)
    logger.debug('oplog返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.set_group_nick_name_buf2resp(ret_bytes)

# 消息撤回
def revoke_msg(wxid, svrid):
    # 组包
    send_data = business.revoke_msg_req2buf(wxid, svrid)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/revokemsg', send_data)
    logger.debug('revokemsg返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.revoke_msg_buf2resp(ret_bytes)

# 从通讯录中删除好友/恢复好友(删除对方后可以用此接口再添加对方)
# 群聊使用此接口可以保存到通讯录
def delete_friend(wxid, delete = True):
    # 获取好友(群聊)详细信息
    friend, __ = get_contact(wxid)
    # 设置保存通讯录标志位
    if delete:
        friend.type = (friend.type>>1)<<1                       # 清零
    else:
        friend.type |= 1                                        # 置1
    # 组包
    send_data = business.op_friend_req2buf(friend.SerializeToString())
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/oplog', send_data)
    logger.debug('oplog返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.op_friend_buf2resp(ret_bytes)

# 拉黑/恢复 好友关系
def ban_friend(wxid, ban = True):
    # 获取好友(群聊)详细信息
    friend, __ = get_contact(wxid)
    # 设置黑名单标志位
    if ban:
        friend.type |= 1<<3                                     # 置1
    else:
        friend.type = ((friend.type>>4)<<4) + (friend.type&7)   # 清零
    # 组包
    send_data = business.op_friend_req2buf(friend.SerializeToString())
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/oplog', send_data)
    logger.debug('oplog返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.op_friend_buf2resp(ret_bytes)

# 设置好友备注名/群聊名
def set_friend_name(wxid, name):
    cmd_id = 2
    # 获取好友(群聊)详细信息
    friend, __ = get_contact(wxid)
    if wxid.endswith('@chatroom'):
        # 群聊: 设置群聊名/cmd_id
        friend.nickname.name = name
        cmd_id = 27
    else:
        # 好友: 设置备注名
        friend.remark_name.name = name
    # 组包
    send_data = business.op_friend_req2buf(friend.SerializeToString(), cmd_id)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/oplog', send_data)
    logger.debug('oplog返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.op_friend_buf2resp(ret_bytes)

# 发布群公告(仅限群主;自动@所有人)
def set_chatroom_announcement(wxid, text):
    # 组包
    send_data = business.set_chatroom_announcement_req2buf(wxid, text)
    # 发包
    ret_bytes = Util.mmPost('/cgi-bin/micromsg-bin/setchatroomannouncement', send_data)
    logger.debug('setchatroomannouncement返回数据:' + Util.b2hex(ret_bytes))
    # 解包
    return business.set_chatroom_announcement_buf2resp(ret_bytes)

# 初始化python模块
def init_all():
    #配置logger
    logger.config("microchat", out=2)
    logo_bingo()
    # 初始化ECC key
    if not Util.GenEcdhKey():
        logger.error('初始化ECC Key失败!')
        Util.ExitProcess()
    # 从db加载dns
    dns_ip.load_dns()
