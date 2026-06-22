import os
import sys
import ctypes
import socket

# 1. Load the compiled C library (connection.dll on Windows)
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connection.dll"))
if not os.path.exists(lib_path):
    print(f"Error: Could not find connection library at {lib_path}")
    print("Please compile it first using: gcc -shared -o connection.dll src/connection/infrastructure/tcp_connection.c -lws2_32")
    sys.exit(1)

connection_lib = ctypes.CDLL(lib_path)

# 2. Define argument and return types for the C functions
# In D, socket_t is intptr_t, which maps to ctypes.c_void_p or ctypes.c_ssize_t
socket_t_type = ctypes.c_ssize_t

connection_lib.connection_start_server.argtypes = [ctypes.c_int]
connection_lib.connection_start_server.restype = socket_t_type

connection_lib.connection_connect_to_server.argtypes = [ctypes.c_char_p, ctypes.c_int]
connection_lib.connection_connect_to_server.restype = socket_t_type

connection_lib.connection_close.argtypes = [socket_t_type]
connection_lib.connection_close.restype = None

PORT = 8080

def run_server():
    print(f"[Python Server] Starting C TCP server on port {PORT}...")
    
    # Call the C server function (blocks until a client connects)
    raw_socket_handle = connection_lib.connection_start_server(PORT)
    
    if raw_socket_handle == -1:
        print("[Python Server] Failed to start server.")
        return

    print(f"[Python Server] Client connected! Raw socket handle: {raw_socket_handle}")
    
    # Wrap the raw socket descriptor/handle into a Python socket object.
    # Python will manage sending and receiving using its standard library wrapper.
    try:
        py_socket = socket.socket(
            family=socket.AF_INET, 
            type=socket.SOCK_STREAM, 
            proto=socket.IPPROTO_TCP, 
            fileno=raw_socket_handle
        )
        
        # Receive raw data
        data = py_socket.recv(1024)
        print(f"[Python Server] Received raw data: {data}")
        
        # Send raw response
        response = b"Hello from Python Server via C Socket!"
        py_socket.sendall(response)
        print(f"[Python Server] Sent raw response: {response}")
    except Exception as e:
        print(f"[Python Server] Error occurred during communication: {e}")
    finally:
        # Close using the C function to cleanly release Winsock resources,
        # or Python socket's close() which internally closes the file descriptor/handle.
        print("[Python Server] Closing socket...")
        connection_lib.connection_close(raw_socket_handle)

def run_client(server_ip):
    print(f"[Python Client] Connecting to {server_ip}:{PORT} using C client...")
    
    # Call the C client function
    ip_bytes = server_ip.encode('utf-8')
    raw_socket_handle = connection_lib.connection_connect_to_server(ip_bytes, PORT)
    
    if raw_socket_handle == -1:
        print("[Python Client] Failed to connect to server.")
        return

    print(f"[Python Client] Connected! Raw socket handle: {raw_socket_handle}")
    
    # Wrap the raw socket descriptor/handle into a Python socket object
    try:
        py_socket = socket.socket(
            family=socket.AF_INET, 
            type=socket.SOCK_STREAM, 
            proto=socket.IPPROTO_TCP, 
            fileno=raw_socket_handle
        )
        
        # Send raw message
        message = b"Hello from Python Client!"
        py_socket.sendall(message)
        print(f"[Python Client] Sent raw data: {message}")
        
        # Receive response
        data = py_socket.recv(1024)
        print(f"[Python Client] Received response: {data}")
    except Exception as e:
        print(f"[Python Client] Error occurred during communication: {e}")
    finally:
        print("[Python Client] Closing socket...")
        connection_lib.connection_close(raw_socket_handle)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_ctypes.py server")
        print("  python test_ctypes.py client [server_ip]")
        sys.exit(1)
        
    mode = sys.argv[1].lower()
    if mode == "server":
        run_server()
    elif mode == "client":
        ip = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
        run_client(ip)
    else:
        print("Unknown mode. Use 'server' or 'client'.")
