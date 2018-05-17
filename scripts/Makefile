SRC_PATH=..

all:

.PHONY: all check

include $(SRC_PATH)/config-host.mak

all:
	@echo "Use 'make check' to run the scripts' own unittests"

check:
	$(PYTHON) -m unittest discover -v .
