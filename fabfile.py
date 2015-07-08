from fabric.api import run
from fabric.api import env

env.hosts = ['localhost', ]

def host_type():
    run('uname -s')
