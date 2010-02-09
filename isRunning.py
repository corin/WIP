import os
from time import time

f = "/usr/local/lib/weather/do_not_touch"

if os.path.exists(f):
    if os.stat(f).st_mtime < (time() - 1200):
        print "Hung."
