import http.client
import logging
import random
import struct
import string
import time
import urllib
import xmltodict
import zlib
from . import define
from . import dns_ip
from . import mm_pb2
from .plugin import plugin
from . import Util
from .plugin.logger_wrapper import logger
from google.protobuf.internal import decoder, encoder

# 组包(压缩加密+封包),参数:protobuf序列化后数据,cgi类型,是否使用压缩算法
def pack(src, cgi_type, use_compress=0):
    # 必要参数合法性判定
    if not Util.cookie or not Util.uin or not Util.sessionKey:
        return b''
    # 压缩加密
    len_proto_compressed = len(src)
    if use_compress:
        (body, len_proto_compressed) = Util.compress_and_aes(src, Util.sessionKey)
    else:
        body = Util.aes(src, Util.sessionKey)
    logger.debug("cgi:{},protobuf数据:{}\n加密后数据:{}".format(cgi_type, Util.b2hex(src), Util.b2hex(body)))
    # 封包包头
    header = bytearray(0)
    header += b'\xbf'                                                                               # 标志位(可忽略该字节)
    header += bytes([0])                                                                            # 最后2bit：02--包体不使用压缩算法;前6bit:包头长度,最后计算      
    header += bytes([((0x5 << 4) + 0xf)])                                                           # 05:AES加密算法  0xf:cookie长度(默认使用15字节长的cookie)
    header += struct.pack(">I", define.__CLIENT_VERSION__)                                          # 客户端版本号 网络字节序
    header += struct.pack(">i", Util.uin)                                                           # uin
    header += Util.cookie                                                                           # cookie
    header += encoder._VarintBytes(cgi_type)                                                        # cgi type
    header += encoder._VarintBytes(len(src))                                                        # body proto压缩前长度
    header += encoder._VarintBytes(len_proto_compressed)                                            # body proto压缩后长度
    header += bytes([0]*15)                                                                         # 3个未知变长整数参数,共15字节
    header[1] = (len(header) << 2) + (1 if use_compress else 2)                                     # 包头长度
    logger.debug("包头数据:{}".format(Util.b2hex(header)))
    # 组包
    senddata = header + body
    return senddata

# 解包
def UnPack(src, key=b''):
    if len(src) < 0x20:
        raise RuntimeError('Unpack Error!Please check mm protocol!')                                # 协议需要更新
        return b''
    if not key:
        key = Util.sessionKey
    # 解析包头
    nCur = 0
    if src[nCur] == struct.unpack('>B', b'\xbf')[0]:
        nCur += 1                                                                                   # 跳过协议标志位
    nLenHeader = src[nCur] >> 2                                                                     # 包头长度
    bUseCompressed = (src[nCur] & 0x3 == 1)                                                         # 包体是否使用压缩算法:01使用,02不使用
    nCur += 1
    nDecryptType = src[nCur] >> 4                                                                   # 解密算法(固定为AES解密): 05 aes解密 / 07 rsa解密
    nLenCookie = src[nCur] & 0xf                                                                    # cookie长度
    nCur += 1
    nCur += 4                                                                                       # 服务器版本(当前固定返回4字节0)
    uin = struct.unpack('>i', src[nCur:nCur+4])[0]                                                  # uin
    nCur += 4
    cookie_temp = src[nCur:nCur+nLenCookie]                                                         # cookie
    if cookie_temp and not(cookie_temp == Util.cookie):
        Util.cookie = cookie_temp                                                                   # 刷新cookie
    nCur += nLenCookie
    (nCgi, nCur) = decoder._DecodeVarint(src, nCur)                                                 # cgi type
    (nLenProtobuf, nCur) = decoder._DecodeVarint(src, nCur)                                         # 压缩前protobuf长度
    (nLenCompressed, nCur) = decoder._DecodeVarint(src, nCur)                                       # 压缩后protobuf长度
    logger.debug('包头长度:{}\n是否使用压缩算法:{}\n解密算法:{}\ncookie长度:{}\nuin:{}\ncookie:{}\ncgi type:{}\nprotobuf长度:{}\n压缩后protobuf长度:{}'.format(
        nLenHeader, bUseCompressed, nDecryptType, nLenCookie, uin, str(Util.cookie), nCgi, nLenProtobuf, nLenCompressed))
    # 对包体aes解密解压缩
    body = src[nLenHeader:]                                                                         # 取包体数据
    if bUseCompressed:
        protobufData = Util.decompress_and_aesDecrypt(body, key)
    else:
        protobufData = Util.aesDecrypt(body, key)
    logger.debug('解密后数据:%s' % str(protobufData))
    return protobufData

