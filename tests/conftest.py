import os
import sys
import types
import web3


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if not hasattr(web3, "WebsocketProvider") and hasattr(web3, "WebSocketProvider"):
    web3.WebsocketProvider = web3.WebSocketProvider
if not hasattr(web3.Web3, "toChecksumAddress") and hasattr(web3.Web3, "to_checksum_address"):
    web3.Web3.toChecksumAddress = staticmethod(web3.Web3.to_checksum_address)
if not hasattr(web3.Web3, "isChecksumAddress") and hasattr(web3.Web3, "is_checksum_address"):
    web3.Web3.isChecksumAddress = staticmethod(web3.Web3.is_checksum_address)
if not hasattr(web3.Web3, "toWei") and hasattr(web3.Web3, "to_wei"):
    web3.Web3.toWei = staticmethod(web3.Web3.to_wei)
if not hasattr(web3.Web3, "fromWei") and hasattr(web3.Web3, "from_wei"):
    web3.Web3.fromWei = staticmethod(web3.Web3.from_wei)


if "backoff" not in sys.modules:
    def _passthrough_decorator(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap

    sys.modules["backoff"] = types.SimpleNamespace(
        on_exception=_passthrough_decorator,
        expo=lambda *args, **kwargs: None,
    )


if "pika" not in sys.modules:
    sys.modules["pika"] = types.SimpleNamespace(BlockingConnection=object)


if "leveldb" not in sys.modules:
    sys.modules["leveldb"] = types.SimpleNamespace(LevelDB=object)
