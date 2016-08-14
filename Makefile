

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
test: all
	./bin/tester --exe=dop_gelpia benchmarks/dop_format/hand_generated
	./bin/tester --exe=dop_gelpia --dreal benchmarks/dop_format/dreal_benchmarks
	./bin/tester --exe=gelpia benchmarks/gelpia_format/fptaylor_generated

.PHONY: test-dreal
test-dreal: all
	./bin/tester --exe=dOp_wrapper --dreal benchmarks/dop_format/dreal_benchmarks

.PHONY: clean
clean:
	$(RM) -r bin/*
