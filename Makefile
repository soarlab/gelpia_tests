

all: bin/tester bin/dOp_wrapper bin/reverse_diff_tester

bin/reverse_diff_tester: src/*.py src/reverse_diff_tester.py
	cp src/*.py bin
	cp src/reverse_diff_tester.py bin/reverse_diff_tester
	chmod +x bin/reverse_diff_tester

bin/tester: src/tester.py src/*.py
	cp src/*.py bin
	cp src/tester.py bin/tester
	chmod +x bin/tester

bin/dOp_wrapper: src/dOp_wrapper.sh
	cp src/dOp_wrapper.sh bin/dOp_wrapper
	chmod +x bin/dOp_wrapper

.PHONY: test
test: test-max test-min

.PHONY: test-max
test-max: all
	./bin/tester ${TESTER_ARGS} --exe=../bin/dop_gelpia benchmarks/dop_format
	./bin/tester ${TESTER_ARGS} --exe=../bin/gelpia benchmarks/gelpia_format

.PHONY: test-min
test-min: all
	./bin/tester ${TESTER_ARGS} --exe=../bin/dop_gelpia --min benchmarks/dop_format
	./bin/tester ${TESTER_ARGS} --exe=../bin/gelpia --min benchmarks/gelpia_format


.PHONY: clean
clean:
	$(RM) -r bin/*
