import os
import ctypes
import socket

# Find the DLL path relative to this file
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# The DLL should be in the project root directory
_DLL_PATH = os.path.abspath(os.path.join(_CURRENT_DIR, "..", "..", "connection.dll"))

# Load library and configure signatures
try:
    _lib = ctypes.CDLL(_DLL_PATH)
except OSError as e:
    raise OSError(
        f"Could not load C connection library at: {_DLL_PATH}\n"
        "Please build it first by running:\n"
        "gcc -shared -Wall -Wextra -o connection.dll src/connection/infrastructure/tcp_connection.c -lws2_32"
    ) from e

# Define types (socket_t is intptr_t -> c_ssize_t)
_socket_t = ctypes.c_ssize_t

_lib.connection_start_server.argtypes = [ctypes.c_int]
_lib.connection_start_server.restype = _socket_t

_lib.connection_connect_to_server.argtypes = [ctypes.c_char_p, ctypes.c_int]
_lib.connection_connect_to_server.restype = _socket_t

_lib.connection_close.argtypes = [_socket_t]
_lib.connection_close.restype = None


def start_server(port: int) -> socket.socket:
    """
    Starts a TCP server using the C socket library and blocks waiting for a client.
    Returns a native Python socket.socket object wrapping the connected socket.
    """
    raw_handle = _lib.connection_start_server(port)
    if raw_handle == -1:
        raise OSError("C connection_start_server failed to start or accept client.")
        
    return socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
        fileno=raw_handle
    )


def connect_to_server(ip: str, port: int) -> socket.socket:
    """
    Connects to a TCP server using the C socket library.
    Returns a native Python socket.socket object wrapping the connected socket.
    """
    ip_bytes = ip.encode('utf-8')
    raw_handle = _lib.connection_connect_to_server(ip_bytes, port)
    if raw_handle == -1:
        raise OSError(f"C connection_connect_to_server failed to connect to {ip}:{port}.")
        
    return socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
        fileno=raw_handle
    )


def close_socket(sock: socket.socket) -> None:
    """
    Detaches the socket from Python's socket object and closes it cleanly using the C library.
    This prevents double-close errors by releasing Python's ownership of the descriptor.
    """
    try:
        # Retrieve the raw file descriptor and release Python ownership
        fd = sock.detach()
        if fd != -1:
            _lib.connection_close(fd)
    except Exception:
        # If already closed or detached, ignore
        pass