# 登录组包函数
def login_req2buf(name, password):
    # 随机生成16位登录包AesKey
    login_aes_key = bytes(''.join(random.sample(string.ascii_letters + string.digits, 16)), encoding="utf8")

    # protobuf组包1
    accountRequest = mm_pb2.ManualAuthAccountRequest(
        aes=mm_pb2.ManualAuthAccountRequest.AesKey(
            len=16,
            key=login_aes_key
        ),
        ecdh=mm_pb2.ManualAuthAccountRequest.Ecdh(
            nid=713,
            ecdhKey=mm_pb2.ManualAuthAccountRequest.Ecdh.EcdhKey(
                len=len(Util.EcdhPubKey),
                key=Util.EcdhPubKey
            )
        ),
        userName=name,
        password1=Util.GetMd5(password),
        password2=Util.GetMd5(password)
    )
    # protobuf组包2
    deviceRequest = mm_pb2.ManualAuthDeviceRequest(
        login=mm_pb2.LoginInfo(
            aesKey=login_aes_key,
            uin=0,
            guid=define.__GUID__ + '\0',  # guid以\0结尾
            clientVer=define.__CLIENT_VERSION__,
            androidVer=define.__ANDROID_VER__,
            unknown=1,
        ),
        tag2=mm_pb2.ManualAuthDeviceRequest._Tag2(),
        imei=define.__IMEI__,
        softInfoXml=define.__SOFTINFO__.format(define.__IMEI__, define.__ANDROID_ID__, define.__MANUFACTURER__+" "+define.__MODELNAME__, define.__MOBILE_WIFI_MAC_ADDRESS__,
                                               define.__CLIENT_SEQID_SIGN__, define.__AP_BSSID__, define.__MANUFACTURER__, "taurus", define.__MODELNAME__, define.__IMEI__),
        unknown5=0,
        clientSeqID=define.__CLIENT_SEQID__,
        clientSeqID_sign=define.__CLIENT_SEQID_SIGN__,
        loginDeviceName=define.__MANUFACTURER__+" "+define.__MODELNAME__,
        deviceInfoXml=define.__DEVICEINFO__.format(
            define.__MANUFACTURER__, define.__MODELNAME__),
        language=define.__LANGUAGE__,
        timeZone="8.00",
        unknown13=0,
        unknown14=0,
        deviceBrand=define.__MANUFACTURER__,
        deviceModel=define.__MODELNAME__+"armeabi-v7a",
        osType=define.__ANDROID_VER__,
        realCountry="cn",
        unknown22=2,  # Unknown
    )

    logger.debug("accountData protobuf数据:" + Util.b2hex(accountRequest.SerializeToString()))
    logger.debug("deviceData protobuf数据:" +  Util.b2hex(deviceRequest.SerializeToString()))

    # 加密
    reqAccount = Util.compress_and_rsa(accountRequest.SerializeToString())
    reqDevice = Util.compress_and_aes(deviceRequest.SerializeToString(), login_aes_key)

    logger.debug("加密后数据长度:reqAccount={},reqDevice={}".format(len(reqAccount), len(reqDevice[0])))
    logger.debug("加密后reqAccount数据:" + Util.b2hex(reqAccount))
    logger.debug("加密后reqDevice数据:" + Util.b2hex(reqDevice[0]))

    # 封包包体
    subheader = b''
    subheader += struct.pack(">I", len(accountRequest.SerializeToString()))                         # accountData protobuf长度
    subheader += struct.pack(">I", len(deviceRequest.SerializeToString()))                          # deviceData protobuf长度
    subheader += struct.pack(">I", len(reqAccount))                                                 # accountData RSA加密后长度
    # 包体由头信息、账号密码加密后数据、硬件设备信息加密后数据3部分组成
    body = subheader + reqAccount + reqDevice[0]

    # 封包包头
    header = bytearray(0)
    header += bytes([0])                                                                            # 最后2bit：02--包体不使用压缩算法;前6bit:包头长度,最后计算
    header += bytes([((0x7 << 4) + 0xf)])                                                           # 07:RSA加密算法  0xf:cookie长度
    header += struct.pack(">I", define.__CLIENT_VERSION__)                                          # 客户端版本号 网络字节序
    header += bytes([0]*4)                                                                          # uin
    header += bytes([0]*15)                                                                         # coockie
    header += encoder._VarintBytes(701)                                                             # cgi type
    header += encoder._VarintBytes(len(body))                                                       # body 压缩前长度
    header += encoder._VarintBytes(len(body))                                                       # body 压缩后长度(登录包不需要压缩body数据)
    header += struct.pack(">B", define.__LOGIN_RSA_VER__)                                           # RSA秘钥版本
    header += b'\x01\x02'                                                                           # Unknown Param
    header[0] = (len(header) << 2) + 2                                                              # 包头长度

    # 组包
    logger.debug('包体数据:' + str(body))
    logger.debug('包头数据:' + str(header))
    senddata = header + body

    return (senddata, login_aes_key)

