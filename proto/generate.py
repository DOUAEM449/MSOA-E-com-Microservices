"""Generate the Python gRPC stubs from proto/inventory.proto.

The generated files are written next to each service that uses the contract:
  services/inventory/inventory_pb2.py, inventory_pb2_grpc.py  (server)
  services/orders/inventory_pb2.py,    inventory_pb2_grpc.py  (client)

Usage (from the repository root):
  pip install grpcio-tools
  python proto/generate.py

Never edit the generated files by hand: change the .proto and run this again.
"""
from pathlib import Path

from grpc_tools import protoc

PROTO_DIR = Path(__file__).resolve().parent
ROOT = PROTO_DIR.parent
TARGETS = [ROOT / "services" / "inventory", ROOT / "services" / "orders"]


def main() -> None:
    for target in TARGETS:
        code = protoc.main([
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={target}",
            f"--grpc_python_out={target}",
            str(PROTO_DIR / "inventory.proto"),
        ])
        if code != 0:
            raise SystemExit(f"protoc failed for {target} (exit code {code})")
        print(f"generated stubs in {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
