import psutil

def get_free_disk():
    '''в байтах'''
    return psutil.disk_usage('/').free

def get_free_ram():
    '''в байтах'''
    return psutil.virtual_memory().available

def get_cpu_count() -> int:
    '''в штуках'''
    res = psutil.cpu_count(logical=True)
    if res is None:
        raise Exception("could not determine cpu count, set it manually")
    return res

def get_avg_load():
    '''in percents, [0;1]'''
    return (psutil.getloadavg()[0] * get_cpu_count()) / 100