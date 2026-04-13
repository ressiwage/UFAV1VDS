help:
	echo 'david_{bench|build|rebuild|show}'
david_bench:
	sh benchmarks/decoder/dav1d.sh
david_build:
	cd code/decoder && meson setup build -Denable_asm=false --buildtype=release && cd build && ninja
david_rebuild:
	cd code/decoder && meson setup build -Denable_asm=false \
	--buildtype=release --reconfigure && cd build && ninja
david_show:
	bash code/scripts/david_compare.sh code/tvav.obu