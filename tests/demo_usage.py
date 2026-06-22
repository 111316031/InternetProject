import sys
from src.connection import connection

PORT = 8080

def run_server():
    print("[Demo Server] Waiting for connection on port 8080...")
    # This calls C code in the background, blocks until a connection is accepted,
    # and returns a standard Python socket.socket object
    client_socket = connection.start_server(PORT)
    
    print("[Demo Server] Client connected successfully!")
    
    # Standard Python socket operations
    data = client_socket.recv(1024)
    print(f"[Demo Server] Received data: {data.decode('utf-8')}")
    
    client_socket.sendall(b"Hello from Python Server wrapper!")
    
    # Use the connection module's close_socket helper to cleanly release C socket
    connection.close_socket(client_socket)
    print("[Demo Server] Closed client socket.")

def run_client(ip):
    print(f"[Demo Client] Connecting to {ip}:{PORT}...")
    # This calls C code to connect to the server, and returns a standard Python socket.socket object
    server_socket = connection.connect_to_server(ip, PORT)
    
    print("[Demo Client] Connected to server successfully!")
    
    # Standard Python socket operations
    server_socket.sendall(b"Hello from Python Client wrapper!")
    
    response = server_socket.recv(1024)
    print(f"[Demo Client] Received response: {response.decode('utf-8')}")
    
    # Use the connection module's close_socket helper to cleanly release C socket
    connection.close_socket(server_socket)
    print("[Demo Client] Closed server socket.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m tests.demo_usage server")
        print("  python -m tests.demo_usage client [server_ip]")
        sys.exit(1)
        
    mode = sys.argv[1].lower()
    if mode == "server":
        run_server()
    elif mode == "client":
        ip = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
        run_client(ip)