# 登录解包函数
def login_buf2Resp(buf, login_aes_key):
    # 解包
    loginRes = mm_pb2.ManualAuthResponse()
    loginRes.result.code = -1
    loginRes.ParseFromString(UnPack(buf, login_aes_key))

    # 更新DNS信息
    for dns_info in loginRes.dns.redirect.real_host:
        if dns_info.host == 'long.weixin.qq.com':                                                   # 更新长链接信息
            dns_ip.long_ip = []                                                                     # 清空旧的长链接ip池
            for ip_info in loginRes.dns.ip.longlink:
                if  dns_info.redirect == ip_info.host.replace('\x00', ''):
                    logger.debug('更新长链接DNS:[{}:{}]'.format(dns_info.redirect, ip_info.ip.replace('\x00', '')))
                    dns_ip.long_ip.append(ip_info.ip.replace('\x00', ''))                           # 保存长链接ip
        elif dns_info.host == 'short.weixin.qq.com':                                                # 更新短链接信息
            dns_ip.short_ip = []                                                                    # 清空旧的短链接ip池
            for ip_info in loginRes.dns.ip.shortlink:
                if dns_info.redirect == ip_info.host.replace('\x00', ''):
                    logger.debug('更新短链接DNS:[{}:{}]'.format(dns_info.redirect, ip_info.ip.replace('\x00', '')))
                    dns_ip.short_ip.append(ip_info.ip.replace('\x00', ''))                          # 保存短链接ip
    # 保存dns到db
    dns_ip.save_dns()

    # 登录异常处理
    if -301 == loginRes.result.code:                                                                # DNS解析失败,请尝试更换idc
        logger.error('登陆结果:\ncode:{}\n即将尝试切换DNS重新登陆!'.format(loginRes.result.code))                    
    elif -106 == loginRes.result.code:                                                              # 需要在IE浏览器中滑动操作解除环境异常/扫码、短信、好友授权(滑动解除异常后需要重新登录一次)
        logger.error('登陆结果:\ncode:{}\nError msg:{}\n'.format(loginRes.result.code, loginRes.result.err_msg.msg[loginRes.result.err_msg.msg.find('<Content><![CDATA[')+len('<Content><![CDATA['):loginRes.result.err_msg.msg.find(']]></Content>')]))
        # 打开IE,完成授权
        logger.error('请在浏览器授权后重新登陆!')
        Util.OpenIE(loginRes.result.err_msg.msg[loginRes.result.err_msg.msg.find('<Url><![CDATA[')+len('<Url><![CDATA['):loginRes.result.err_msg.msg.find(']]></Url>')])
    elif loginRes.result.code:                                                                      # 其他登录错误
        logger.error('登陆结果:\ncode:{}\nError msg:{}\n'.format(loginRes.result.code, loginRes.result.err_msg.msg[loginRes.result.err_msg.msg.find(
            '<Content><![CDATA[')+len('<Content><![CDATA['):loginRes.result.err_msg.msg.find(']]></Content>')]))
    else:                                                                                           # 登陆成功
        # 密钥协商
        Util.sessionKey = Util.aesDecrypt(loginRes.authParam.session.key, Util.DoEcdh(loginRes.authParam.ecdh.ecdhKey.key))
        # 保存uin/wxid
        Util.uin = loginRes.authParam.uin
        Util.wxid = loginRes.accountInfo.wxId
        logger.info('登陆成功!\nsession_key:{}\nuin:{}\nwxid:{}\nnickName:{}\nalias:{}'.format(Util.sessionKey, Util.uin, Util.wxid, loginRes.accountInfo.nickName, loginRes.accountInfo.Alias),13)
        # 初始化db
        Util.init_db()

    return loginRes.result.code

# 首次登录设备初始化组包函数
def new_init_req2buf(cur=b'', max=b''):
    # protobuf组包
    new_init_request = mm_pb2.NewInitRequest(
        login=mm_pb2.LoginInfo(
            aesKey=Util.sessionKey,
            uin=Util.uin,
            guid=define.__GUID__ + '\0',  # guid以\0结尾
            clientVer=define.__CLIENT_VERSION__,
            androidVer=define.__ANDROID_VER__,
            unknown=3,
        ),
        wxid=Util.wxid,
        sync_key_cur=cur,
        sync_key_max=max,
        language=define.__LANGUAGE__,
    )

    # 组包
    return pack(new_init_request.SerializeToString(), 139)

