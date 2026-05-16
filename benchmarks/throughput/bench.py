PATH_38MB_MKV = 'code/tvav.mkv'
PATH_476MB_MKV='code/tvav2.1.mkv'
PATH_909MB_MKV='code/tvav60.mkv'

PATH_867_MB='code/tvav.obu'
PATH_434_MB='code/tvav2.1.obu'
PATH_37_MB='code/tvav60.obu'

ITEMS = [
    {'obu':PATH_867_MB, 'mkv':PATH_909MB_MKV},
    {'obu':PATH_434_MB, 'mkv':PATH_476MB_MKV},
    {'obu':PATH_37_MB, 'mkv':PATH_38MB_MKV}
]

GATEWAY_URL = 'http://194.87.131.81:7995'

import requests, os, random, time

def upload_simple( file):
    global ACCESS
    pass

def upload_opt(file):
    global ACCESS
    url = requests.get(f"{GATEWAY_URL}/upload?neccessary_ram={os.path.getsize(ITEMS[file]['obu'])}", headers={'auth': f'Bearer {ACCESS}'})
    res = url.json()['url']
    print(res)
    file_status = requests.post(res, files={'file':open(ITEMS[file]['obu'], 'rb')}, headers={'accept': 'application/json'})
    print(file_status, file_status.text)
    return file_status.text

ACCESS = requests.post(f"{GATEWAY_URL}/login", json={'username':'root', 'password':'root'}).json()['access_token']
rep=f'benchmarks/throughput/REPORT_{random.randint(100, 999)}.md'
print(f'saving in {rep}')
with open(rep, 'w+') as out:
    start_time,start_time_  = time.time(), time.time()
    failed = 0
    for i in range(50):
        try:
            out.write(f"{i}<:> {upload_opt(1)}<:> {time.time() - start_time}\n\n")
        except Exception as e:
            failed+=1
            raise e
            out.write(f"{i}<:> {e}<:> {time.time() - start_time}\n\n")

        start_time = time.time()
        out.flush()
    out.write(f'done in: {time.time() - start_time_}, failed: {failed}\n')
