PATH_38MB_MKV = 'code/tvav60.mkv'
PATH_476MB_MKV='code/tvav2.1.mkv'
PATH_909MB_MKV='code/tvav.mkv'

PATH_867_MB='code/tvav.obu'
PATH_434_MB='code/tvav2.1.obu'
PATH_37_MB='code/tvav60.obu'

ITEMS = [
    {'obu':PATH_867_MB, 'mkv':PATH_909MB_MKV},
    {'obu':PATH_434_MB, 'mkv':PATH_476MB_MKV},
    {'obu':PATH_37_MB, 'mkv':PATH_38MB_MKV}
]

GATEWAY_URL = 'http://72.56.39.104:8001'

import requests, os, random, time, threading

def upload_simple( file):
    global ACCESS
    file_status = requests.post(f"{GATEWAY_URL}/upload", files={'file':open(ITEMS[file]['mkv'], 'rb')}, headers={'accept': 'application/json'})
    return file_status.text

def upload_opt(file):
    global ACCESS
    url = requests.get(f"{GATEWAY_URL}/upload?neccessary_ram={os.path.getsize(ITEMS[file]['obu'])}", headers={'auth': f'Bearer {ACCESS}'})
    print(url.text)
    res = url.json()['url']
    file_status = requests.post(res, files={'file':open(ITEMS[file]['obu'], 'rb')}, headers={'accept': 'application/json'})
    return file_status.text
acc_req = requests.post(f"{GATEWAY_URL}/login", json={'username':'root', 'password':'root'})
print(acc_req, acc_req.text)
ACCESS = acc_req.json()['access_token']
rep=f'benchmarks/throughput/REPORT_{random.randint(100, 999)}.md'
print(f'saving in {rep}')
def sequential(out, file_index, upload_func):
    out.write(f"sequential bench, FI {file_index}, URL {GATEWAY_URL}\n")
    start_time,start_time_  = time.time(), time.time()
    failed = 0
    for i in range(50):
        try:
            out.write(f"{i}<:> {upload_func(file_index)[:500]}<:> {time.time() - start_time}\n\n")
        except Exception as e:
            failed+=1
            out.write(f"{i}<:> {e}<:> {time.time() - start_time}\n\n")

        start_time = time.time()
        out.flush()
    out.write(f'done in: {time.time() - start_time_}, failed: {failed}\n')

def parallel(out, file_index, upload_func, workers=50, iterations=50):
    out.write(f"parallel bench, FI {file_index}, URL {GATEWAY_URL}\n")
    start_time_ = time.time()
    failed = 0
    lock = threading.Lock()
    results = [None] * iterations

    def task(i):
        t = time.time()
        try:
            result = upload_func(file_index)[:500]
            results[i] = (i, result, time.time() - t)
        except Exception as e:
            results[i] = (i, str(e), time.time() - t, True)

    threads = []
    semaphore = threading.Semaphore(workers)

    def worker(i):
        with semaphore:
            task(i)
            print(i,'done')

    for i in range(iterations):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.5)

    for t in threads:
        t.join()

    for entry in results:
        if entry is None:
            continue
        is_error = len(entry) == 4 and entry[3]
        if is_error:
            failed += 1
        i, res, elapsed = entry[0], entry[1], entry[2]
        with lock:
            out.write(f"{i}<:> {res}<:> {elapsed}\n\n")

    out.write(f'done in: {time.time() - start_time_}, failed: {failed}\n')
    out.flush()

with open(rep, 'w+') as out:
    parallel(out, 2, upload_simple, iterations=2)    