# 更新好友信息
def update_contact_info(friend,update = True):
    tag = '[更新好友信息]' if update else '[查询好友信息]'
    is_friend = '<好友>' if (friend.type & 1) else '<非好友>'
    # 过滤系统wxid
    if friend.wxid.id in define.MM_DEFAULT_WXID:
        logger.info('{}:跳过默认wxid[{}]'.format(tag, friend.wxid.id), 6)
        return
    # 好友分类
    if friend.wxid.id.endswith('@chatroom'):                                                    # 群聊
        logger.info('{}{}:群聊名:{} 群聊wxid:{} chatroom_serverVer:{} chatroom_max_member:{} 群主:{} 群成员数量:{}'.format(tag, is_friend, friend.nickname.name, friend.wxid.id, friend.chatroom_serverVer, friend.chatroom_max_member, friend.chatroomOwnerWxid, friend.group_member_list.cnt), 6)
    elif friend.wxid.id.startswith('gh_'):                                                      # 公众号
        logger.info('{}{}:公众号:{} 公众号wxid:{} alias:{} 注册主体:{}'.format(tag, is_friend, friend.nickname.name, friend.wxid.id, friend.alias, friend.register_body if friend.register_body_type == 24 else '个人'), 6)
    else:                                                                                       # 好友
        logger.info('{}{}:昵称:{} 备注名:{} wxid:{} alias:{} 性别:{} 好友来源:{} 个性签名:{}'.format(tag, is_friend, friend.nickname.name, friend.remark_name.name, friend.wxid.id, friend.alias, friend.sex, Util.get_way(friend.src), friend.qianming), 6)
    if update or friend.wxid.id.endswith('@chatroom'):
        # 将好友信息存入数据库
        Util.insert_contact_info_to_db(friend.wxid.id, friend.nickname.name, friend.remark_name.name, friend.alias, friend.avatar_big, friend.v1_name, friend.type, friend.sex, friend.country,friend.sheng, friend.shi, friend.qianming, friend.register_body, friend.src, friend.chatroomOwnerWxid, friend.chatroom_serverVer, friend.chatroom_max_member, friend.group_member_list.cnt)
    return

# 首次登录设备初始化解包函数
def new_init_buf2resp(buf):
    # 解包
    res = mm_pb2.NewInitResponse()
    res.ParseFromString(UnPack(buf))

    # newinit后保存sync key
    Util.set_sync_key(res.sync_key_cur)                                                                 # newinit结束前不要异步调用newsync
    logger.debug('newinit sync_key_cur len:{}\ndata:{}'.format(len(res.sync_key_cur), Util.b2hex(res.sync_key_cur)))
    logger.debug('newinit sync_key_max len:{}\ndata:{}'.format(len(res.sync_key_max), Util.b2hex(res.sync_key_max)))

    # 初始化数据
    logger.info('newinit cmd数量:{},是否需要继续初始化:{}'.format(res.cntList, res.continue_flag))

    # 初始化
    for i in range(res.cntList):
        if 5 == res.tag7[i].type:                                                                       # 未读消息
            msg = mm_pb2.Msg()
            msg.ParseFromString(res.tag7[i].data.data)
            if 10002 == msg.type or 9999 == msg.type:                                                   # 过滤系统垃圾消息
                continue
            else:
                # 将消息存入数据库
                Util.insert_msg_to_db(msg.serverid, msg.createTime, msg.from_id.id, msg.to_id.id, msg.type, msg.raw.content)
                logger.info('收到新消息:\ncreate utc time:{}\ntype:{}\nfrom:{}\nto:{}\nraw data:{}\nxml data:{}'.format(Util.utc_to_local_time(msg.createTime), msg.type, msg.from_id.id, msg.to_id.id, msg.raw.content, msg.xmlContent))
        elif 2 == res.tag7[i].type:                                                                     # 好友列表
            friend = mm_pb2.contact_info()
            friend.ParseFromString(res.tag7[i].data.data)
            # 更新好友信息到数据库
            update_contact_info(friend)
    return (res.continue_flag, res.sync_key_cur, res.sync_key_max)

# 同步消息组包函数
def new_sync_req2buf():
    # protobuf组包
    req = mm_pb2.new_sync_req(
        flag=mm_pb2.new_sync_req.continue_flag(flag=0),
        selector=7,
        sync_Key=Util.get_sync_key(),
        scene=3,
        device=define.__ANDROID_VER__,
        sync_msg_digest=1,
    )

    # 组包
    return pack(req.SerializeToString(), 138)

# 同步消息解包函数
def new_sync_buf2resp(buf):
    # 解包
    res = mm_pb2.new_sync_resp()
    res.ParseFromString(UnPack(buf))

    # 刷新sync key
    Util.set_sync_key(res.sync_key)
    logger.debug('newsync sync_key len:{}\ndata:{}'.format(
        len(res.sync_key), Util.b2hex(res.sync_key)))

    # 解析
    for i in range(res.msg.cntList):
        if 5 == res.msg.tag2[i].type:                                                                       # 未读消息
            msg = mm_pb2.Msg()
            msg.ParseFromString(res.msg.tag2[i].data.data)
            if 9999 == msg.type:                                                                            # 过滤系统垃圾消息
                continue
            if 10002 == msg.type and 'weixin' ==  msg.from_id.id:                                           # 过滤系统垃圾消息                                                          
                continue   
            else:
                # 将消息存入数据库
                Util.insert_msg_to_db(msg.serverid, msg.createTime, msg.from_id.id, msg.to_id.id, msg.type, msg.raw.content)
                logger.info('收到新消息:\ncreate utc time:{}\ntype:{}\nfrom:{}\nto:{}\nraw data:{}\nxml data:{}'.format(Util.utc_to_local_time(msg.createTime), msg.type, msg.from_id.id, msg.to_id.id, msg.raw.content, msg.xmlContent))
                # 接入插件
                plugin.dispatch(msg)   
        elif 2 == res.msg.tag2[i].type:                                                                     # 更新好友消息
            friend = mm_pb2.contact_info()
            friend.ParseFromString(res.msg.tag2[i].data.data)
            # 更新好友信息到数据库
            update_contact_info(friend)
    return

