# Detect Operating System
ifeq ($(OS),Windows_NT)
    TARGET = connection.dll
    LDFLAGS = -lws2_32
    RM = del /f /q
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        TARGET = connection.dylib
    else
        TARGET = connection.so
    endif
    LDFLAGS =
    CFLAGS += -fPIC
    RM = rm -f
endif

CC = gcc
CFLAGS += -Wall -Wextra -shared

SRC = src/connection/infrastructure/tcp_connection.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	$(RM) $(TARGET)
