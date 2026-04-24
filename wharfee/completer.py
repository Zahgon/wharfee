# -*- coding: utf-8
import fuzzyfinder

from itertools import chain
from prompt_toolkit.completion import Completer, Completion
from .options import COMMAND_OPTIONS, COMMAND_NAMES, all_options, find_option, \
    split_command_and_args
from .helpers import list_dir, parse_path, complete_path
from .utils import shlex_split, shlex_first_token


class DockerCompleter(Completer):
    """
    Completer for Docker commands and parameters.
    """

    def __init__(self, containers=None, running=None, images=None, tagged=None,
                 volumes=None, long_option_names=True, fuzzy=False):
        """
        Initialize the completer
        :return:
        """
        self.all_completions = set(COMMAND_NAMES)
        self.containers = set(containers) if containers else set()
        self.running = set(running) if running else set()
        self.images = set(images) if images else set()
        self.tagged = set(tagged) if tagged else set()
        self.volumes = set(volumes) if volumes else set()
        self.long_option_mode = long_option_names
        self.fuzzy = fuzzy
        self.enabled = True

    def set_enabled(self, enabled):
        """
        Setter for enabled/disabled property.
        :param enabled: boolean
        """
        pass

    def set_volumes(self, volumes):
        """
        Setter for list of available volumes.
        :param volumes: list
        """
        self.volumes = set(volumes) if volumes else set()

    def set_containers(self, containers):
        """
        Setter for list of available containers.
        :param containers: list
        """
        self.containers = set(containers) if containers else set()

    def set_running(self, containers):
        """
        Setter for list of running containers.
        :param containers: list
        """
        self.running = set(containers) if containers else set()

    def set_images(self, images):
        """
        Setter for list of available images.
        :param images: list
        """
        self.images = set(images) if images else set()

    def set_tagged(self, images):
        """
        Setter for list of tagged images.
        :param images: list
        """
        self.tagged = set(images) if images else set()

    def set_long_options(self, is_long):
        """
        Setter for long option names.
        :param is_long: boolean
        """
        self.long_option_mode = is_long

    def get_long_options(self):
        """
        Getter for long option names.
        """
        return self.long_option_mode

    def set_fuzzy_match(self, is_fuzzy):
        """
        Setter for fuzzy match option.
        :param is_fuzzy: boolean
        """
        self.fuzzy = is_fuzzy

    def get_fuzzy_match(self):
        """
        Getter for fuzzy match option.
        :return: boolean
        """
        return self.fuzzy

    def get_completions(self, document, _):
        """
        Get completions for the current scope.
        :param document:
        :param _: complete_event
        """
        pass

    @staticmethod
    def find_command_matches(command, word='', prev='', params=None,
                             containers=None, running=None, images=None,
                             tagged=None, volumes=None, long_options=True,
                             fuzzy=False):
        """
        Find all matches in context of the given command.
        :param command: string: command keyword (such as "ps", "images")
        :param word: string: word currently being typed
        :param prev: string: previous word
        :param params: list of command parameters
        :param containers: list of containers
        :param running: list of running containers
        :param images: list of images
        :param tagged: list of tagged images
        :param volumes: list of volumes
        :param long_options: boolean
        :param fuzzy: boolean
        :return: iterable
        """
        pass

    @staticmethod
    def find_filepath_matches(word):
        """
        Yield matching directory or file names.
        :param word:
        :return: iterable
        """
        pass

    @staticmethod
    def find_directory_matches(word):
        """
        Yield matching directory names.
        :param word:
        :return: iterable
        """
        pass

    @staticmethod
    def find_dictionary_matches(word, dic, fuzzy):
        """
        Yield all matching names in dict
        :param dic: dict mapping name to display name
        :param word: string user typed
        :param fuzzy: boolean
        :return: iterable
        """
        pass

    @staticmethod
    def find_collection_matches(word, lst, fuzzy):
        """
        Yield all matching names in list
        :param lst: collection
        :param word: string user typed
        :param fuzzy: boolean
        :return: iterable
        """
        pass

    @staticmethod
    def find_matches(text, collection, fuzzy):
        """
        Find all matches for the current text
        :param text: text before cursor
        :param collection: collection to suggest from
        :param fuzzy: boolean
        :return: iterable
        """
        pass

    @staticmethod
    def get_tokens(text):
        """
        Parse out all tokens.
        :param text:
        :return: list
        """
        pass

    @staticmethod
    def first_token(text):
        """
        Find first word in a sentence
        :param text:
        :return:
        """
        pass

    @staticmethod
    def last_token(text):
        """
        Find last word in a sentence
        :param text:
        :return:
        """
        pass

    @staticmethod
    def safe_split(text):
        """
        Shlex can't always split. For example, "\" crashes the completer.
        """
        pass

    @staticmethod
    def in_quoted_string(text):
        """
        Find last word in a sentence
        :param text:
        :return:
        """
        pass