# 通知服务器消息已接收(无返回数据)(仅用于长链接)
def sync_done_req2buf():
    # 取sync key
    sync_key = mm_pb2.SyncKey()
    sync_key.ParseFromString(Util.get_sync_key())
    # 包体
    body = sync_key.msgkey.SerializeToString()
    # 包头:固定8字节,网络字节序;4字节本地时间与上次newsync时间差(us);4字节protobuf长度
    header = b'\x00\x00\x00\xff' + struct.pack(">I", len(body))
    # 组包
    send_data = header + body
    logger.debug('report kv数据:{}'.format(Util.b2hex(send_data)))
    return send_data

# 发送文字消息请求(名片和小表情[微笑])
def new_send_msg_req2buf(to_wxid, msg_content, at_user_list = [], msg_type=1):
    # protobuf组包
    req = mm_pb2.new_send_msg_req(
        cnt=1,  # 本次发送消息数量(默认1条)
        msg=mm_pb2.new_send_msg_req.msg_info(
            to=mm_pb2.Wxid(id=to_wxid),
            content=msg_content,  # 消息内容
            type=msg_type,  # 默认发送文字消息,type=1
            utc=Util.get_utc(),
            client_id=Util.get_utc() + random.randint(0, 0xFFFF)                                            # 确保不重复
        )
    )
    # 群聊at功能
    if len(at_user_list):
        user_list = ''.join(["{},".format(x) for x in at_user_list]).strip(',')
        req.msg.at_list = '<msgsource><atuserlist><![CDATA[{}]]></atuserlist></msgsource>'.format(user_list)
    # 组包
    return pack(req.SerializeToString(), 522)

# 发送文字消息解包函数
def new_send_msg_buf2resp(buf):
    # 解包
    res = mm_pb2.new_send_msg_resp()
    res.ParseFromString(UnPack(buf))
    # 消息发送结果
    if res.res.code:                                                                                        # -44被删好友,-22被拉黑;具体提示系统会发type=10000的通知
        logger.info('消息发送失败,错误码:{}'.format(res.res.code))
    else:
        logger.debug('消息发送成功,svrid:{}'.format(res.res.svrid))

    return (res.res.code, res.res.svrid)

# 分享链接组包函数
def send_app_msg_req2buf(wxid, title, des, link_url, thumb_url):
    # protobuf组包
    req = mm_pb2.new_send_app_msg_req(
        login=mm_pb2.LoginInfo(
            aesKey=Util.sessionKey,
            uin=Util.uin,
            guid=define.__GUID__ + '\0',  # guid以\0结尾
            clientVer=define.__CLIENT_VERSION__,
            androidVer=define.__ANDROID_VER__,
            unknown=0,
        ),
        info=mm_pb2.new_send_app_msg_req.appmsg_info(
            from_wxid=Util.wxid,
            app_wxid='',
            tag3=0,
            to_wxid=wxid,
            type=5,
            content=define.SHARE_LINK.format(title, des, link_url, thumb_url),
            utc=Util.get_utc(),
            client_id='{}{}{}{}'.format(wxid, random.randint(
                1, 99), 'T', Util.get_utc()*1000 + random.randint(1, 999)),
            tag10=3,
            tag11=0,
        ),
        tag4=0,
        tag6=0,
        tag7='',
        fromScene='',
        tag9=0,
        tag10=0,
    )
    # 组包
    return pack(req.SerializeToString(), 222), req.info.content, req.info.client_id

# 分享链接解包函数
def send_app_msg_buf2resp(buf):
    # 解包
    res = mm_pb2.new_send_app_msg_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('分享链接发送结果:{},svrid:{}'.format(res.tag1.len, res.svrid))
    return (res.tag1.len, res.svrid)

#好友操作请求
def verify_user_req2buf(opcode,user_wxid,user_v1_name,user_ticket,user_anti_ticket,send_content):
    #protobuf组包
    req = mm_pb2.verify_user_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        op_code = opcode,
        tag3 = 1,
        user = mm_pb2.verify_user_req.user_info(
            wxid = user_v1_name,
            ticket = user_ticket,
            anti_ticket = user_anti_ticket,
            tag4 = 0,
            tag8 = 0,
        ),
        content = send_content,
        tag6 = 1,
        scene = b'\x06',
    )
    #组包
    return pack(req.SerializeToString(),30)

#好友操作结果
def verify_user_msg_buf2resp(buf): 
    #解包
    res = mm_pb2.verify_user_resp()
    res.ParseFromString(UnPack(buf))
    logger.info('好友操作返回结果:{},wxid:{}'.format(res.res.code,res.wxid))
    #返回对方wxid
    return res.wxid

