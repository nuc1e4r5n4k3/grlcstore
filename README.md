# GRLC-Store
A way to store arbitrary files on the Garlicoin blockchain

This repository contains 2 implementations to interact with arbitrary files stored on the Garlicoin (or I guess any bitcoin-compatible) blockchain.
Both implementations are very rudimentary and simplistic. Right now this is more of a proof of concept than anything else.

## Data storing method
This method writes data to the blockchain by generating transactions with a lot of outputs just above the dust limit.
This method is similar to burning coins: the transaction is valid, but there is probabilistically no way to redeem the coins,
hence they are probably lost forever. On top of this, you need to pay the normal transaction fees for the transactions themselves.

This all means that it is not cheap to store data: it requires about 12 GRLC per MiB. On the plus side, the data will be on the blockchain forever
and automatically be replicated by nodes all over the world.

The transaction outputs themselves are P2WSH outputs. SegWit's variant of regular pay-to-script-hash outputs.
This allows to store 32 bytes of data (as opposed to 20 bytes for P2PKH, P2WPKH and P2SH) per output, with 3 bytes overhead.
The minimal output amount for it to be not be treated as dust with this type of output is 0.00033 GRLC.

Transactions are generated with 1 (or more) inputs, 251 data/burn outputs and 1 change output.
This to keep below the 253 output limit that requires a change in the transaction output amount encoding,
which does seem to be handled incorrectly/not according to specification by at least some of the code.

This all means that one full transaction (also known as a _Chunk_) contains 8032 bytes of data,
is 10984 in total (2952 bytes overhead) and requires 0.093815 GRLC (0.010985 transaction fee and 0.08283 in burnt coins).

### Levels or storage and indexing
Files are stored in 3 steps:

 1. First, chunks are generated for raw data storage. No metadata is included at all.
 2. Next, the Index Chain is built. This is a chain of chunks that is filled with the chunk IDs (transaction IDs) of the data chunks, in the correct order
 3. Finally, the Master File Index is generated, which contains:
 * The `GRLCFILE` magic sequence.
 * The filename of the file that is stored.
 * The size of the file.
 * The SHA1 and SHA256 digests of the file data.
 * The ID of the first chunk of the Index Chain.

## The python implementation
The python implementation consists of 2 files: 

 - `grlcstore.py`
 - `grlcextract.py`
 
These are used to write files to and read files from the blockchain. Both are stand-alone and only use standard python libraries, except for a dependency [python-bitcoinrpc](https://github.com/jgarzik/python-bitcoinrpc).

Note that for the time being both files need to be edited to include Garlicoin Core RPC details.

### Garlicoin Core configuration
There are a couple of specific requirements regarding the Garlicoin Core configuration for the python code to work correctly.

#### Requirements for both storing and extracting files
* Configure RPC using the `rpcuser`, `rpcpassword` and `rpcport` options.

#### Additional requirements only used for storing files
* Enable the ability to spend unconfirmed transaction outputs using `spendzeroconfchange`.

#### Additional requirements only used for extracting files
* Enable transaction indexing using the `txindex` option (note that changing this requires a full blockchain redownload).

### Storing files
After editing `grlcstore.py` to include the correct Garlicoin Core RPC configuration, make sure you Garlicoin Core wallet is unlocked (for potentially a very long time) by using the `walletpassphrase` command (not required if you did not encrypt your wallet) and run:

`python grlcstore.py /file/to/store.ext`

This will start creating transactions to write out the file's data. Note that this can potentially take a very, very long time and there is currently no progress indicator.
Speed depends on the file's size, the size of the wallet (both in private keys as well as in UTXOs) and the performance of the machine itself.

Note that this action is not recoverable. It might be a good idea to try storing some small files or do some tests on the Garlicoin testnet before storing any large files to avoid loss of coins.

When to action completes, it will print out a Master File Index transaction ID. This is the ID under which your file is stored on the blockchain and is required in order to download it again.

### Extracting files from the blockchain
After you edited `grlcextract.py` to include the correct Garlicoin Core RPC configuration, you simply run:

`python grlcextract.py MASTER_FILE_INDEX_ID`

Note that this process is quite fast as it just reads data from your hard drive.


## The web client
In addition to the python store/extract implementation, there is also a web client that can only be used to download files from the chain.
This is a single, javascript-enabled webpage that depends on [Garlic Insight](https://garlicinsight.com/) to read data from the blockchain.

In order to use it, just simple host it somewhere, open a browser to it, paste in the Master File Index transaction ID and it will download the file and then ask you where to store it.

Note that a version of this is hosted on https://garlicfiledownload.freshgrlc.net/ .

