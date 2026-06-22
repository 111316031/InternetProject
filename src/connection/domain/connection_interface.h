#ifndef DOMAIN_CONNECTION_INTERFACE_H
#define DOMAIN_CONNECTION_INTERFACE_H

#include "connection_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Starts a TCP server and blocks waiting for a client to connect.
 * @param port The port to listen on.
 * @return The connected raw socket, or INVALID_SOCKET_VAL on failure.
 */
socket_t connection_start_server(int port);

/**
 * @brief Connects to a TCP server at the given IP and port.
 * @param ip The server IP address (e.g. "127.0.0.1" or IPv6 address).
 * @param port The server port.
 * @return The connected raw socket, or INVALID_SOCKET_VAL on failure.
 */
socket_t connection_connect_to_server(const char* ip, int port);

/**
 * @brief Closes a socket connection.
 * @param sock The socket to close.
 */
void connection_close(socket_t sock);

#ifdef __cplusplus
}
#endif

#endif // DOMAIN_CONNECTION_INTERFACE_H
