import fcntl
import subprocess

proc = subprocess.Popen(["dav1d", "-i", 'tvav.obu', "-o", "-"],
                        stdout=subprocess.PIPE)

fd = proc.stdout.fileno()

# Проверить текущий размер
current = fcntl.fcntl(fd, 1032)  # F_GETPIPE_SZ = 1032
print(f"pipe buffer: {current}")  # обычно 65536

# Установить максимум
# /proc/sys/fs/pipe-max-size — системный максимум (обычно 1MB)
fcntl.fcntl(fd, 1031, 1_048_576)  # F_SETPIPE_SZ = 1031

# Проверить что применилось (ядро может дать меньше)
actual = fcntl.fcntl(fd, 1032)
print(f"actual pipe buffer: {actual}")
proc.kill()