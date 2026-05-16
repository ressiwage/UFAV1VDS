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
	 --reconfigure && cd build && ninja

david_trace:
	perf record -g --call-graph dwarf \
  	code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1; \
	perf report --stdio --no-children | head -60

david_callgrind:
	valgrind --tool=callgrind \
	--callgrind-out-file=callgrind.out \
	--collect-jumps=yes --cache-sim=yes --branch-sim=yes \
	code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1 ; \
	callgrind_annotate --auto=yes callgrind.out

vtune:
	sudo /opt/intel/oneapi/vtune/latest/bin64/vtune -collect hotspots -knob sampling-mode=sw -knob enable-stack-collection=true -- ./code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1
david_perfprof:
	sudo ~/.cargo/bin/samply record	code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1

david_perfproff:
    LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libprofiler.so \
    CPUPROFILE=prof.out \
    code/decoder/build/tools/dav1d -i code/tvav.obu --limit 1000 -o /dev/null --threads 1;

david_show:
	bash code/scripts/david_compare.sh code/tvav.obu

david_show_save:
	bash code/scripts/david_comp_save.sh code/tvav.obu

throughput_bench:
	python benchmarks/throughput/bench.py