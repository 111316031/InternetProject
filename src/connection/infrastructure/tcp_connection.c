#ifdef _WIN32
    #undef _WIN32_WINNT
    #define _WIN32_WINNT 0x0600
#endif
#include "../domain/connection_interface.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #ifdef _MSC_VER
        #pragma comment(lib, "ws2_32.lib")
    #endif
    
    // Internal helper to initialize Winsock automatically on Windows
    static int init_winsock(void) {
        static int initialized = 0;
        if (!initialized) {
            WSADATA wsa;
            if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
                fprintf(stderr, "[Connection] Error: WSAStartup failed.\n");
                return 0;
            }
            initialized = 1;
        }
        return 1;
    }
#else
    #include <sys/types.h>
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>

    #define SOCKET int
    #define INVALID_SOCKET (-1)
    #define SOCKET_ERROR (-1)
    #define closesocket close
    
    static int init_winsock(void) {
        return 1; // No-op on non-Windows platforms
    }
#endif

socket_t connection_start_server(int port) {
    if (!init_winsock()) {
        return INVALID_SOCKET_VAL;
    }

    if (port < 1 || port > 65535) {
        fprintf(stderr, "[Connection] Error: Invalid port number %d. Must be between 1 and 65535.\n", port);
        return INVALID_SOCKET_VAL;
    }

    SOCKET server_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server_fd == INVALID_SOCKET) {
        fprintf(stderr, "[Connection] Error: Failed to create socket.\n");
        return INVALID_SOCKET_VAL;
    }

    // Allow quick reuse of the port
    int opt = 1;
#ifdef _WIN32
    // On Windows, SO_REUSEADDR behaves slightly differently, but it's still useful.
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
#else
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#endif

    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons((uint16_t)port);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) == SOCKET_ERROR) {
        fprintf(stderr, "[Connection] Error: Bind failed.\n");
        closesocket(server_fd);
        return INVALID_SOCKET_VAL;
    }

    if (listen(server_fd, 1) == SOCKET_ERROR) {
        fprintf(stderr, "[Connection] Error: Listen failed.\n");
        closesocket(server_fd);
        return INVALID_SOCKET_VAL;
    }

    printf("[Connection] Server listening on port %d... Waiting for incoming connection...\n", port);

    struct sockaddr_in client_address;
    int client_addr_len = sizeof(client_address);
    SOCKET client_fd = accept(server_fd, (struct sockaddr*)&client_address, &client_addr_len);
    if (client_fd == INVALID_SOCKET) {
        fprintf(stderr, "[Connection] Error: Accept failed.\n");
        closesocket(server_fd);
        return INVALID_SOCKET_VAL;
    }

    // Get client IP address string
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_address.sin_addr, client_ip, INET_ADDRSTRLEN);
    printf("[Connection] Client connected from %s:%d\n", client_ip, ntohs(client_address.sin_port));

    // Close the listening socket as we only need the active connection
    closesocket(server_fd);

    return (socket_t)client_fd;
}

socket_t connection_connect_to_server(const char* ip, int port) {
    if (!init_winsock()) {
        return INVALID_SOCKET_VAL;
    }

    if (!ip) {
        fprintf(stderr, "[Connection] Error: IP address cannot be NULL.\n");
        return INVALID_SOCKET_VAL;
    }
    if (port < 1 || port > 65535) {
        fprintf(stderr, "[Connection] Error: Invalid port number %d.\n", port);
        return INVALID_SOCKET_VAL;
    }

    SOCKET sock_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock_fd == INVALID_SOCKET) {
        fprintf(stderr, "[Connection] Error: Failed to create socket.\n");
        return INVALID_SOCKET_VAL;
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons((uint16_t)port);

    // Convert IPv4 address from text to binary form
    if (inet_pton(AF_INET, ip, &serv_addr.sin_addr) <= 0) {
        fprintf(stderr, "[Connection] Error: Invalid address / Address not supported: %s\n", ip);
        closesocket(sock_fd);
        return INVALID_SOCKET_VAL;
    }

    printf("[Connection] Connecting to %s:%d...\n", ip, port);

    if (connect(sock_fd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == SOCKET_ERROR) {
        fprintf(stderr, "[Connection] Error: Connection failed.\n");
        closesocket(sock_fd);
        return INVALID_SOCKET_VAL;
    }

    printf("[Connection] Successfully connected to %s:%d\n", ip, port);
    return (socket_t)sock_fd;
}

void connection_close(socket_t sock) {
    if (sock != INVALID_SOCKET_VAL) {
#ifdef _WIN32
        closesocket((SOCKET)sock);
#else
        close((int)sock);
#endif
    }
}
