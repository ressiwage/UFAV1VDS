emcc ff_transcode.c \
    -I$(pwd)/wasm-build/include \
    -L$(pwd)/wasm-build/lib\
   -fPIC -lavformat \
   -sASSERTIONS -s'EXPORTED_RUNTIME_METHODS=["callMain", "FS"]' -lavcodec \
    -lavutil \
    -s WASM=1 \
    -g -O3 \
    -o output.js