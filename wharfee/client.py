#!/usr/bin/env python
# -*- coding: utf-8
import sys
import pretty
import re
import pexpect

from docker import APIClient as DockerAPIClient
from docker.utils import kwargs_from_env
from docker.errors import APIError
from docker.errors import DockerException, InvalidVersion
from requests.exceptions import ConnectionError
from requests.packages.urllib3 import disable_warnings
from .options import allowed_args
from .options import parse_command_options
from .options import format_command_help, format_command_line
from .options import COMMAND_NAMES, split_command_and_args
from .options import OptionError
from .helpers import filesize, parse_port_bindings, parse_volume_bindings, \
    parse_exposed_ports, parse_kv_as_dict
from .utils import shlex_split
from .decorators import if_exception_return


class DockerClient(object):
    """
    This client is a "translator" between docker-py API and
    the standard docker command line. We need one because docker-py
    does not use the same naming for command names and their parameters.
    For example, "docker ps" is named "containers", "-n" parameter
    is named "limit", some parameters are not implemented at all, etc.
    """

    def __init__(self, timeout=None, clear_handler=None, refresh_handler=None, logger=None):
        """
        Initialize the Docker wrapper.
        :param timeout: int
        :param clear_handler: callable
        :param refresh_handler: callable
        :param logger: logger
        """

        assert callable(clear_handler)
        assert callable(refresh_handler)

        self.logger = logger
        self.exception = None

        self.handlers = {
            'attach': (self.attach, 'Attach to a running container.'),
            'build': (self.build, ("Build a new image from the source"
                                   " code")),
            'clear': (clear_handler, "Clear the window."),
            'create': (self.create, 'Create a new container.'),
            'exec': (self.execute, ("Run a command in a running"
                                    " container.")),
            'help': (self.help, "Help on available commands."),
            'pause': (self.pause, "Pause all processes within a container."),
            'ps': (self.containers, "List containers."),
            'port': (self.port, ("List port mappings for the container, or "
                                 "lookup the public-facing port that is "
                                 "NAT-ed to the private_port.")),
            'pull': (self.pull, ("Pull an image or a repository from the "
                                 "registry.")),
            'push': (self.push, ("Push an image or a repository to the "
                                 "registry.")),
            'images': (self.images, "List images."),
            'info': (self.info, "Display system-wide information."),
            'inspect': (self.inspect, "Return low-level information on a " +
                        "container or image."),
            'kill': (self.kill, "Kill one or more running containers"),
            'login': (self.login, ("Register or log in to a Docker registry "
                                   "server (defaut "
                                   "\"https://index.docker.io/v1/\").")),
            'logs': (self.logs, "Fetch the logs of a container."),
            'refresh': (refresh_handler, "Refresh autocompletions."),
            'rename': (self.rename, "Rename a container."),
            'restart': (self.restart, "Restart a running container."),
            'run': (self.run, "Run a command in a new container."),
            'rm': (self.rm, "Remove one or more containers."),
            'rmi': (self.rmi, "Remove one or more images."),
            'search': (self.search, "Search the Docker Hub for images."),
            'shell': (self.shell, "Get shell into a running container."),
            'start': (self.start, "Restart a stopped container."),
            'stop': (self.stop, "Stop a running container."),
            'tag': (self.tag, "Tag an image into a repository."),
            'top': (self.top, "Display the running processes of a container."),
            'unpause': (self.unpause, ("Unpause all processes within a "
                                       "container.")),
            'version': (self.version, "Show the Docker version information."),
            'volume create': (self.volume_create, "Create a new volume."),
            'volume inspect': (self.volume_inspect, "Inspect one or more "
                               "volumes."),
            'volume ls': (self.volume_ls, "List volumes."),
            'volume rm': (self.volume_rm, "Remove a volume."),
        }

        self.output = None
        self.after = None
        self.command = None
        self.log = None

        self.is_refresh_containers = False
        self.is_refresh_running = False
        self.is_refresh_images = False
        self.is_refresh_volumes = False

        disable_warnings()

        if sys.platform.startswith('darwin') \
                or sys.platform.startswith('win32'):
            try:
                # mac or win
                kwargs = kwargs_from_env()
                # hack from here:
                # http://docker-py.readthedocs.org/en/latest/boot2docker/
                # See also: https://github.com/docker/docker-py/issues/406
                if 'tls' in kwargs:
                    kwargs['tls'].assert_hostname = False
                kwargs['timeout'] = timeout
                self.instance = DockerAPIClient(**kwargs)

            except DockerException as x:
                if 'CERTIFICATE_VERIFY_FAILED' in str(x):
                    raise DockerSslException(x)
                elif 'ConnectTimeoutError' in str(x):
                    raise DockerTimeoutException(x)
                else:
                    raise x
        else:
            # unix-based
            kwargs = kwargs_from_env()
            kwargs['timeout'] = timeout
            self.instance = DockerAPIClient(**kwargs)

    def debug(self, message):
        """Log a debug message if logger is passed in."""
        if self.logger is not None:
            self.logger.debug(message)

    def handle_input(self, text):
        """
        Parse the command, run it via the client, and return
        some iterable output to print out. This will parse options
        and arguments out of the command line and into parameters
        consistent with docker-py naming. It is designed to be the
        only really public method of the client. Other methods
        are just pass-through methods that delegate commands
        to docker-py.
        :param text: user input
        :return: iterable
        """

        def reset_output():
            """ Set all internals to initial state."""
            self.command = None
            self.is_refresh_containers = False
            self.is_refresh_running = False
            self.is_refresh_images = False
            self.is_refresh_volumes = False
            self.after = None
            self.log = None
            self.exception = None

        tokens = shlex_split(text) if text else ['']
        cmd, params = split_command_and_args(tokens)

        reset_output()

        if cmd and cmd in self.handlers:
            handler = self.handlers[cmd][0]
            self.command = cmd

            if params:
                try:
                    if '-h' in tokens or '--help' in tokens:
                        self.output = [format_command_help(cmd)]
                    else:
                        parser, popts, pargs = parse_command_options(
                            cmd, params)
                        if 'help' in popts:
                            del popts['help']

                        self.output = handler(*pargs, **popts)

                except APIError as ex:
                    reset_output()
                    self.output = [str(ex.explanation)]

                except OptionError as ex:
                    reset_output()
                    raise ex

                except Exception as ex:
                    reset_output()
                    self.output = [ex.__repr__()]
            else:
                self.output = handler()
        elif cmd:
            self.output = self.help()

    def attach(self, *args, **kwargs):
        """
        Attach to a running container.
        :param kwargs:
        :return: None
        """
        if not args:
            return ['Container name or ID is required.']

        container = args[0]

        def on_after():
            pass

        self.after = on_after

        command = format_command_line('attach', False, args, kwargs)
        process = pexpect.spawnu(command)
        process.interact()

    def help(self, *_):
        """
        Collect and return help docstrings for all commands.
        :return: list of tuples
        """

        help_rows = [(key, self.handlers[key][1])
                     for key in COMMAND_NAMES]
        return help_rows

    def not_implemented(self, *_, **kw):
        """
        Placeholder for commands to be implemented.
        :return: iterable
        """
        pass

    def version(self, *_):
        """
        Return the version. Equivalent of docker version.
        :return: list of tuples
        """
        pass

    def info(self, *_):
        """
        Return the system info. Equivalent of docker info.
        :return: list of tuples
        """
        pass

    def inspect(self, *args, **_):
        """
        Return image or container info. Equivalent of docker inspect.
        :return: dict
        """
        pass

    def containers(self, *_, **kwargs):
        """
        Return the list of containers. Equivalent of docker ps.
        :return: list of dicts
        """

        # Truncate by default.
        if 'trunc' in kwargs and kwargs['trunc'] is None:
            kwargs['trunc'] = True

        def format_names(names):
            """
            Container names start with /.
            Let's strip this for readability.
            """
            if isinstance(names, list):
                formatted = []
                for name in names:
                    if isinstance(name, str):
                        formatted.append(name.lstrip('/'))
                    else:
                        formatted.append(name)
                return formatted
            return names

        csdict = self.instance.containers(**kwargs)
        if len(csdict) > 0:

            if 'quiet' not in kwargs or not kwargs['quiet']:
                for i in range(len(csdict)):
                    csdict[i]['Names'] = format_names(csdict[i]['Names'])
                    csdict[i]['Created'] = pretty.date(csdict[i]['Created'])

            return csdict
        else:
            return ['There are no containers to list.']

    def pause(self, *args, **kwargs):
        """
        Pause all processes in a container. Equivalent of docker pause.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def port(self, *args, **_):
        """
        List port mappings for the container. Equivalent of docker port.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def rm(self, *args, **kwargs):
        """
        Remove a container. Equivalent of docker rm.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def rmi(self, *args, **kwargs):
        """
        Remove an image. Equivalent of docker rm.
        :param kwargs:
        :return: Image name.
        """
        pass

    def run(self, *args, **kwargs):
        """
        Create and start a container. Equivalent of docker run.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        if not args:
            return ['Image name is required.']

        if kwargs['remove'] and kwargs['detach']:
            return ['Use either --rm or --detach.']

        # Always call external cli for this, rather than figuring out
        # why docker-py throws "jack is incompatible with use of CloseNotifier in same ServeHTTP call"
        kwargs['force'] = True
        called, args, kwargs = self.call_external_cli('run', *args, **kwargs)
        if not called:
            kwargs['image'] = args[0]
            kwargs['command'] = args[1:] if len(args) > 1 else []

            kwargs = self._add_port_bindings(kwargs)
            kwargs = self._add_exposed_ports(kwargs)
            kwargs = self._add_link_bindings(kwargs)
            kwargs = self._add_volumes_from(kwargs)
            kwargs = self._add_volumes(kwargs)
            kwargs = self._add_network_mode(kwargs)

            create_args = allowed_args('create', **kwargs)
            result = self.instance.create_container(**create_args)

            if result:
                if "Warnings" in result and result['Warnings']:
                    return [result['Warnings']]
                if "Id" in result and result['Id']:
                    self.is_refresh_containers = True
                    is_attach = 'detach' not in kwargs or not kwargs['detach']
                    start_args = allowed_args('start', **kwargs)
                    start_args.update({
                        'container': result['Id'],
                        'attach': is_attach
                    })
                    return self.start(**start_args)
            return ['There was a problem running the container.']

    def create(self, *args, **kwargs):
        """
        Create a container. Equivalent of docker create.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def rename(self, *args, **kwargs):
        """
        Rename a container. Equivalent of docker rename.
        :param kwargs:
        :return: None.
        """
        pass

    def restart(self, *args, **kwargs):
        """
        Restart a running container. Equivalent of docker restart.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        if not args:
            return ['Container name is required.']

        def stream():
            for container in args:
                self.instance.restart(container, **kwargs)
                yield container

        return stream()

    @if_exception_return(InvalidVersion, None)
    def volume_create(self, *args, **kwargs):
        """
        Create a volume. Equivalent of docker volume create.
        :param kwargs:
        :return: Volume name.
        """
        pass

    @if_exception_return(InvalidVersion, None)
    def volume_ls(self, *args, **kwargs):
        """
        List volumes. Equivalent of docker volume ls.
        :param kwargs:
        :return: Iterable.
        """
        quiet = kwargs.pop('quiet', False)

        kwargs = self._add_filters(kwargs)

        vdict = self.instance.volumes(**kwargs)
        result = vdict.get('Volumes', None)

        if result:
            if quiet:
                result = [volume['Name'] for volume in result]
            return result
        else:
            return ['There are no volumes to list.']

    @if_exception_return(InvalidVersion, None)
    def volume_rm(self, *args, **kwargs):
        """
        Remove a volume. Equivalent of docker volume rm.
        :param kwargs:
        :return: Volume name.
        """
        pass

    @if_exception_return(InvalidVersion, None)
    def volume_inspect(self, *args, **_):
        """
        Return volume info. Equivalent of docker volume ls.
        :return: dict
        """
        pass

    def tag(self, *args, **kwargs):
        """
        Tag an image into repository. Equivalent of docker tag.
        :param kwargs:
        :return: Iamge ID.
        """
        pass

    def _add_filters(self, params):
        """
        Update kwargs if filters are present.
        :param params: dict
        :return dict
        """
        if params.get('filters', None):
            filters = parse_kv_as_dict(params['filters'], True)
            params['filters'] = filters
        return params

    def _add_opts(self, params):
        """
        Update kwargs if opts are present.
        :param params: dict
        :return dict
        """
        pass

    def _add_volumes(self, params):
        """
        Update kwargs if volumes are present.
        :param params: dict
        :return dict
        """
        if params.get('volumes', None):
            binds = parse_volume_bindings(params['volumes'])
            params['volumes'] = [x['bind'] for x in binds.values()]
            conf = self.instance.create_host_config(binds=binds)
            self._update_host_config(params, conf)
        return params

    def _add_volumes_from(self, params):
        """
        Update kwargs if volumes-from are present.
        :param params: dict
        :return dict
        """
        if params.get('volumes_from', None):
            cs = ','.join(params['volumes_from'])
            cs = [x.strip() for x in cs.split(',') if x]
            conf = self.instance.create_host_config(volumes_from=cs)
            self._update_host_config(params, conf)
        return params

    def _add_network_mode(self, params):
        """
        Update kwargs if --net is present.
        :param params: dict
        :return: dict
        """
        if 'net' in params:
            conf = self.instance.create_host_config(network_mode=params['net'])
            self._update_host_config(params, conf)
        return params

    def _add_link_bindings(self, params):
        """
        Update kwargs if user wants to link containers.
        :param params: dict
        :return dict
        """
        if params.get('links', None):
            links = {}
            for link in params['links']:
                link_name, link_alias = link.split(':', 1)
                links[link_name] = link_alias
            link_conf = self.instance.create_host_config(links=links)
            self._update_host_config(params, link_conf)
        return params

    def _add_port_bindings(self, params):
        """
        Update kwargs if user wants to bind some ports.
        :param params: dict
        :return dict
        """
        if params.get('port_bindings', None):
            port_bindings = parse_port_bindings(params['port_bindings'])

            # Have to provide list of ports to open in create_container.
            params['ports'] = port_bindings.keys()

            # Have to provide host config with port mappings.
            port_conf = self.instance.create_host_config(
                port_bindings=port_bindings)

            self._update_host_config(params, port_conf)

        return params

    def _add_exposed_ports(self, params):
        """
        Update kwargs if user wants to expose some ports.
        :param params: dict
        :return dict
        """
        if params.get('expose', None):
            ports = parse_exposed_ports(params['expose'])

            # Have to provide list of ports to open in create_container.
            params['ports'] = ports.keys()

            # Have to provide host config with port mappings.
            port_conf = self.instance.create_host_config(
                port_bindings=ports)

            self._update_host_config(params, port_conf)

        return params

    def _update_host_config(self, params, config_to_merge):
        """
        Update config dictionary in kwargs with another dictionary.
        :param params: dict
        :param config_to_merge: dict with new values
        :return dict
        """
        if params.get('host_config', None):
            params['host_config'].update(config_to_merge)
        else:
            params['host_config'] = config_to_merge
        return params

    def _is_repo_tag_valid(self, repo):
        """
        When an image is tagged into a repo, make sure only allowed symbols
        are used.
        :param repo:
        :return: (boolean, "error message")
        """
        pass

    def execute(self, *args, **kwargs):
        """
        Execute a command in the container. Equivalent of docker exec.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def build(self, *args, **kwargs):
        """
        Build an image. Equivalent of docker build.
        :param kwargs:
        :return: Iterable output.
        """
        pass

    def shell(self, *args, **_):
        """
        Get the shell into a running container. A shortcut for
        docker exec -it /usr/bin/env bash.
        :param kwargs:
        :return: None
        """
        pass

    def start(self, *args, **kwargs):
        """
        Start a container. Equivalent of docker start.
        :param kwargs:
        :return: Container ID or iterable output.
        """

        if args:
            kwargs['container'] = args[0]

        if not kwargs['container']:
            return ['Container name is required.']

        called, args, kwargs = self.call_external_cli('start', *args, **kwargs)
        if not called:

            if 'remove' in kwargs and kwargs['remove']:
                def on_after():
                    pass

                self.after = on_after

            startargs = allowed_args('start', **kwargs)

            attached = None

            if 'attach' in kwargs and kwargs['attach']:
                attached = self.view(
                    container=kwargs['container'],
                    stream=True,
                    stdout=True,
                    stderr=False,
                    logs=False)

            result = self.instance.start(**startargs)

            # Just in case the stream generated no output, let's allow for
            # retrieving the logs. They will be our last resort output.
            self.log = lambda: self.instance.logs(kwargs['container'])

            self.is_refresh_running = True
            if result:
                return [result]
            elif attached:
                return attached
            else:
                return [kwargs['container']]

    def view(self, *_, **kwargs):
        """
        Attach to container STDOUT and / or STDERR.
        Docker-py does not allow attaching to STDIN.
        :param kwargs:
        :return: Iterable output
        """
        result = self.instance.attach(**kwargs)
        return result

    def login(self, *args, **kwargs):
        """
        Register or log in to a Docker registry server.
        :param kwargs:
        :return: None
        """
        pass

    def logs(self, *args, **kwargs):
        """
        Retrieve container logs. Equivalent of docker logs.
        :param kwargs:
        :return: Iterable output
        """
        if not args:
            return ['Container ID/name is required.']

        kwargs['container'] = args[0]

        result = self.instance.logs(**kwargs)
        if isinstance(result, bytes):
            result = result.decode()
        if not kwargs['stream']:
            result = [result]
        return result

    def images(self, *_, **kwargs):
        """
        Return the list of images. Equivalent of docker images.
        :return: list of dicts
        """
        result = self.instance.images(**kwargs)
        re_digits = re.compile('^[0-9]+$', re.UNICODE)

        def convert_image_dict(a):
            """
            Drop some keys and change some values to pretty-print image dict.
            """
            b = {}
            for k, v in a.items():
                if k not in ['RepoTags', 'RepoDigests', 'Labels', 'Size']:
                    b[k] = v
                if k == 'Created' and v and re_digits.search(str(v)):
                    b[k] = pretty.date(v)
                if k == 'VirtualSize':
                    b[k] = filesize(v)

            # If we have more than one repo tag, return as many dicts

            if a.get('RepoTags', None) is None:
                a['RepoTags'] = ['<none>:<none>']

            for rt in a['RepoTags']:
                repo, tag = rt.rsplit(':', 1)
                c = {}
                c.update(b)
                c['Repository'] = repo
                c['Tag'] = tag
                yield c

        if len(result) > 0:
            if isinstance(result[0], dict):
                converted = []
                for x in result:
                    for y in convert_image_dict(x):
                        converted.append(y)
                return converted
            return result
        else:
            return ['There are no images to list.']

    def search(self, *args, **_):
        """
        Return the list of images matching specified term.
        Equivalent of docker search.
        :return: list of dicts
        """

        if not args or len(args) < 1:
            return "Search term is required."

        result = self.instance.search(args[0])

        if len(result) > 0:
            for res in result:
                # Make results  more readable, like official CLI does.
                if 'is_trusted' in res:
                    res['is_trusted'] = '[OK]' if res['is_trusted'] else ''
                if 'is_official' in res:
                    res['is_official'] = '[OK]' if res['is_official'] else ''
            return result
        else:
            return ['No images were found.']

    def stop(self, *args, **kwargs):
        """
        Stop a running container. Equivalent of docker stop.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        if not args:
            return ['Container name is required.']

        def stream():
            for container in args:
                try:
                    self.instance.stop(container, **kwargs)
                    self.is_refresh_running = True
                    yield container
                except APIError as ex:
                    yield '{0:.25}: {1}'.format(container, ex.explanation)

        return stream()

    def kill(self, *args, **kwargs):
        """
        Kill a running container. Equivalent of docker kill.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        if not args:
            return ['Container name is required.']

        def stream():
            for container in args:
                try:
                    self.instance.kill(container, **kwargs)
                    self.is_refresh_running = True
                    yield container
                except APIError as ex:
                    yield '{0:.25}: {1}'.format(container, ex.explanation)

        return stream()

    def top(self, *args, **kwargs):
        """
        Show top processes in a container. Equivalent of docker rm.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def pull(self, *args, **kwargs):
        """
        Pull an image by name. Equivalent of docker pull.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def push(self, *args, **kwargs):
        """
        Push an image into repository. Equivalent of docker push.
        :param kwargs:
        :return: interactive.
        """
        pass

    def unpause(self, *args, **kwargs):
        """
        Unpause all processes in a container. Equivalent of docker unpause.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        pass

    def call_external_cli(self, cmd, *args, **kwargs):
        """
        Call the "official" CLI if needed.
        :param args:
        :param kwargs:
        :return:
        """
        called = False

        is_force = kwargs.pop('force', False)
        is_interactive = kwargs.get('interactive', None)
        is_tty = kwargs.get('tty', None)
        is_attach = kwargs.get('attach', None)
        is_attach_bool = is_attach in [True, False]

        def execute_external():
            """
            Call the official cli
            """
            command = format_command_line(cmd, False, args, kwargs)
            process = pexpect.spawnu(command)
            process.interact()

        def on_after_interactive():
            # \r is to make sure when there is some error output,
            # prompt is back to beginning of line
            pass

        def on_after_attach():
            pass

        if is_force or is_interactive or is_tty or (is_attach and not is_attach_bool):
            self.after = on_after_attach if is_attach or (not is_interactive and not is_tty) else on_after_interactive
            called = True
            execute_external()

        return called, args, kwargs


class DockerPermissionException(Exception):

    def __init__(self, inner_exception):
        self.inner_exception = inner_exception
        self.message = """You don't have the necessary permissions to call Docker API.
Try the following:

  # Add a docker group if it does not exist yet.
  sudo groupadd docker

  # Add the connected user "${USER}" to the docker group.
  # Change the user name to match your preferred user.
  sudo gpasswd -a ${USER} docker

  # Restart the Docker daemon.
  # If you are in Ubuntu 14.04, use docker.io instead of docker
  sudo service docker restart

You may need to reboot the machine.
"""


class DockerSslException(Exception):
    """
    Wrapper to handle SSL: CERTIFICATE_VERIFY_FAILED:
    https://github.com/docker/docker-py/issues/465
    """

    def __init__(self, inner_exception):
        self.inner_exception = inner_exception
        self.message = """Your version of requests library has a problem with OpenSSL.
Try the following:

  brew switch openssl 1.0.1j
"""


class DockerTimeoutException(Exception):
    """
    Wrapper to handle ConnectTimeoutError.
    """

    def __init__(self, inner_exception):
        self.inner_exception = inner_exception
        self.message = """The Docker daemon, or boot2docker \
does not seem to be running."""
