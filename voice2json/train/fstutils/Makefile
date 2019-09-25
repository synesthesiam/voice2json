CPPFLAGS:=$(CFLAGS) -lfst -g -Wall -ldl --std=c++11

all: fstprint-all fstcount-all

%: %.cc
	$(CXX) $< $(CPPFLAGS) $(LDFLAGS) -o $@
