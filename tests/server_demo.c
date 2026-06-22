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

int main(void) {
    printf("[Server Demo] Initializing server...\n");

    socket_t client_sock = connection_start_server(PORT);
    if (client_sock == INVALID_SOCKET_VAL) {
        fprintf(stderr, "[Server Demo] Failed to start server and accept connection.\n");
        return 1;
    }

    printf("[Server Demo] Connection established! Waiting for raw data...\n");

    // Receive data
    char buffer[BUFFER_SIZE];
    memset(buffer, 0, BUFFER_SIZE);

    // Using standard recv on the raw socket descriptor
    int bytes_received = recv((SOCKET)client_sock, buffer, BUFFER_SIZE - 1, 0);
    if (bytes_received < 0) {
        perror("[Server Demo] recv failed");
    } else if (bytes_received == 0) {
        printf("[Server Demo] Client closed connection.\n");
    } else {
        printf("[Server Demo] Received %d bytes of raw data: \"%s\"\n", bytes_received, buffer);

        // Send a response back to client
        const char* msg = "Hello from TCP Server!";
        int bytes_sent = send((SOCKET)client_sock, msg, (int)strlen(msg), 0);
        if (bytes_sent < 0) {
            perror("[Server Demo] send failed");
        } else {
            printf("[Server Demo] Sent %d bytes response: \"%s\"\n", bytes_sent, msg);
        }
    }

    // Close the connection
    connection_close(client_sock);
    printf("[Server Demo] Connection closed. Demo finished.\n");

    return 0;
}
