TARGET = main

OBJS = Board.o main.o

CPLUSPLUS_VERSION = -std=c++17
WARN_FLAGS = -Werror -Wall -Wextra
CXXFLAGS = $(CPLUSPLUS_VERSION) $(WARN_FLAGS)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $^ -o $@

%.o: %.cc
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(TARGET) $(OBJS)
