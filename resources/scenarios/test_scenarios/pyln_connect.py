#!/usr/bin/env python3

from io import BytesIO

from commander import Commander
from pyln.proto.message import Message, MessageNamespace
from pyln.proto.wire import PrivateKey, PublicKey, connect


class PyLNConnect(Commander):
    def set_test_params(self):
        self.num_nodes = 0

    def run_test(self):
        ln = self.lns["tank-0000-ln"]
        ln.createrune()
        uri = ln.uri()
        pk, host = uri.split("@")
        host, port = host.split(":")

        ls_privkey = PrivateKey(
            bytes.fromhex("1111111111111111111111111111111111111111111111111111111111111111")
        )
        remote_pubkey = PublicKey(bytes.fromhex(pk))

        lc = connect(ls_privkey, remote_pubkey, host, port)

        # Send an init message, with no global features, and 0b10101010 as local
        # features.
        # From BOLT1:
        #   type: 16 (init)
        #   data:
        #       [u16:gflen]
        #       [gflen*byte:globalfeatures]
        #       [u16:flen]
        #       [flen*byte:features]
        #       [init_tlvs:tlvs]
        lc.send_message(b"\x00\x10\x00\x00\x00\x01\xaa")

        # Import the BOLT#1 init message namesapce
        ns = MessageNamespace(
            [
                "msgtype,init,16",
                "msgdata,init,gflen,u16,",
                "msgdata,init,globalfeatures,byte,gflen",
                "msgdata,init,flen,u16,",
                "msgdata,init,features,byte,flen",
            ]
        )
        # read reply from peer
        msg = lc.read_message()
        self.log.info(f"Got message bytes: {msg.hex()}")
        # interpret reply from peer
        stream = BytesIO(msg)
        msg = Message.read(ns, stream)
        self.log.info(f"Decoded message type: {msg.messagetype} content: {msg.to_py()}")


def main():
    PyLNConnect().main()


if __name__ == "__main__":
    main()
