from fabric.api import run
from fabric.api import env
from fabric.api import prompt
from fabric.api import execute
from fabric.api import sudo
import boto.ec2
import time


env.hosts = ['localhost', ]
env.aws_region = 'us-west-2'
env.key_filename = '~/.ssh/pk-aws.pem'


def host_type():
    run('uname -s')


def get_ec2_connection():
    if 'ec2' not in env:
        conn = boto.ec2.connect_to_region(env.aws_region)
        if conn is not None:
            env.ec2 = conn
            print "Connected to EC2 region %s" % env.aws_region
        else:
            msg = "Unable to connect to EC2 region %s"
            raise IOError(msg % env.aws_region)
    return env.ec2


def provision_instance(wait_for_running=False, timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    conn = get_ec2_connection()
    instance_type = 't1.micro'
    key_name = 'pk-aws'
    security_group = 'ssh-access'
    image_id = 'ami-d0d8b8e0'

    reservations = conn.run_instances(
        image_id,
        key_name=key_name,
        instance_type=instance_type,
        security_groups=[security_group, ]
    )
    new_instances = [i for i in reservations.instances if i.state == u'pending']
    running_instance = []
    if wait_for_running:
        waited = 0
        while new_instances and (waited < timeout_val):
            time.sleep(wait_val)
            waited += (wait_val)
            for instance in new_instances:
                state = instance.state
                print "Instance %s is %s" % (instance.id, state)
                if state == "running":
                    running_instance.append(
                        new_instances.pop(new_instances.index(i))
                    )
                instance.update()


def stop_instance(wait_for_stopped=True, timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    select_instance(state='running')
    instance = env.active_instance
    instance.stop()

    stopped_instances = []
    stopping_instances = [instance]
    if wait_for_stopped:
        waited = 0
        while stopping_instances and (waited < timeout_val):
            time.sleep(wait_val)
            waited += (wait_val)
            for instance in stopping_instances:
                state = instance.state
                print "Instance %s is %s" % (instance.id, state)
                if state == "stopped":
                    stopped_instances.append(
                        stopping_instances.pop()
                    )
                instance.update()


def terminate_instance(wait_for_change=True, timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    select_instance(state='stopped')
    instance = env.active_instance
    instance.terminate()

    terminated_instances = []
    terminating_instances = [instance]
    if wait_for_change:
        waited = 0
        while terminating_instances and (waited < timeout_val):
            time.sleep(wait_val)
            waited += (wait_val)
            for instance in terminating_instances:
                state = instance.state
                print "Instance %s is %s" % (instance.id, state)
                if state == "terminated":
                    terminated_instances.append(
                        terminating_instances.pop()
                    )
                instance.update()


def list_aws_instances(verbose=False, state='all'):
    conn = get_ec2_connection()

    reservations = conn.get_all_reservations()
    instances = []
    for res in reservations:
        for instance in res.instances:
            if state == 'all' or instance.state == state:
                instance = {
                    'id': instance.id,
                    'type': instance.instance_type,
                    'image': instance.image_id,
                    'state': instance.state,
                    'instance': instance,
                }
                instances.append(instance)
    env.instances = instances
    if verbose:
        import pprint
        pprint.pprint(env.instances)


def select_instance(state='all'):
    if env.get('active_instance', False):
        return

    list_aws_instances(state=state)

    prompt_text = "Please select from the following instances:\n"
    instance_template = " %(ct)d: %(state)s instance %(id)s\n"
    for idx, instance in enumerate(env.instances):
        ct = idx + 1
        args = {'ct': ct}
        args.update(instance)
        prompt_text += instance_template % args
    prompt_text += "Choose an instance: "

    def validation(input):
        choice = int(input)
        if choice not in range(1, len(env.instances) + 1):
            raise ValueError("%d is not a valid instance" % choice)
        return choice

    choice = prompt(prompt_text, validate=validation)
    env.active_instance = env.instances[choice - 1]['instance']


def run_command_on_selected_server(command):
    select_instance()
    selected_hosts = [
        'ubuntu@' + env.active_instance.public_dns_name
    ]
    execute(command, hosts=selected_hosts)


def _install_nginx():
    sudo('apt-get update')
    sudo('apt-get install nginx')
    sudo('/etc/init.d/nginx start')


def install_nginx():
    run_command_on_selected_server(_install_nginx)