#收红包请求1(获取timingIdentifier)
def recieve_wxhb_req2buf(channelId,msgType,nativeUrl,sendId,inWay = 1,ver='v1.0'):
    #protobuf组包
    wxhb_info = 'channelId={}&inWay={}&msgType={}&nativeUrl={}&sendId={}&ver={}'.format(channelId,inWay,msgType,urllib.parse.quote(nativeUrl),sendId,ver)
    req = mm_pb2.receive_wxhb_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        cmd = -1,
        tag3 = 1,
        info = mm_pb2.mmStr(
            len = len(wxhb_info),
            str = wxhb_info,
        )
    )
    #组包
    return pack(req.SerializeToString(),1581)

#收红包请求1响应[返回:(timingIdentifier,sendUser_wxid)]
def recieve_wxhb_buf2resp(buf):
    res = mm_pb2.receive_wxhb_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('红包详细信息:' + res.hb_info.str)
    try:
        if not res.ret_code and 'ok' == res.ret_msg:
            #解析timingIdentifier
            info = eval(res.hb_info.str)
            logger.info('[recieve_wxhb_buf2resp]timingIdentifier={},sendUserName={}'.format(info['timingIdentifier'],info['sendUserName']))
            return (info['timingIdentifier'],info['sendUserName'])
    except:
        pass
    logger.info('[recieve_wxhb_buf2resp]请求timingIdentifier失败,err_code={},err_msg:{}'.format(res.ret_code,res.ret_msg))    
    return ('','')

# 收红包请求2(拆红包)
def open_wxhb_req2buf(channelId,msgType,nativeUrl,sendId,sessionUserName,timingIdentifier,ver='v1.0'):
    #protobuf组包
    wxhb_info = 'channelId={}&msgType={}&nativeUrl={}&sendId={}&sessionUserName={}&timingIdentifier={}&ver={}'.format(channelId,msgType,urllib.parse.quote(nativeUrl),sendId,sessionUserName,timingIdentifier,ver)
    req = mm_pb2.open_wxhb_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        cmd = -1,
        tag3 = 1,
        info = mm_pb2.mmStr(
            len = len(wxhb_info),
            str = wxhb_info,
        )
    )
    #组包
    return pack(req.SerializeToString(),1685)

# 收红包请求2响应
def open_wxhb_buf2resp(buf):
    res = mm_pb2.open_wxhb_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('[红包领取结果]错误码={},详细信息:{}'.format(res.ret_code,res.res.str))
    return (res.ret_code,res.res.str)

# 查看红包信息请求
def qry_detail_wxhb_req2buf(nativeUrl, sendId, limit = 11, offset = 0, ver='v1.0'):
    #protobuf组包
    wxhb_info = 'limit={}&nativeUrl={}&offset={}&sendId={}&ver={}'.format(limit, urllib.parse.quote(nativeUrl), offset, sendId, ver)
    req = mm_pb2.qry_detail_wxhb_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        cmd = -1,
        tag3 = 1,
        info = mm_pb2.mmStr(
            len = len(wxhb_info),
            str = wxhb_info,
        )
    )
    return pack(req.SerializeToString(),1585)

# 查看红包信息响应
def qry_detail_wxhb_buf2resp(buf):
    res = mm_pb2.qry_detail_wxhb_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('[红包领取信息]错误码={},详细信息:{}'.format(res.ret_code,res.res.str))
    return (res.ret_code,res.res.str)

# 发送emoji表情
def send_emoji_req2buf(wxid, file_name, game_type, content):
    #protobuf组包
    req = mm_pb2.send_emoji_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        tag2 = 1,
        emoji = mm_pb2.send_emoji_req.emoji_info(
            animation_id = file_name,                                          # emoji 加密文件名                   
            tag2 = 0,
            tag3 = random.randint(1, 9999),
            tag4 = mm_pb2.send_emoji_req.emoji_info.TAG4(tag1 = 0),
            tag5 = 1,
            to_wxid = wxid,
            game_ext = '<gameext type="{}" content="{}" ></gameext>'.format(game_type, content),        
            tag8 = '',
            utc = '{}'.format(Util.get_utc() * 1000 + random.randint(1, 999)),
            tag11 = 0,
        ),
        tag4 = 0,
    )
    #组包
    return pack(req.SerializeToString(), 175), req.emoji.utc

# 发送emoji表情响应
def send_emoji_buf2resp(buf):
    res = mm_pb2.send_emoji_resp()
    res.ParseFromString(UnPack(buf))
    if res.res.code:                                                            # emoji发送失败                                                
        logger.info('emoji发送失败, 错误码={}'.format(res.res.code), 11)
    return res.res.code, res.res.svrid

