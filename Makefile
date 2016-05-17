

all: bin/tester bin/dOp_wrapper


bin/tester: src/tester.py src/gelpia_test_support.py src/dop_test_support.py
	cp src/gelpia_test_support.py bin
	cp src/dop_test_support.py bin
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
