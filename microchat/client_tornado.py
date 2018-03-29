from tornado import gen
from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
import struct
from .dns_ip import get_ips
from . import interface
from . import Util
from . import business

#recv缓冲区大小
BUFFSIZE = 4096

#心跳包seq id
HEARTBEAT_SEQ = 0xFFFFFFFF

#长链接确认包seq id
IDENTIFY_SEQ = 0xFFFFFFFE

#推送消息seq id
PUSH_SEQ = 0

#cmd id
CMDID_NOOP_REQ = 6  #心跳
CMDID_IDENTIFY_REQ = 205  #长链接确认
CMDID_MANUALAUTH_REQ = 253  #登录
CMDID_PUSH_ACK = 24  #推送通知
CMDID_REPORT_KV_REQ = 1000000190  #通知服务器消息已接收

#解包结果
UNPACK_FAIL = -1  #解包失败
UNPACK_CONTINUE = 0  #封包不完整,继续接收数据
UNPACK_OK = 1  #解包成功


def recv_data_handler(recv_data):
    print("tornado recv: ", recv_data)


#心跳时间间隔（秒）
HEARTBEAT_TIMEOUT = 60


class ChatClient(object):
    """docstring for ChatClient"""

    def __init__(self, ioloop, recv_cb, host, port, usr_name, passwd):
        self.ioloop = ioloop
        self.recv_cb = recv_cb
        self.host = host
        self.port = port
        self.usr_name = usr_name
        self.passwd = passwd
        self.last_heartbeat_time = 0
        self.cnt = 0
        #封包编号(递增1)
        self.seq = 1
        self.login_aes_key = b''
        self.recv_data = b''

    @gen.coroutine
    def start(self):
        self.stream = yield TCPClient().connect(self.host, self.port)
        self.send_heart_beat()
        # self.stream.read_until(b'\n', self.__recv)
        self.longin()
        self.stream.read_bytes(16, self.__recv_header)

    def send_heart_beat(self):
        print(
            'last_heartbeat_time={},Util.get_utc() - last_heartbeat_time = {}'.
            format(self.last_heartbeat_time,
                   Util.get_utc() - self.last_heartbeat_time))
        #判断是否需要发送心跳包
        if (Util.get_utc() - self.last_heartbeat_time) > HEARTBEAT_TIMEOUT:
            #长链接发包
            send_data = self.pack(CMDID_NOOP_REQ)
            self.stream.write(send_data)
            #记录本次发送心跳时间
            self.last_heartbeat_time = Util.get_utc()
            return True
        else:
            return False

    def longin(self):
        (login_buf, self.login_aes_key) = business.login_req2buf(
            self.usr_name, self.passwd)
        send_data = self.pack(CMDID_MANUALAUTH_REQ, login_buf)
        self.stream.write(send_data)

    @gen.coroutine
    def __recv_header(self, data):
        self.cnt += 1
        self.recv_data = data
        print('recive from the server', data)
        (len_ack, _, _) = struct.unpack('>I4xII', data)
        if self.recv_cb:
            self.recv_cb(data)
        # yield self.stream.read_until(b'\n', self.__recv)
        yield self.stream.read_bytes(len_ack - 16, self.__recv_payload)

    @gen.coroutine
    def __recv_payload(self, data):
        print('recive from the server', data)
        if self.recv_cb:
            self.recv_cb(data)
        self.recv_data += data
        if data != b'':
            (ret, buf) = self.unpack(self.recv_data)
            if UNPACK_OK == ret:
                (ret, buf) = self.unpack(buf)
                while UNPACK_OK == ret:
                    (ret, buf) = self.unpack(buf)
                #刷新心跳
                self.send_heart_beat()
        # yield self.stream.read_until(b'\n', self.__recv)
        yield self.stream.read_bytes(16, self.__recv_header)

    @gen.coroutine
    def send(self, data):
        yield self.stream.write(data.encode('utf-8'))

    def stop(self):
        self.ioloop.stop()

    #长链接组包
    def pack(self, cmd_id, buf=b''):
        header = bytearray(0)
        header += struct.pack(">I", len(buf) + 16)
        header += b'\x00\x10'
        header += b'\x00\x01'
        header += struct.pack(">I", cmd_id)
        if CMDID_NOOP_REQ == cmd_id:  #心跳包
            header += struct.pack(">I", HEARTBEAT_SEQ)
        elif CMDID_IDENTIFY_REQ == cmd_id:
            header += struct.pack(
                ">I", IDENTIFY_SEQ
            )  #登录确认包(暂未实现;该请求确认成功后服务器会直接推送消息内容,否则服务器只下发推送通知,需要主动同步消息)
        else:
            header += struct.pack(">I", self.seq)
            #封包编号自增
            self.seq += 1

        return header + buf

    #长链接解包
    def unpack(self, buf):
        if len(buf) < 16:                                           #包头不完整
            return (UNPACK_CONTINUE,b'')
        else:
            #解析包头
            header = buf[:16]
            (len_ack, cmd_id_ack, seq_id_ack) = struct.unpack('>I4xII', header)
            print('封包长度:{},cmd_id:{},seq_id:0x{:x}'.format(len_ack, cmd_id_ack,
                                                        seq_id_ack))
            #包长合法性验证
            if len(buf) < len_ack:  #包体不完整
                return (UNPACK_CONTINUE, b'')
            else:
                if CMDID_PUSH_ACK == cmd_id_ack and PUSH_SEQ == seq_id_ack:  #推送通知:服务器有新消息
                    #尝试获取sync key
                    sync_key = Util.get_sync_key()
                    if sync_key:  #sync key存在
                        interface.new_sync()  #使用newsync同步消息
                        self.stream.write(
                            self.pack(CMDID_REPORT_KV_REQ,
                                    business.sync_done_req2buf()))  #通知服务器消息已接收
                    else:  #sync key不存在
                        interface.new_init()  #使用短链接newinit初始化sync key
                else:
                    cmd_id = cmd_id_ack - 1000000000
                    if CMDID_NOOP_REQ == cmd_id:  #心跳响应
                        pass
                    elif CMDID_MANUALAUTH_REQ == cmd_id:  #登录响应
                        if business.login_buf2Resp(buf[16:len_ack],
                                                self.login_aes_key):
                            raise RuntimeError('登录失败!')  #登录失败
                return (UNPACK_OK, buf[len_ack:])

        return (UNPACK_OK,b'')


def start(wechat_usrname, wechat_passwd):
    ioloop = IOLoop.instance()
    _, szlong_ip = get_ips()
    interface.InitAll()
    tcp_client = ChatClient(ioloop=ioloop, usr_name=wechat_usrname, passwd=wechat_passwd, recv_cb=recv_data_handler,
                            host=szlong_ip[0], port=443)
    tcp_client.start()
    PeriodicCallback(tcp_client.send_heart_beat, 1000*60).start()  # start scheduler
    ioloop.start()