# 收款请求
def transfer_operation_req2buf(invalid_time, trans_id, transaction_id, user_name):
    #protobuf组包
    transfer_operation = 'invalid_time={}&op=confirm&total_fee=0&trans_id={}&transaction_id={}&username={}'.format(invalid_time, trans_id, transaction_id, user_name)
    transfer_operation_with_sign = 'invalid_time={}&op=confirm&total_fee=0&trans_id={}&transaction_id={}&username={}&WCPaySign={}'.format(invalid_time, trans_id, transaction_id, user_name, Util.SignWith3Des(transfer_operation))
    req = mm_pb2.transfer_operation_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        tag2 = 0,
        tag3 = 1,
        info = mm_pb2.mmStr(
            len = len(transfer_operation_with_sign),
            str = transfer_operation_with_sign,
        )
    )
    #组包
    return pack(req.SerializeToString(), 385)

# 收款结果
def transfer_operation_buf2resp(buf):
    res = mm_pb2.transfer_operation_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('[收款结果]错误码={},详细信息:{}'.format(res.ret_code,res.res.str))
    return (res.ret_code,res.res.str)   

# 查询转账记录请求
def transfer_query_req2buf(invalid_time, trans_id, transfer_id):
    #protobuf组包
    transfer_info = 'invalid_time={}&trans_id={}&transfer_id={}'.format(invalid_time, trans_id, transfer_id)
    transfer_info_with_sign = 'invalid_time={}&trans_id={}&transfer_id={}&WCPaySign={}'.format(invalid_time, trans_id, transfer_id, Util.SignWith3Des(transfer_info))
    req = mm_pb2.transfer_query_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        tag2 = 0,
        tag3 = 1,
        info = mm_pb2.mmStr(
            len = len(transfer_info_with_sign),
            str = transfer_info_with_sign,
        )
    )
    #组包
    return pack(req.SerializeToString(), 385)

# 查询转账记录结果
def transfer_query_buf2resp(buf):
    res = mm_pb2.transfer_query_resp()
    res.ParseFromString(UnPack(buf))
    logger.debug('[查询转账记录]错误码={},详细信息:{}'.format(res.ret_code,res.res.str))
    return (res.ret_code,res.res.str)

# 获取好友信息请求
def get_contact_req2buf(wxid):
    #protobuf组包
    req = mm_pb2.get_contact_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        tag2 = 1,
        wxid = mm_pb2.Wxid(id = wxid),
        tag4 = 0,
        tag6 = 1,
        tag7 = mm_pb2.get_contact_req.TAG7(),
        tag8 = 0,
    )
    # 组包
    return pack(req.SerializeToString(), 182)

# 获取好友信息响应
def get_contact_buf2resp(buf):
    res = mm_pb2.get_contact_resp()
    res.ParseFromString(UnPack(buf))
    # 显示好友信息
    update_contact_info(res.info, False)
    return res.info, res.ticket

# 建群聊请求
def create_chatroom_req2buf(group_member_list):
    #protobuf组包
    req = mm_pb2.create_chatroom_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        tag2 = mm_pb2.create_chatroom_req.TAG2(),
        member_cnt = len(group_member_list),
        tag5 = 0,
    )
    # 添加群成员
    for wxid in group_member_list:
        member = req.member.add()
        member.wxid.id = wxid
    # 组包
    return pack(req.SerializeToString(), 119)

# 建群聊响应
def create_chatroom_buf2resp(buf):
    res = mm_pb2.create_chatroom_resp()
    res.ParseFromString(UnPack(buf))
    if not res.res.code and res.chatroom_wxid.id:
        logger.info('建群成功!群聊wxid:{}'.format(res.chatroom_wxid.id), 11)
    else:
        logger.info('建群失败!\n错误码:{}\n错误信息:{}'.format(res.res.code, res.res.msg.msg), 5)
    return res.chatroom_wxid.id

# 面对面建群请求
def mm_facing_create_chatroom_req2buf(op_code, pwd = '9999', lon = 116.39, lat = 39.90):
    #protobuf组包
    req = mm_pb2.mm_facing_create_chatroom_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        op_code = op_code,
        chatroom_pwd = pwd,
        lon = lon,
        lat = lat,
        tag6 = 1,
        tag9 = 0,
    )
    # 组包
    return pack(req.SerializeToString(), 653)

# 面对面建群响应
def mm_facing_create_chatroom_buf2resp(buf, op_code):
    res = mm_pb2.mm_facing_create_chatroom_resp()
    res.ParseFromString(UnPack(buf))
    if 0 == op_code:
        if res.res.code:
            logger.info('面对面建群步骤1失败!\n错误码:{}\n错误信息:{}'.format(res.res.code, res.res.msg.msg), 5)
        return res.res.code, ''
    else:    
        if not res.res.code and res.wxid:
            logger.info('面对面建群成功! {} 面对面群聊wxid:{}'.format(res.res.msg.msg, res.wxid), 11)
        else:
            logger.info('面对面建群步骤2失败!\n错误码:{}\n错误信息:{}'.format(res.res.code, res.res.msg.msg), 5)  
        return res.res.code, res.wxid

