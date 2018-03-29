import struct
from . import business
from . import interface
from . import Util
from socket import *
from .Util import logger

# recv缓冲区大小
BUFFSIZE = 4096

# 封包编号(递增1)
seq = 1

# 心跳包seq id
HEARTBEAT_SEQ = 0xFFFFFFFF

# 长链接确认包seq id
IDENTIFY_SEQ = 0xFFFFFFFE

# 推送消息seq id
PUSH_SEQ = 0

# cmd id
CMDID_NOOP_REQ = 6  # 心跳
CMDID_IDENTIFY_REQ = 205  # 长链接确认
CMDID_MANUALAUTH_REQ = 253  # 登录
CMDID_PUSH_ACK = 24  # 推送通知
CMDID_REPORT_KV_REQ = 1000000190  # 通知服务器消息已接收

# 解包结果
UNPACK_FAIL = -1  # 解包失败
UNPACK_CONTINUE = 0  # 封包不完整,继续接收数据
UNPACK_OK = 1  # 解包成功

# 登录包aes key
login_aes_key = b''

# 长链接套接字
longlink = socket(AF_INET, SOCK_STREAM)

# 上次发送心跳时间
last_heartbeat_time = 0

# 心跳时间间隔（秒）(4分半内必须通信一次)
HEARTBEAT_TIMEOUT = 60

# 长链接组包


def pack(cmd_id, buf=b''):
    global seq
    header = bytearray(0)
    header += struct.pack(">I", len(buf)+16)  # 封包总长度(含包头) 4字节
    header += b'\x00\x10'  # 包头长度 2字节 固定00 10(包头长16字节)
    header += b'\x00\x01'  # 协议版本 2字节 固定00 01
    header += struct.pack(">I", cmd_id)  # cmd_id 4字节  不同cgi对应不同cmd_id
    if CMDID_NOOP_REQ == cmd_id:
        header += struct.pack(">I", HEARTBEAT_SEQ)  # 心跳包
    elif CMDID_IDENTIFY_REQ == cmd_id:
        # 登录确认包(暂未实现;该请求确认成功后服务器会直接推送消息内容,否则服务器只下发推送通知,需要主动同步消息)
        header += struct.pack(">I", IDENTIFY_SEQ)
    else:
        header += struct.pack(">I", seq)  # 封包编号 4字节 (除心跳-1，推送0外,其余消息从1每次自增1)
        # 封包编号自增
        seq += 1

    logger.debug('长链接包头:{}'.format(Util.b2hex(header)))

    return header + buf

# 长链接解包


def unpack(buf):
    if len(buf) < 16:  # 包头不完整
        return (UNPACK_CONTINUE, b'')
    else:
        # 解析包头
        header = buf[:16]
        (len_ack, cmd_id_ack, seq_id_ack) = struct.unpack('>I4xII', header)
        logger.info('收到新的封包,长度:{},cmd_id:{},seq_id:0x{:x}'.format(
            len_ack, cmd_id_ack, seq_id_ack))
        # 包长合法性验证
        if len(buf) < len_ack:  # 包体不完整
            return (UNPACK_CONTINUE, b'')
        else:
            if CMDID_PUSH_ACK == cmd_id_ack and PUSH_SEQ == seq_id_ack:  # 推送通知:服务器有新消息
                # 尝试获取sync key
                sync_key = Util.get_sync_key()
                if sync_key:  # sync key存在
                    interface.new_sync()  # 使用newsync同步消息
                    # 通知服务器消息已接收
                    longlink.send(pack(CMDID_REPORT_KV_REQ,
                                       business.sync_done_req2buf()))
                else:  # sync key不存在
                    interface.new_init()  # 使用短链接newinit初始化sync key
            else:
                cmd_id = cmd_id_ack - 1000000000
                if CMDID_NOOP_REQ == cmd_id:  # 心跳响应
                    logger.info('心跳返回:{}'.format(Util.b2hex(buf)))
                    pass
                elif CMDID_MANUALAUTH_REQ == cmd_id:  # 登录响应
                    if business.login_buf2Resp(buf[16:len_ack], login_aes_key):
                        raise RuntimeError('登录失败!')  # 登录失败
                    else:
                        # 登录成功,测试发送消息接口
                        #interface.new_send_msg('weixin','Hello weixin!'.encode(encoding="utf-8"))
                        pass
            return (UNPACK_OK, buf[len_ack:])

    return (UNPACK_OK, b'')


def send_heartbeat():
    global last_heartbeat_time
    # 判断是否需要发送心跳包
    if (Util.get_utc() - last_heartbeat_time) > HEARTBEAT_TIMEOUT:
        # 长链接发包
        longlink.send(pack(CMDID_NOOP_REQ))
        # 记录本次发送心跳时间
        last_heartbeat_time = Util.get_utc()
        return True
    else:
        return False


# 长链接demo
def run(name, password):
    # 连接服务器
    longlink.settimeout(HEARTBEAT_TIMEOUT + 1)
    longlink.connect((Util.ip['longip'], 443))

    # 发送心跳
    if send_heartbeat():
        recv_data = longlink.recv(BUFFSIZE)
        logger.info('服务器返回心跳数据:{}'.format(Util.b2hex(recv_data)))

    # 登录
    global login_aes_key
    (login_buf, login_aes_key) = business.login_req2buf(name, password)
    longlink.send(pack(CMDID_MANUALAUTH_REQ, login_buf))

    # 死循环recv
    recv_data = b''
    while True:
        try:
            recv_data += longlink.recv(BUFFSIZE)
        except Exception as e:
            if str(e) == 'timed out':
                # 发送心跳
                send_heartbeat()
                continue
            else:
                raise RuntimeError('recv Error!!!')
        logger.debug('收到数据:{}'.format(Util.b2hex(recv_data)))
        (ret, buf) = unpack(recv_data)
        if UNPACK_OK == ret:
            while UNPACK_OK == ret:
                (ret, buf) = unpack(buf)
            recv_data = buf
            # 刷新心跳
            send_heartbeat()
        elif UNPACK_CONTINUE == ret:
            pass

    longlink.close()
    return
