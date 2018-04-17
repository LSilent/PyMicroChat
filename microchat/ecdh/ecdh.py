from .openssl import OpenSSL
import ctypes
import sys
import hashlib

MD5_DIGEST_LENGTH = 16

def int_to_bytes(x):
    return x.to_bytes((x.bit_length() + 7) // 8, sys.byteorder)

def int_from_bytes(xbytes):
    return int.from_bytes(xbytes, sys.byteorder)

# 使用c接口生成ECDH本地密钥对
def gen_ecdh(curve=713):    
    # EC_KEY *ec_key = EC_KEY_new_by_curve_name(nid);
    ec_key = OpenSSL.EC_KEY_new_by_curve_name(curve)
    if ec_key == 0:
        raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ... " + OpenSSL.get_error())

    # int ret = EC_KEY_generate_key(ec_key);
    if (OpenSSL.EC_KEY_generate_key(ec_key)) == 0:
        OpenSSL.EC_KEY_free(ec_key)
        raise Exception("[OpenSSL] EC_KEY_generate_key FAIL ... " + OpenSSL.get_error())

    if (OpenSSL.EC_KEY_check_key(ec_key)) == 0:
        OpenSSL.EC_KEY_free(ec_key)
        raise Exception("[OpenSSL] EC_KEY_check_key FAIL ... " + OpenSSL.get_error())

    # int nLenPub = i2o_ECPublicKey(ec_key, NULL);
    len_pub = OpenSSL.i2o_ECPublicKey(ec_key, None)
    out_pub_key = ctypes.POINTER(ctypes.c_ubyte)()
    if (OpenSSL.i2o_ECPublicKey(ec_key, ctypes.byref(out_pub_key))) == 0:
        OpenSSL.EC_KEY_free(ec_key)
        raise Exception("[OpenSSL] i2o_ECPublicKey FAIL ... " + OpenSSL.get_error())

    lpub_key = [0]*len_pub
    for x in range(len_pub):
        lpub_key[x] = out_pub_key[x]
    pub_key = bytes(bytearray(lpub_key))
    OpenSSL.OPENSSL_free(out_pub_key, None, 0)

    # int nLenPub = i2d_ECPrivateKey(ec_key, NULL);
    len_pri = OpenSSL.i2d_ECPrivateKey(ec_key, None)
    out_pri_key = ctypes.POINTER(ctypes.c_ubyte)()
    if (OpenSSL.i2d_ECPrivateKey(ec_key, ctypes.byref(out_pri_key))) == 0:
        OpenSSL.EC_KEY_free(ec_key)
        raise Exception("[OpenSSL] i2d_ECPrivateKey FAIL ... " + OpenSSL.get_error())

    lpri_key = [0]*len_pri
    for y in range(len_pri):
        lpri_key[y] = out_pri_key[y]
    pri_key = bytes(bytearray(lpri_key))
    OpenSSL.OPENSSL_free(out_pri_key, None, 0)

    OpenSSL.EC_KEY_free(ec_key)

    return pub_key, len_pub, pri_key, len_pri

# void *KDF_MD5(const void *in, size_t inlen, void *out, size_t *outlen)
def kdf_md5(arr_in, in_len, arr_out, out_len):
    p_arr_in = ctypes.c_char_p(arr_in)
    p_arr_out = ctypes.c_char_p(arr_out)
    p_out_len = ctypes.POINTER(ctypes.c_long)(out_len)
    src = p_arr_in.value
    m = hashlib.md5()
    m.update(src)
    digest_m = m.digest()
    p_out_len.value = MD5_DIGEST_LENGTH
    p_arr_out.value = digest_m[:]
    return arr_out

# 密钥协商
def do_ecdh(curve, server_pub_key, local_pri_key):

    pub_ec_key = OpenSSL.EC_KEY_new_by_curve_name(curve)
    if pub_ec_key == 0:
        raise Exception("[OpenSSL] o2i_ECPublicKey FAIL ... " + OpenSSL.get_error())
    public_material = ctypes.c_char_p(server_pub_key)
    p_pub_ec_key = ctypes.c_void_p(pub_ec_key)
    pub_ec_key = OpenSSL.o2i_ECPublicKey(ctypes.byref(p_pub_ec_key), ctypes.byref(public_material), len(server_pub_key))
    if pub_ec_key == 0:
        OpenSSL.EC_KEY_free(pub_ec_key)
        raise Exception("[OpenSSL] o2i_ECPublicKey FAIL ... " + OpenSSL.get_error())

    pri_ec_key = OpenSSL.EC_KEY_new_by_curve_name(curve)
    if pri_ec_key == 0:
        OpenSSL.EC_KEY_free(pub_ec_key)
        raise Exception("[OpenSSL] d2i_ECPrivateKey FAIL ... " + OpenSSL.get_error())
    private_material = ctypes.c_char_p(local_pri_key)
    p_pri_ec_key = ctypes.c_void_p(pri_ec_key)
    pri_ec_key = OpenSSL.d2i_ECPrivateKey(ctypes.byref(p_pri_ec_key), ctypes.byref(private_material), len(local_pri_key))
    if pri_ec_key == 0:
        OpenSSL.EC_KEY_free(pub_ec_key)
        OpenSSL.EC_KEY_free(pri_ec_key)
        raise Exception("[OpenSSL] d2i_ECPrivateKey FAIL ... " + OpenSSL.get_error())

    share_key = ctypes.create_string_buffer(2048)

    # 回调函数
    # void *KDF_MD5(const void *in, size_t inlen, void *out, size_t *outlen)
    # KD_MD5 = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_long))
    # cb = KD_MD5(kdf_md5)

    ret = OpenSSL.ECDH_compute_key(share_key, 28, OpenSSL.EC_KEY_get0_public_key(pub_ec_key), pri_ec_key, 0)

    OpenSSL.EC_KEY_free(pub_ec_key)
    OpenSSL.EC_KEY_free(pri_ec_key)
    
    if ret:
        # 对share_key取md5
        m = hashlib.md5()
        m.update(share_key.value)
        digest_m = m.digest()    

        return MD5_DIGEST_LENGTH, digest_m
    return 0, None