# 群聊拉人请求
def add_chatroom_member_req2buf(chatroom_wxid, member_list):
    #protobuf组包
    req = mm_pb2.add_chatroom_member_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        member_cnt = len(member_list),
        chatroom_wxid = mm_pb2.add_chatroom_member_req.chatroom_info(wxid = chatroom_wxid),
        tag5 = 0,
    )
    # 添加群成员
    for wxid in member_list:
        member = req.member.add()
        member.wxid.id = wxid
    # 组包
    return pack(req.SerializeToString(), 120)

# 群聊拉人响应
def add_chatroom_member_buf2resp(buf):
    res = mm_pb2.mm_facing_create_chatroom_resp()
    res.ParseFromString(UnPack(buf))
    return (res.res.code, res.res.msg.msg)

# 设置群聊昵称请求
def set_group_nick_name_req2buf(chatroom_wxid, nick_name):
    # protobuf组包
    req = mm_pb2.oplog_req(
        tag1 = mm_pb2.oplog_req.TAG1(
            tag1 = 1,
            cmd = mm_pb2.oplog_req.TAG1.CMD(
                cmd_id = 48,
                option = mm_pb2.oplog_req.TAG1.CMD.OPTION(
                    data = mm_pb2.op_set_group_nick_name(
                        tag1 = chatroom_wxid,
                        tag2 = Util.wxid,
                        tag3 = nick_name,
                    ).SerializeToString(),
                ),
            ),
        ), 
    )
    req.tag1.cmd.option.len = len(req.tag1.cmd.option.data)
    # 组包
    return pack(req.SerializeToString(), 681)

# 设置群聊昵称响应
def set_group_nick_name_buf2resp(buf):
    res = mm_pb2.oplog_resp()
    res.ParseFromString(UnPack(buf))
    try:
        code,__ = decoder._DecodeVarint(res.res.code, 0)
        if code:
            logger.info('设置群昵称失败,错误码:0x{:x},错误信息:{}'.format(code, res.res.msg), 11)
    except:
        code = -1
        logger.info('设置群昵称失败!', 11)
    return code

# 消息撤回请求
def revoke_msg_req2buf(wxid, svrid):
    # 在数据库中查询svrid对应的client_msg_id
    client_msg_id = Util.get_client_msg_id(svrid)
    #protobuf组包
    req = mm_pb2.revoke_msg_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        client_id = client_msg_id,
        new_client_id = 0,
        utc = Util.get_utc(),
        tag5 = 0,
        from_wxid = Util.wxid,
        to_wxid = wxid,
        index_of_request = 0,                                                       # 自增1
        svrid = svrid,
    )
    # 组包
    return pack(req.SerializeToString(), 594)

# 消息撤回响应
def revoke_msg_buf2resp(buf):
    res = mm_pb2.revoke_msg_resp()
    res.ParseFromString(UnPack(buf))
    logger.info('[消息撤回]错误码:{},提示信息:{}'.format(res.res.code, res.response_sys_wording), 11)
    return res.res.code

# 好友(群聊)操作请求:删除/保存/拉黑/恢复/设置群昵称/设置好友备注名
def op_friend_req2buf(friend_info, cmd = 2):
    #protobuf组包
    req = mm_pb2.oplog_req(
        tag1 = mm_pb2.oplog_req.TAG1(
            tag1 = 1,
            cmd = mm_pb2.oplog_req.TAG1.CMD(
                cmd_id = cmd,
                option = mm_pb2.oplog_req.TAG1.CMD.OPTION(
                    data = friend_info,
                ),
            ),
        ), 
    )
    req.tag1.cmd.option.len = len(req.tag1.cmd.option.data)
    # 组包
    return pack(req.SerializeToString(), 681)

# 好友(群聊)操作结果
def op_friend_buf2resp(buf):
    res = mm_pb2.oplog_resp()
    res.ParseFromString(UnPack(buf))
    try:
        code,__ = decoder._DecodeVarint(res.res.code, 0)
        if code:
            logger.info('好友操作失败,错误码:0x{:x},错误信息:{}'.format(code, res.res.msg), 11)
    except:
        code = -1
        logger.info('好友操作失败!', 11)
    return code

# 发布群公告请求(仅限群主;自动@所有人)
def set_chatroom_announcement_req2buf(wxid, text):
    #protobuf组包
    req = mm_pb2.set_chatroom_announcement_req(
        login = mm_pb2.LoginInfo(
            aesKey =  Util.sessionKey,
            uin = Util.uin,
            guid = define.__GUID__ + '\0',          #guid以\0结尾
            clientVer = define.__CLIENT_VERSION__,
            androidVer = define.__ANDROID_VER__,
            unknown = 0,
        ),
        chatroom_wxid = wxid,
        content = text,
    )
    # 组包
    return pack(req.SerializeToString(), 993)

# 发布群公告响应
def set_chatroom_announcement_buf2resp(buf):
    res = mm_pb2.set_chatroom_announcement_resp()
    res.ParseFromString(UnPack(buf))
    if res.res.code:
        logger.info('发布群公告失败!错误码:{},提示信息:{}'.format(res.res.code, res.res.message), 11)
    return res.res.code