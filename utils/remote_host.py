from paramiko import SSHClient
import os

import config
from config import logger


def _get_ssh_client(host: str, user: str, key_path: str) -> SSHClient:
    logger.info(f'Connecting to server {host}.')
    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(hostname=host, username=user, key_filename=key_path)
    logger.info(f'Successfully connected to server {host}.')
    return ssh


def _get_ssh_key_path(remote_name: str) -> str:
    """
    Read path to SSH public kay from .env
    :param remote_name: name of a remote config section in the general config.
    :return: file system path to the SSH public key for remote server connecting.
    """
    env_var_name_with_path = config.general_config['remote'][remote_name]['path_to_ssh_var_name']
    ssh_path = os.getenv(env_var_name_with_path)
    if ssh_path.startswith('~'):
        ssh_path = os.path.expanduser(ssh_path)
    return ssh_path


def get_ssh_client(remote_name: str) -> SSHClient:
    remote_config = config.general_config['remote'][remote_name]
    ssh_path = _get_ssh_key_path(remote_name)

    return _get_ssh_client(host=remote_config['host'],
                           user=remote_config['user'],
                           key_path=ssh_path)


def exec_command(ssh: SSHClient, command: str) -> str:
    """
    Execute a shell command on a remote server.
    :param ssh: paramiko ssh client
    :param command: the command to execute
    :return: response string.
    """
    try:
        _, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        out = stdout.read()

        error = stderr.read()
        if len(error) > 0:
            raise SystemExit(error)

    except Exception as e:
        raise SystemExit(f"There was an issue with ssh command: {e}")
    finally:
        stdout.close()
        stderr.close()

    return out.decode('utf-8')


def sftp_put_callback(count: int, total: int) -> None:
    """
    Format callback to sys.stdout.
    :param count:
    :param total:
    :return:
    """
    from sys import stdout
    stdout.write("\rSending bytes: [{:8d}/{:8d} ({:3d}%)]".format(count, total, int(count * 100 / total)))
    stdout.flush()


def is_folder_empty(ssh: SSHClient, path: str) -> bool:
    cmd = f"""
        [ "$(ls -A {path})" ] && echo "Not Empty" || echo "Empty"
        """
    result = exec_command(ssh, command=cmd)
    logger.info(f'The {path} folder is {result.strip()}.')

    return result.strip() == 'Empty'


def is_folder_exists(ssh: SSHClient, path: str) -> bool:
    """
    :param ssh: SSH client
    :param path: remote path to check
    :return: True if the folder exists
    """
    cmd = f"""
    [ -d "{path}" ] && echo "Exists" || echo "Not Exists"
    """
    result = exec_command(ssh, command=cmd).rstrip("\n")
    logger.info(f'The {path} folder is {result.strip()}.')

    return result == 'Exists'