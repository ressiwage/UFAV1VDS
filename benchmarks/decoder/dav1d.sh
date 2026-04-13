

cat code/tvav.obu > /dev/null

hyperfine \
  --warmup 1 \
  --runs 3 \
  --export-json results.json \
  'code/decoder/build/tools/dav1d -i code/tvav.obu -o /dev/null --threads 1' 