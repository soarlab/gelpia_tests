

all: bin/tester


bin/tester: src/tester.py
	cp src/tester.py bin/tester
	chmod +x bin/tester


.PHONY: test
test: all
	./bin/tester --exe=dop_gelpia benchmarks/dop_benchmarks
	./bin/tester --exe=dop_gelpia --dreal benchmarks/dreal_dop_benchmarks
	./bin/tester --exe=gelpia benchmarks/fptaylor_generated

.PHONY: clean
clean:
	$(RM) bin/*
