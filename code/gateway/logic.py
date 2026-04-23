from config import CPU_THRESHOLD, RAM_THRESHOLD

def server_rank_key(server):
    cpu = server['cpu']
    ram = server['ram']
    sid = server['id']
    
    cpu_score = cpu if cpu < CPU_THRESHOLD else 1
    ram_score = -ram if ram > RAM_THRESHOLD else 1
    
    return (cpu_score, ram_score, sid)
 