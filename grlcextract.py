import sys

from binascii import hexlify, unhexlify
from hashlib import sha1, sha256

from jsonrpc.authproxy import AuthServiceProxy, JSONRPCException


RPCUSER = 'MY_GARLICOIN_CORE_RPC_USERNAME'
RPCPASSWORD = 'MY_GARLICOIN_CORE_RPC_PASSWORD'
RPCPORT = 42068


MAGIC = 'GRLCFILE'
__LAST_ID__ = '0000000000000000000000000000000000000000000000000000000000000000'

rpcproxy = None

def get_rpc_proxy():
    global rpcproxy
    if rpcproxy == None:
        rpcproxy = AuthServiceProxy('http://%s:%s@localhost:%d/' % (RPCUSER, RPCPASSWORD, RPCPORT))
    return rpcproxy

def get_tx_data_entries(txid):
    proxy = get_rpc_proxy()
    tx = proxy.decoderawtransaction(proxy.getrawtransaction(txid))
    return [ unhexlify(output['scriptPubKey']['asm'].split(' ')[-1]) for output in filter(lambda output: output['scriptPubKey']['type'] in [ 'witness_v0_scripthash', 'nulldata' ], tx['vout']) ]

def load_chunks_ids_from_index_chain(txid):
    data = ''
    while txid != __LAST_ID__:
        entries = get_tx_data_entries(txid)
        txid = hexlify(entries[0])
        data += ''.join(entries[1:])

    if len(data) % 32 != 0:
        raise Exception('Error decoding chunk IDs')

    return [ hexlify(data[i:i+32]) for i in range(0, len(data), 32) ]

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: %s <master index txid>' % sys.argv[0])
        sys.exit(1)

    master_index = get_tx_data_entries(sys.argv[1])

    if master_index[0][:len(MAGIC)] != MAGIC:
        raise Exception('Invalid Master File Index transaction ID')

    filename = master_index[1].rstrip('\0')
    file_sha1_size = hexlify(master_index[2])
    file_size = int(file_sha1_size[-16:], 16)
    file_sha1 = file_sha1_size[:40]
    file_sha256 = hexlify(master_index[3])
    index_chain_txid = hexlify(master_index[4])

    print("""
    Extracting:    %s
    File size:     %d bytes
    SHA1 digest:   %s
    SHA256 digest: %s
    Index chain:   %s
    """ % (master_index[1], file_size, file_sha1, file_sha256, index_chain_txid))

    print('Resolving indices...')
    chunks = load_chunks_ids_from_index_chain(index_chain_txid)
    print('File stored in %d chunks, extracting from chain...' % len(chunks))

    data = ''.join([ ''.join(get_tx_data_entries(txid)) for txid in chunks ])[:file_size]
    print('Extracted %d bytes' % len(data))

    if sha1(data).hexdigest() != file_sha1:
        raise Exception('Extracted file, but SHA1 digest does not match Master File Index')
    if sha256(data).hexdigest() != file_sha256:
        raise Exception('Extracted file, but SHA256 digest does not match Master File Index')

    print('File data verification OK, writing out...')
    with open(filename, 'wb') as f:
        f.write(data)

    print('Success!')
