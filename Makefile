help:
	echo 'david_{bench|build|rebuild|show}'
david_bench:
	sh benchmarks/decoder/dav1d.sh
david_bench_sm:
	sh benchmarks/decoder/dav1d_sm.sh
david_build:
	cd code/decoder && meson setup build -Denable_asm=false --buildtype=release && cd build && ninja
david_rebuild:
	cd code/decoder && meson setup build -Denable_asm=false \
	--buildtype=release --reconfigure && cd build && ninja

david_trace_build:
	cd code/decoder && meson setup build --buildtype=debugoptimized -Denable_asm=false \
	--buildtype=release --reconfigure && cd build && ninja

david_trace:
	perf record -g --call-graph dwarf \
  	code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1; \
	perf report --stdio --no-children | head -60

david_callgrind:
	valgrind --tool=callgrind \
	--callgrind-out-file=callgrind.out \
	--collect-jumps=yes \
	code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1 ; \
	callgrind_annotate --auto=yes callgrind.out


david_show:
	bash code/scripts/david_compare.sh code/tvav.obu