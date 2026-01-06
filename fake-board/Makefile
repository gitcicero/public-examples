TARGET = main

OBJS = Board.o main.o

CPLUSPLUS_VERSION ?= -std=c++17

ifeq ($(strip $(WARN_EVERYTHING)),)
WARN_FLAGS = -Werror -Wall -Wextra
else
# Best practice is not to use -Weverything, but this may expose issues worth fixing.
WARN_FLAGS = -Werror -Weverything -Wno-c++98-compat -Wno-poison-system-directories \
-Wno-padded -Wno-weak-vtables
endif
CXXFLAGS = $(CPLUSPLUS_VERSION) $(WARN_FLAGS)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $^ -o $@

%.o: %.cc
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(TARGET) $(OBJS)
