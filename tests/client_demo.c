#include "../src/connection/domain/connection_interface.h"
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
    #include <winsock2.h>
#else
    #include <sys/socket.h>
    #include <unistd.h>
    typedef int SOCKET;
#endif

#define PORT 8080
#define BUFFER_SIZE 1024

int main(int argc, char* argv[]) {
    char ip[100];
    if (argc > 1) {
        strncpy(ip, argv[1], sizeof(ip) - 1);
        ip[sizeof(ip) - 1] = '\0';
    } else {
        printf("Please enter Server IP: ");
        if (fgets(ip, sizeof(ip), stdin) == NULL) {
            fprintf(stderr, "Failed to read IP address.\n");
            return 1;
        }
        // Remove trailing newline character
        size_t len = strlen(ip);
        if (len > 0 && ip[len - 1] == '\n') {
            ip[len - 1] = '\0';
        }
    }

    printf("[Client Demo] Connecting to server %s on port %d...\n", ip, PORT);

    socket_t client_sock = connection_connect_to_server(ip, PORT);
    if (client_sock == INVALID_SOCKET_VAL) {
        fprintf(stderr, "[Client Demo] Connection failed.\n");
        return 1;
    }

    printf("[Client Demo] Connected successfully! Sending data...\n");

    const char* msg = "Hello, this is client message!";
    int bytes_sent = send((SOCKET)client_sock, msg, (int)strlen(msg), 0);
    if (bytes_sent < 0) {
        perror("[Client Demo] send failed");
    } else {
        printf("[Client Demo] Sent %d bytes of raw data: \"%s\"\n", bytes_sent, msg);
    }

    // Wait for response
    char buffer[BUFFER_SIZE];
    memset(buffer, 0, BUFFER_SIZE);
    int bytes_received = recv((SOCKET)client_sock, buffer, BUFFER_SIZE - 1, 0);
    if (bytes_received < 0) {
        perror("[Client Demo] recv failed");
    } else if (bytes_received == 0) {
        printf("[Client Demo] Server closed connection.\n");
    } else {
        printf("[Client Demo] Received response from server: \"%s\"\n", buffer);
    }

    connection_close(client_sock);
    printf("[Client Demo] Connection closed. Demo finished.\n");

    return 0;
}
