import sys

from binascii import hexlify, unhexlify
from hashlib import sha1, sha256
from os import path
from time import sleep

from jsonrpc.authproxy import AuthServiceProxy, JSONRPCException


RPCUSER = 'MY_GARLICOIN_CORE_RPC_USERNAME'
RPCPASSWORD = 'MY_GARLICOIN_CORE_RPC_PASSWORD'
RPCPORT = 42068


MAGIC = 'GRLCFILE'

BLOCKSIZE = 32
CHUNKSIZE = BLOCKSIZE * 0xfb

FEE = 0.001
BURN_SATS = 33000

__LAST_ID__ = '0000000000000000000000000000000000000000000000000000000000000000'

rpcproxy = None

def get_rpc_proxy():
    global rpcproxy
    if rpcproxy == None:
        rpcproxy = AuthServiceProxy('http://%s:%s@localhost:%d/' % (RPCUSER, RPCPASSWORD, RPCPORT))
    return rpcproxy

class Transaction(object):
    VERSION = '02000000'
    INPUTS = '00'
    COINS_OUT = '%02x%02x000000000000' % (BURN_SATS % 0x100, BURN_SATS / 0x100)
    SW_V0 = '00'
    FOOTER = '00000000'

    def __init__(self, data_outputs):
        self.unsigned = None
        self.signed = None
        self.id = None
        self.generate(data_outputs)

    def generate(self, data_outputs):
        if len(data_outputs) >= 0xfd:
            outputs = 'fd' + '%02x%02x' % (len(data_outputs) % 0x100, len(data_outputs) / 0x100)
        else:
            outputs = '%02x' % len(data_outputs)

        self.template = self.VERSION + self.INPUTS + outputs
        for output in data_outputs:
            data_len = len(output)
            self.template += self.COINS_OUT
            self.template += '%02X' % (data_len + 2)
            self.template += self.SW_V0
            self.template += '%02X' % data_len + hexlify(output)
        self.template += self.FOOTER

    def fund(self):
        self.unsigned = get_rpc_proxy().fundrawtransaction(self.template, { 'feeRate': FEE })['hex']

    def sign(self):
        self.signed = get_rpc_proxy().signrawtransaction(self.unsigned)['hex']

    def broadcast(self):
        self.id = get_rpc_proxy().sendrawtransaction(self.signed)

class Chunk(object):
    def __init__(self, data=None):
        self.outputs = []
        self._tx = None
        if data != None:
            for block in [ data[i:i + BLOCKSIZE] for i in range(0, len(data), BLOCKSIZE) ]:
                self.append(block)

    def prepend(self, block):
        self.outputs.insert(0, (block + '\0' * BLOCKSIZE)[:BLOCKSIZE])

    def append(self, block):
        self.outputs.append((block + '\0' * BLOCKSIZE)[:BLOCKSIZE])

    def blocks(self):
        return self.outputs

    def raw(self):
        return ''.join(self.outputs)

    def store(self):
        if self._tx == None:
            self._tx = Transaction(self.outputs)
            sent = False
            while not sent:
                try:
                    self._tx.fund()
                    self._tx.sign()
                    self._tx.broadcast()
                    sent = True
                except JSONRPCException as e:
                    print(e.error)
                    print('Error trying to create, sign or send out transaction, waiting 20 seconds before retrying')
                    sleep(20)
                    print('Retrying...')
        return self._tx.id

class Blob(object):
    def __init__(self, data):
        self.data = data
        self._chunks = None

    def as_chunks(self):
        if self._chunks == None:
            self._chunks = self.encode()
        return self._chunks

class ChainedBlob(Blob):
    def encode(self):
        return [ Chunk(self.data[i:i + CHUNKSIZE - BLOCKSIZE]) for i in range(0, len(self.data), CHUNKSIZE - BLOCKSIZE) ]

    def store(self):
        last_id = __LAST_ID__
        for chunk in reversed(self.as_chunks()):
            chunk.prepend(unhexlify(last_id))
            last_id = chunk.store()
        return last_id

class IndexedBlob(Blob):
    def encode(self):
        return [ Chunk(self.data[i:i + CHUNKSIZE]) for i in range(0, len(self.data), CHUNKSIZE) ]

    def store(self):
        print('Writing out data, %d chunks at %d bytes per chunk...' % (len(self.as_chunks()), CHUNKSIZE))
        chunk_ids = [ chunk.store() for chunk in self.as_chunks() ]
        index_data = ChainedBlob(''.join([ unhexlify(id) for id in chunk_ids ]))
        print('Writing out %d indexes...' % len(index_data.as_chunks()))
        return index_data.store()

class ChainFile(object):
    def __init__(self, data, name='unnamed'):
        self.blob = IndexedBlob(data)
        self.name = name
        self.size = len(data)
        self.hash20 = sha1(data).digest()
        self.hash32 = sha256(data).digest()

    def store(self):
        first_index_chunk_id = self.blob.store()
        chunk = Chunk()
        chunk.append(MAGIC)
        chunk.append(self.name)
        chunk.append(self.hash20 + '\0' * (BLOCKSIZE - 28) + unhexlify('%016x' % self.size))
        chunk.append(self.hash32)
        chunk.append(unhexlify(first_index_chunk_id))
        return chunk.store()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: %s <file>' % sys.argv[0])
        sys.exit(1)
    with open(sys.argv[1], 'rb') as file:
        blob = ChainFile(file.read(), name=sys.argv[1].split(path.sep)[-1])
        txid = blob.store()
        print('Stored on chain. File Master Index transaction ID: %s' % txid)
