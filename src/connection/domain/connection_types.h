#ifndef DOMAIN_CONNECTION_TYPES_H
#define DOMAIN_CONNECTION_TYPES_H

#include <stdint.h>

/**
 * @brief Abstract socket type to decouple Domain from specific OS dependencies in headers.
 * On Windows, SOCKET is UINT_PTR (64-bit on x64). On Unix, it is int (32-bit).
 * Using intptr_t ensures we can store both without truncation or warning.
 */
typedef intptr_t socket_t;

#define INVALID_SOCKET_VAL ((socket_t)-1)

#endif // DOMAIN_CONNECTION_TYPES_H
